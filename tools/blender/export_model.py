"""Metadata/constraint exporter. Executed by Blender, never saves its input."""
from contextlib import contextmanager
import math
from pathlib import Path
import sys

import bpy
from driver_controls import metadata_definition, recognized_driver, rest_position

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exchange import CONTRACT, CONTRACT_VERSION, verify_pair, yaml_text


def gltf_available():
    try:
        bpy.ops.export_scene.gltf.get_rna_type()
    except (AttributeError, RuntimeError) as error:
        raise ValueError('Exportador glTF no disponible en esta instalación de Blender.') from error


def choose_scene(name):
    if name:
        if name in bpy.data.scenes:
            return bpy.data.scenes[name]
        raise ValueError('Indica --scene. Escenas disponibles: ' + ', '.join(s.name for s in bpy.data.scenes))
    if 'csysArch' in bpy.data.scenes:
        return bpy.data.scenes['csysArch']
    # Link the same objects, never move them out of the user's collections.
    # Once created, membership is owned by the user and is not synchronized.
    source = bpy.context.scene
    scene = bpy.data.scenes.new('csysArch')
    scene.unit_settings.system = source.unit_settings.system
    scene.unit_settings.scale_length = source.unit_settings.scale_length
    scene.unit_settings.length_unit = source.unit_settings.length_unit
    for obj in bpy.data.objects:
        scene.collection.objects.link(obj)
    return scene


def choose_roots(scene, name):
    candidates = [obj for obj in scene.objects if obj.parent is None and
                  any(child.type == 'MESH' for child in [obj, *obj.children_recursive])]
    if name:
        root = scene.objects.get(name)
        if root not in candidates:
            raise ValueError('Indica --root con un objeto sin padre y con mallas. Raíces disponibles: ' +
                             ', '.join(obj.name for obj in candidates))
        return [root]
    if not candidates:
        raise ValueError('La escena no contiene raíces con mallas exportables.')
    return candidates


def definition(obj):
    if 'control_definition' in obj:
        return metadata_definition(obj)
    constraints = [c for c in obj.constraints if not c.mute]
    if len(constraints) != 1 or constraints[0].type not in {'LIMIT_ROTATION', 'LIMIT_LOCATION'}:
        raise ValueError('se necesita una única constraint activa Limit Rotation o Limit Location')
    constraint = constraints[0]
    if constraint.owner_space not in {'LOCAL', 'WORLD'} or abs(constraint.influence - 1) > 1e-6:
        raise ValueError('la constraint debe ser LOCAL o WORLD y tener influencia 1')
    if constraint.owner_space == 'WORLD':
        ancestor = obj.parent
        while ancestor:
            if ancestor.get('control_key') is not None or ancestor.constraints or ancestor.animation_data or any(abs(v) > 1e-6 for v in ancestor.matrix_world.to_euler('XYZ')):
                raise ValueError('WORLD requiere ancestros fijos alineados con el mundo')
            ancestor = ancestor.parent
        if any(abs(v) > 1e-6 for v in obj.rotation_euler):
            raise ValueError('WORLD requiere rotación de reposo cero')
        if constraint.type == 'LIMIT_LOCATION' and any(abs(v) > 1e-6 for v in obj.matrix_world.translation):
            raise ValueError('WORLD Location requiere reposo en el origen mundial')
    if obj.rotation_mode != 'XYZ':
        raise ValueError('el pivote debe usar rotación Euler XYZ')
    if any(abs(v) > 1e-6 for v in [*obj.delta_location, *obj.delta_rotation_euler]) or any(abs(v-1) > 1e-6 for v in obj.delta_scale):
        raise ValueError('aplica o elimina las transformaciones delta del pivote')
    rotation = constraint.type == 'LIMIT_ROTATION'
    ranges = {}
    for axis in 'xyz':
        bounded = (getattr(constraint, 'use_limit_' + axis) if rotation else
                   getattr(constraint, 'use_min_' + axis) and getattr(constraint, 'use_max_' + axis))
        if not bounded:
            raise ValueError('limita los tres ejes: uno móvil y los otros dos bloqueados a cero')
        low, high = getattr(constraint, 'min_' + axis), getattr(constraint, 'max_' + axis)
        if not math.isfinite(low) or not math.isfinite(high) or high < low:
            raise ValueError('límites no finitos o invertidos')
        ranges[axis] = (low, high)
    moving = [axis for axis, (low, high) in ranges.items() if high-low > 1e-7]
    if len(moving) != 1 or any(abs(v) > 1e-6 for axis, values in ranges.items() if axis not in moving for v in values):
        raise ValueError('se necesita un eje móvil y dos bloqueados a cero')
    axis = moving[0]
    glb_axis, sign = {'x': ('x', 1), 'y': ('z', -1), 'z': ('y', 1)}[axis]
    low, high = sorted((math.degrees(v) if rotation else v) * sign for v in ranges[axis])
    low, high = round(low, 4), round(high, 4)
    if not low <= 0 <= high or low >= high:
        raise ValueError('el rango debe incluir cero y tener amplitud representable')
    raw_step = obj.get('control_step_degrees' if rotation else 'control_step_metres', 1.0 if rotation else 0.05)
    if isinstance(raw_step, bool):
        raise ValueError('el paso debe ser numérico, finito y positivo')
    step = float(raw_step)
    if not math.isfinite(step) or step <= 0:
        raise ValueError('el paso debe ser numérico, finito y positivo')
    control = dict(target_node=obj.name, transform='rotation' if rotation else 'position',
                space='global' if constraint.owner_space == 'WORLD' else 'local',
                axis=glb_axis, min=low, max=high, step=step)
    if 'control_round_decimals' in obj:
        value = obj['control_round_decimals']
        if type(value) is not int or not 0 <= value <= 15:
            raise ValueError('control_round_decimals debe ser un entero entre0 y15')
        control['round_decimals'] = value
    return control, axis


