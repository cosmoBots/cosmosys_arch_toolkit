"""Run a trusted toolkit job inside the FreeCAD console."""
import json
from pathlib import Path
import sys
import traceback

import FreeCAD as App
import Mesh
import Part

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from glb import Scene


def metres(vector):
    return [vector.x / 1000, vector.z / 1000, -vector.y / 1000]


def rotation_quaternion(rotation):
    x, y, z, w = rotation.Q
    return [x, z, -y, w]


def identity_rotation(rotation):
    return all(abs(value) < 1e-7 for value in rotation.Q[:3])


def model_tree(document, root_name):
    def collect(obj):
        if not getattr(obj, 'Visibility', True):
            return None
        if obj.isDerivedFrom('App::Link'):
            raise ValueError(f'{obj.Label}: App::Link no admite exportación con pivotes. Usa piezas nativas.')
        if obj.isDerivedFrom('App::Origin'):
            return None
        if obj.isDerivedFrom('App::Part') or obj.TypeId == 'App::DocumentObjectGroup':
            children = [node for child in obj.Group if (node := collect(child)) is not None]
            # STEP assemblies can carry the compound of all their children.
            # Export the assembly as a transform only, or geometry is repeated.
            return (obj, None, children) if children else None
        if obj.isDerivedFrom('Mesh::Feature'):
            return (obj, obj.Mesh, []) if obj.Mesh.CountFacets else None
        shape = getattr(obj, 'Shape', None)
        if shape is None or shape.isNull() or not shape.Faces:
            return None
        return obj, shape, []

    roots = document.RootObjects
    if root_name:
        matches = [obj for obj in roots if root_name in (obj.Name, obj.Label)]
        if len(matches) != 1:
            raise ValueError(f'Raíz FreeCAD ausente o ambigua: {root_name}')
        roots = matches
    model = [node for obj in roots if (node := collect(obj)) is not None]
    if not model:
        raise ValueError('El documento FreeCAD no contiene superficies visibles exportables.')
    return model


def inspect_model(job, document):
    scene = Scene()
    nodes = scene.document['nodes']
    objects = {}
    ancestors = {}
    triangles = 0
    controls = job.get('controls', {})
    presentation = job.get('presentation', {})
    export = job['action'] == 'export'

    def visit(item, parents):
        nonlocal triangles
        obj, shape, children = item
        name = obj.Label.strip() or obj.Name
        if name in objects:
            raise ValueError(f'Etiqueta FreeCAD repetida: {name}. Asigna etiquetas únicas.')
        objects[name] = obj
        ancestors[name] = parents
        placement = getattr(obj, 'Placement', App.Placement())
        node = dict(name=name, translation=metres(placement.Base),
                    rotation=rotation_quaternion(placement.Rotation))
        index = len(nodes)
        nodes.append(node)
        if children:
            node['children'] = [visit(child, (*parents, name)) for child in children]
        if obj.isDerivedFrom('Mesh::Feature'):
            triangles += shape.CountFacets
            if export:
                local_mesh = shape.copy()
                local_mesh.Placement = App.Placement()
                points, faces = local_mesh.Topology
                node['mesh'] = scene.mesh([metres(point) for point in points], faces)
        elif shape is not None:
            local_shape = shape.copy()
            local_shape.Placement = placement.inverse().multiply(shape.Placement)
            points, faces = local_shape.tessellate(job['deflection'])
            if not faces:
                raise ValueError(f'{name}: la triangulación no produjo caras.')
            triangles += len(faces)
            if export:
                node['mesh'] = scene.mesh([metres(point) for point in points], faces)
        return index

    roots = [visit(item, ()) for item in model_tree(document, job['root'])]
    if triangles == 0:
        raise ValueError('El modelo FreeCAD no contiene triángulos exportables.')
    missing = set(definition['target_node'] for definition in controls.values()) - objects.keys()
    if missing and not job['root']:
        raise ValueError('No se encuentran los objetivos FreeCAD: ' + ', '.join(sorted(missing)))
    if missing and job['action'] == 'annotate':
        raise ValueError('Los objetivos deben pertenecer a la raíz elegida: ' + ', '.join(sorted(missing)))
    selected = {key: definition for key, definition in controls.items()
                if definition['target_node'] in objects}
    moving = {definition['target_node'] for definition in selected.values()}
    for key, definition in selected.items():
        target = definition['target_node']
        obj = objects[target]
        placement = getattr(obj, 'Placement', None)
        if placement is None:
            raise ValueError(f'{key}: {target} necesita Placement para actuar como pivote.')
        if not identity_rotation(placement.Rotation):
            raise ValueError(f'{key}: {target} debe tener rotación de reposo cero; usa un App::Part como pivote.')
        if definition['space'] == 'global' and any(
                parent in moving or not identity_rotation(getattr(objects[parent], 'Placement', App.Placement()).Rotation)
                for parent in ancestors[target]):
            raise ValueError(f'{key}: un eje global requiere ancestros fijos y alineados con el mundo.')
    if export:
        scene.write(job['output'], job['name'], roots, selected, presentation)
    return dict(objects=len(nodes), roots=[nodes[i]['name'] for i in roots], controls=selected,
                geometry=dict(triangles=triangles, units='metres', axes='glTF Y-up'))


def run(job):
    version = tuple(int(part) for part in App.Version()[:3])
    if version < (1, 1, 0):
        raise ValueError('Se necesita FreeCAD 1.1 o posterior.')
    report = {'freecad_version': '.'.join(map(str, version))}
    if job['action'] == 'doctor':
        import Import
        return report
    if job['action'] == 'import':
        if not job['preflight'] and not App.GuiUp:
            raise ValueError('Se necesita la interfaz gráfica de FreeCAD para guardar la vista del FCStd.')
        source = Path(job['source'])
        document = App.newDocument(source.stem)
        try:
            source_triangles = None
            if source.suffix.lower() in ('.glb', '.gltf'):
                from gltf_mesh import import_gltf
                source_triangles = import_gltf(source, document)
            else:
                import Import
                Import.insert(str(source), document.Name)
            document.recompute()
            report.update(inspect_model(job, document))
            if source_triangles is not None:
                report['source_triangles'] = source_triangles
                if not job['root'] and source_triangles != report['geometry']['triangles']:
                    actual = report['geometry']['triangles']
                    report['warnings'] = [f'La malla FreeCAD conserva {actual} de {source_triangles} triángulos de entrada.']
            if not job['preflight']:
                import FreeCADGui as Gui
                view = Gui.getDocument(document.Name).activeView()
                view.viewAxonometric()
                view.fitAll()
                document.saveAs(str(Path(job['output']) / (job['name'] + '.FCStd')))
            return report
        finally:
            App.closeDocument(document.Name)
    document = App.openDocument(job['source'])
    try:
        report.update(inspect_model(job, document))
        return report
    finally:
        App.closeDocument(document.Name)


def main(request):
    job = json.loads(Path(request).read_text(encoding='utf8'))
    report = {'errors': [], 'warnings': []}
    try:
        report.update(run(job))
    except Exception as error:
        report['errors'].append(str(error))
        traceback.print_exc()
    Path(job['response']).write_text(json.dumps(report, ensure_ascii=False, allow_nan=False), encoding='utf8')
