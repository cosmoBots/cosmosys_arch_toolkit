"""Import supported interchange formats into a fresh Blender scene."""
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

IMPORTERS = {
    '.glb': ('import_scene', 'gltf'),
    '.gltf': ('import_scene', 'gltf'),
    '.obj': ('wm', 'obj_import'),
    '.stl': ('wm', 'stl_import'),
    '.ply': ('wm', 'ply_import'),
    '.fbx': ('import_scene', 'fbx'),
}


def filter_objects(scene, rules, *, preflight=False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from import_filters import classify
    objects = list(scene.objects)
    modes, evidence = classify([obj.name for obj in objects], rules)
    decisions = dict(zip(objects, modes))
    excluded = set()
    for obj in objects:
        ancestor = obj
        while ancestor is not None:
            if decisions.get(ancestor) == 'exclude':
                excluded.add(obj)
                break
            ancestor = ancestor.parent
    for row in evidence:
        row['matches'] = [objects[index].name for index in row['matches']]
    atomic = [obj for obj in objects if obj not in excluded and decisions[obj] == 'atomic']
    report = dict(rules=evidence, excluded=sorted(obj.name for obj in excluded),
                  atomic=sorted(obj.name for obj in atomic),
                  meshes_before=sum(obj.type == 'MESH' for obj in objects),
                  meshes_after=sum(obj.type == 'MESH' for obj in objects if obj not in excluded), errors=[])
    if not any(obj.type == 'MESH' and obj.data.polygons for obj in objects if obj not in excluded):
        report['errors'].append('El filtrado excluiría todas las superficies del modelo.')
    # Do not silently invalidate an already annotated control contract.
    if any(obj.get('cosmosys_controls') or obj.get('control_key') for obj in excluded):
        report['errors'].append('El filtrado elimina controles anotados; modifica las reglas antes de continuar.')
    if preflight:
        return report
    if report['errors']:
        raise ValueError('; '.join(report['errors']))
    for obj in excluded:
        bpy.data.objects.remove(obj, do_unlink=True)
    # Imported geometry can otherwise remain orphaned inside the saved .blend.
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for obj in atomic:
        obj['cosmosys_import'] = dict(version=1, mode='atomic')
    # Explicit include rules can clear a pre-existing atomic preference.
    matched = {name for row in evidence for name in row['matches']}
    for obj in scene.objects:
        if obj.name in matched and decisions[obj] == 'include' and 'cosmosys_import' in obj:
            del obj['cosmosys_import']
    return report


def import_model(request):
    source = Path(request['source'])
    names = IMPORTERS.get(source.suffix.lower())
    if names is None:
        raise ValueError('Formato no soportado. Usa GLB/glTF, OBJ, STL, PLY o FBX con importador disponible.')
    operator = getattr(getattr(bpy.ops, names[0]), names[1])
    try:
        operator.get_rna_type()
    except (AttributeError, RuntimeError) as error:
        raise ValueError(f'El importador {source.suffix} no está disponible en este Blender.') from error
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'csysArch'
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    result = operator(filepath=str(source))
    if 'FINISHED' not in result:
        raise ValueError('Blender no completó la importación.')
    meshes = [obj for obj in scene.objects if obj.type == 'MESH']
    if not meshes or not any(obj.data.polygons for obj in meshes):
        raise ValueError('El fichero no contiene superficies de malla importables.')
    filtering = filter_objects(scene, request.get('filters', []), preflight=request.get('preflight', False))
    if request.get('preflight'):
        return dict(errors=filtering['errors'], warnings=[], scene=scene.name, preflight=True, filtering=filtering)
    meshes = [obj for obj in scene.objects if obj.type == 'MESH']
    warnings = []
    if source.suffix.lower() in {'.obj', '.stl', '.ply'}:
        warnings.append('Formato sin unidad garantizada: se interpreta 1 unidad como 1 metro; verifica dimensiones o indica --scale.')
    scale = request['scale']
    if scale != 1:
        for obj in [obj for obj in scene.objects if obj.parent is None]:
            obj.matrix_world = Matrix.Scale(scale, 4) @ obj.matrix_world
        bpy.context.view_layer.update()
        warnings.append(f'Factor de escala de importación: {scale:g}. Aplicar escalas antes de exportar controles.')
    path = Path(request['output']) / (request['name'] + '.blend')
    if path.exists():
        raise ValueError('El .blend de salida ya existe; no se sobrescribe.')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    return dict(errors=[], warnings=warnings, filtering=filtering, scene=scene.name, objects=len(scene.objects),
                meshes=len(meshes), imported_blend=str(path))