def inventory(scene, roots):
    objects = sorted({obj for root in roots for obj in [root, *root.children_recursive]
                      if obj.name in scene.objects and obj.type not in {'CAMERA', 'LIGHT'}}, key=lambda obj: obj.name)
    controls, axes, errors, warnings = {}, {}, [], []
    seen_keys = set()
    for obj in objects:
        problems = []
        if obj.type not in {'MESH', 'EMPTY'}:
            problems.append('convierte a malla; sólo se admiten MESH y EMPTY')
        if obj.instance_type != 'NONE':
            problems.append('convierte las instancias en objetos reales antes de exportar')
        if obj.parent and obj.parent.type in {'CAMERA', 'LIGHT'}:
            problems.append('no uses una cámara o luz como padre de geometría exportable')
        if obj.name not in bpy.context.view_layer.objects:
            problems.append('la colección debe estar incluida en la capa activa')
        if any(not math.isfinite(v) for row in obj.matrix_world for v in row):
            problems.append('transformación no finita')
        if any(abs(v-1) > 1e-6 for v in obj.scale):
            problems.append('aplica la escala (debe ser 1,1,1)')
        animation = obj.animation_data
        if 'control_definition' in obj:
            try:
                allowed = 'control_definition' in obj and recognized_driver(obj, metadata_definition(obj)[0])
            except (ValueError, TypeError, KeyError):
                allowed = False
            if not allowed:
                problems.append('animación/driver ajeno al control del toolkit; no se exporta')
        elif animation and (animation.action or animation.drivers or animation.nla_tracks):
            problems.append('animación/driver ajeno al control del toolkit; no se exporta')
        if obj.type == 'MESH' and obj.data.shape_keys:
            problems.append('las shape keys no están soportadas')
        key = obj.get('control_key')
        if 'control_definition' in obj and key is None:
            problems.append('control_definition sin control_key')
        if key is not None:
            if not isinstance(key, str) or not key.strip() or key in seen_keys:
                problems.append('control_key debe ser texto no vacío y único')
            else:
                seen_keys.add(key)
                try:
                    controls[key], axes[key] = definition(obj)
                except (ValueError, TypeError) as error:
                    problems.append(str(error))
        elif any(not c.mute for c in obj.constraints):
            problems.append('constraint activa sin control_key; no se hornea implícitamente')
        if obj.hide_viewport or obj.hide_get() or obj.hide_render:
            warnings.append(f'{obj.name}: se incluirá aunque esté oculto; se exporta el subárbol completo.')
        errors.extend(f'{obj.name}: {problem}' for problem in problems)
    if not any(obj.type == 'MESH' for obj in objects):
        errors.append('La raíz debe contener alguna malla.')
    if not controls:
        warnings.append('Modelo estático: no hay controles control_key.')
    return objects, controls, axes, errors, warnings


@contextmanager
def rest_pose(objects, controls, axes):
    selection, active = list(bpy.context.selected_objects), bpy.context.view_layer.objects.active
    saved = [(obj, obj.location.copy(), obj.rotation_euler.copy(), obj.hide_get(), obj.hide_viewport, obj.hide_render, obj.hide_select) for obj in objects]
    drivers = [(obj, obj.animation_data.drivers[0], obj['control_value']) for obj in objects
               if 'control_definition' in obj and obj.get('control_key') in controls]
    try:
        for obj, curve, value in drivers:
            curve.mute = True
            obj['control_value'] = 0.0
            obj.update_tag()
        for obj in objects:
            obj.hide_viewport = obj.hide_render = obj.hide_select = False
            obj.hide_set(False)
            key = obj.get('control_key')
            if key in controls:
                if controls[key]['transform'] == 'rotation':
                    obj.rotation_euler = (0, 0, 0)
                else:
                    index = 'xyz'.index(axes[key])
                    obj.location[index] = rest_position(obj)[index] if 'control_definition' in obj else 0
        bpy.context.view_layer.update()
        yield
    finally:
        bpy.ops.object.select_all(action='DESELECT')
        for obj, location, rotation, hidden, viewport, render, selectable in saved:
            obj.location, obj.rotation_euler = location, rotation
            obj.hide_set(hidden)
            obj.hide_viewport, obj.hide_render, obj.hide_select = viewport, render, selectable
        for obj, curve, value in drivers:
            obj['control_value'] = value
            curve.mute = False
            obj.update_tag()
        bpy.context.view_layer.update()
        for obj in selection:
            if obj.name in bpy.context.view_layer.objects:
                obj.select_set(True)
        bpy.context.view_layer.objects.active = active


def mesh_bounds(objects):
    graph = bpy.context.evaluated_depsgraph_get()
    minimum, maximum = [math.inf]*3, [-math.inf]*3
    vertices = faces = 0
    for obj in objects:
        if obj.type != 'MESH':
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            faces += len(mesh.polygons)
            vertices += len(mesh.vertices)
            for vertex in mesh.vertices:
                point = evaluated.matrix_world @ vertex.co
                for axis, value in enumerate(point):
                    if not math.isfinite(value):
                        raise ValueError(f'{obj.name}: vértice no finito')
                    minimum[axis] = min(minimum[axis], value)
                    maximum[axis] = max(maximum[axis], value)
        finally:
            evaluated.to_mesh_clear()
    if not vertices or not faces:
        raise ValueError('El subárbol no contiene superficies exportables.')
    return dict(vertices=vertices, faces=faces, minimum=minimum, maximum=maximum,
                dimensions=[maximum[i]-minimum[i] for i in range(3)], units='metres', axes='Blender Z-up')


def write_export(roots, objects, controls, output, name):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / (name + suffix)).exists() for suffix in ('.glb', '.yaml')):
        raise ValueError('La salida ya existe; utiliza una carpeta nueva.')
    partial = output / '.partial'
    partial.mkdir()
    saved = [(obj, {key: obj[key].to_dict() if hasattr(obj[key], 'to_dict') else obj[key]
                    for key in ('cosmosys_model', 'cosmosys_controls') if key in obj}) for obj in objects]
    try:
        root = roots[0]  # Contract owner only; no synthetic parent in Blender/GLB.
        for obj in objects:
            for key in ('cosmosys_model', 'cosmosys_controls'):
                if key in obj:
                    del obj[key]
            key = obj.get('control_key')
            if key in controls:
                obj['cosmosys_controls'] = {key: controls[key]}
        root['cosmosys_model'] = dict(schema=CONTRACT, version=CONTRACT_VERSION, rotation_order='XYZ',
                                     coordinate_system='glTF Y-up, metres', rest='Offsets from zero pose')
        presentation = root.get('gallery_presentation')
        presentation = presentation.to_dict() if presentation else {}
        if presentation:
            root['cosmosys_model']['presentation'] = presentation
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            obj.select_set(True)
        result = bpy.ops.export_scene.gltf(filepath=str(partial / f'{name}.glb'), export_format='GLB',
                    use_selection=True, use_active_scene=True, export_extras=True, export_yup=True,
                    export_animations=False, export_cameras=False, export_lights=False, export_apply=True)
        if 'FINISHED' not in result:
            raise ValueError('Blender no completó la exportación glTF.')
        (partial / f'{name}.yaml').write_text(yaml_text(f'{name}.glb', controls, presentation), encoding='utf8')
        verify_pair(partial / f'{name}.glb', partial / f'{name}.yaml')
        for suffix in ('.glb', '.yaml'):
            (partial / (name + suffix)).rename(output / (name + suffix))
        partial.rmdir()
    finally:
        for obj, properties in saved:
            for key in ('cosmosys_model', 'cosmosys_controls'):
                if key in obj:
                    del obj[key]
            for key, value in properties.items():
                obj[key] = value


def process(*, scene_name=None, root_name=None, output_dir=None, name='model', export_files=False):
    gltf_available()
    scene = choose_scene(scene_name)
    previous = bpy.context.window.scene
    try:
        bpy.context.window.scene = scene
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        roots = choose_roots(scene, root_name)
        objects, controls, axes, errors, warnings = inventory(scene, roots)
        report = dict(scene=scene.name, root=roots[0].name if len(roots) == 1 else None,
                      roots=[root.name for root in roots], objects=len(objects), controls=controls,
                      errors=errors, warnings=warnings)
        if scene.unit_settings.system != 'METRIC' or abs(scene.unit_settings.scale_length-1) > 1e-6:
            errors.append('Configura unidades Metric y Unit Scale = 1 (metros).')
        if not errors:
            with rest_pose(objects, controls, axes):
                report['geometry'] = mesh_bounds(objects)
                if export_files:
                    write_export(roots, objects, controls, output_dir, name)
        return report
    finally:
        bpy.context.window.scene = previous


def export(output_dir, *, scene_name=None, root_name=None, name='model'):
    report = process(scene_name=scene_name, root_name=root_name, output_dir=output_dir, name=name, export_files=True)
    if report['errors']:
        raise ValueError('\n'.join(report['errors']))
    return report['controls']
