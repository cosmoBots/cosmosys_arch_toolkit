"""Create/update toolkit constraints in a staged copy validated before publication."""
import math
from pathlib import Path

import bpy
from export_model import choose_roots, choose_scene, definition, process
from driver_controls import create_driver, metadata_definition, native_channel, recognized_driver, rest_position


def aligned_global(obj):
    """World constraint/export support is deliberately limited to fixed aligned ancestors."""
    ancestor = obj.parent
    while ancestor:
        if ancestor.get('control_key') is not None or ancestor.constraints or ancestor.animation_data:
            return False
        if any(abs(v) > 1e-6 for v in ancestor.matrix_world.to_euler('XYZ')):
            return False
        ancestor = ancestor.parent
    return True


def normalize_scales(objects):
    """Normalize supported static geometry, or reject before publishing the copy."""
    for obj in objects:
        if any(not math.isfinite(v) or v <= 0 for v in obj.scale):
            raise ValueError(f'{obj.name}: escala no finita, nula o negativa; corrige el modelo antes de anotar.')
    scaled = [obj for obj in objects if any(abs(v - 1) > 1e-6 for v in obj.scale)]
    if not scaled:
        return []
    for obj in objects:
        if (obj.type not in {'MESH', 'EMPTY'} or obj.library or obj.instance_type != 'NONE'
                or obj.animation_data or obj.constraints
                or (obj.type == 'MESH' and (obj.modifiers or obj.data.shape_keys))):
            raise ValueError(f'{obj.name}: no se puede normalizar con seguridad un conjunto con '
                             'animación, constraints, modificadores, shape keys, instancias o datos enlazados.')
    before = {obj.name: [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
              for obj in objects if obj.type == 'MESH'}
    visibility = {obj: (obj.hide_viewport, obj.hide_select, obj.hide_get()) for obj in objects}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            obj.hide_viewport = obj.hide_select = False
            obj.hide_set(False)
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True, isolate_users=True)
        bpy.context.view_layer.update()
        deviation = max(((obj.matrix_world @ vertex.co - before[obj.name][index]).length
                         for obj in objects if obj.type == 'MESH'
                         for index, vertex in enumerate(obj.data.vertices)), default=0)
        if not math.isfinite(deviation) or deviation > 1e-5:
            raise ValueError(f'Normalizar escalas cambió vértices en {deviation:g} m; no se guarda la copia.')
        if any(any(abs(v - 1) > 1e-6 for v in obj.scale) for obj in objects):
            raise ValueError('No se consiguieron escalas unitarias; no se guarda la copia.')
    finally:
        for obj, (hidden, locked, local_hidden) in visibility.items():
            obj.hide_set(local_hidden)
            obj.hide_viewport, obj.hide_select = hidden, locked
    return [f'Escalas normalizadas automáticamente en la copia; desviación máxima: {deviation:g} m.']


def annotate(request):
    scene = choose_scene(request.get('scene'))
    bpy.context.window.scene = scene
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    controls = request['controls']
    errors = []
    replacements = []
    for key, control in controls.items():
        obj = scene.objects.get(control['target_node'])
        if obj is None:
            errors.append(f'{key}: no existe {control["target_node"]} en {scene.name}')
            continue
        existing_constraint = (request.get('update_existing') and obj.get('control_key') == key
                    and len(obj.constraints) == 1
                    and obj.constraints[0].name in {f'Control: {key}', 'DOF - edit limits here',
                                                   'DOF - lateral opening (metres)'}
                    and obj.constraints[0].type in {'LIMIT_ROTATION', 'LIMIT_LOCATION'})
        existing_driver = False
        if request.get('update_existing') and obj.get('control_key') == key and 'control_definition' in obj:
            try:
                existing_driver = recognized_driver(obj, metadata_definition(obj)[0])
            except (ValueError, TypeError, KeyError):
                pass
        existing = existing_constraint or existing_driver
        if existing:
            # Recognize the previous toolkit control; never remove arbitrary rig constraints.
            try:
                definition(obj)
                replacements.append(obj)
            except ValueError as error:
                errors.append(f'{obj.name}: control existente no válido: {error}')
        if (obj.animation_data and not existing_driver) or ((obj.constraints or 'control_key' in obj) and not existing):
            errors.append(f'{obj.name}: ya tiene constraints, animación o control_key; no se sobrescribe')
        if not existing_driver and any(abs(v) > 1e-6 for v in obj.matrix_basis.to_quaternion().to_euler('XYZ')):
            errors.append(f'{obj.name}: se requiere reposo Euler XYZ a cero; no se deducen compensaciones')
        if any(abs(v) > 1e-6 for v in [*obj.delta_location, *obj.delta_rotation_euler]) or any(abs(v-1) > 1e-6 for v in obj.delta_scale):
            errors.append(f'{obj.name}: transformaciones delta no soportadas')
        if control['space'] == 'global' and not aligned_global(obj):
            errors.append(f'{obj.name}: el control global exige ancestros fijos alineados con el mundo')
        location = rest_position(obj) if existing_driver else obj.location
        if request.get('constraints') and control['transform'] == 'position' and any(abs(v) > 1e-6 for v in location):
            errors.append(f'{obj.name}: traslación requiere un pivote con localización de reposo cero')
    if errors:
        return dict(errors=errors, warnings=[], scene=scene.name)
    for obj in replacements:
        if 'control_definition' in obj:
            old = metadata_definition(obj)[0]
            path, index, _ = native_channel(old)
            rest = rest_position(obj)
            obj.driver_remove(path, index)
            obj.animation_data_clear()
            if old['transform'] == 'position':
                obj.location = rest
        else:
            obj.constraints.remove(obj.constraints[0])
        for attribute in ('control_key', 'control_step_degrees', 'control_step_metres',
                          'control_definition', 'control_definition_version', 'control_value',
                          'control_rest_position', 'control_round_decimals'):
            if attribute in obj:
                del obj[attribute]
    for control in controls.values():
        obj = scene.objects[control['target_node']]
        # glTF import commonly chooses quaternion display even for zero rest.
        obj.rotation_mode = 'XYZ'
        obj.rotation_euler = (0, 0, 0)
    root_name = request.get('root')
    roots = choose_roots(scene, root_name)
    objects = list({obj for root in roots for obj in [root, *root.children_recursive]
                    if obj.name in scene.objects and obj.type not in {'CAMERA', 'LIGHT'}})
    if any(scene.objects[control['target_node']] not in objects for control in controls.values()):
        raise ValueError('Todos los controles deben pertenecer al subárbol raíz seleccionado; no se guarda la copia.')
    warnings = normalize_scales(objects)
    for key, control in controls.items():
        obj = scene.objects[control['target_node']]
        axis, sign = {'x': ('x', 1), 'y': ('z', 1), 'z': ('y', -1)}[control['axis']]
        rotation = control['transform'] == 'rotation'
        low, high = sorted(value * sign for value in (control['min'], control['max']))
        if rotation:
            low, high = math.radians(low), math.radians(high)
        # Editor locks expose only the authored degree of freedom. Constraints
        # still provide evaluated limits; locks alone do not enforce the range.
        obj.lock_scale = (True, True, True)
        obj.lock_rotation = tuple(not rotation or native_axis != axis for native_axis in 'xyz')
        obj.lock_location = tuple(rotation or native_axis != axis for native_axis in 'xyz')
        if request.get('constraints'):
            constraint = obj.constraints.new('LIMIT_ROTATION' if rotation else 'LIMIT_LOCATION')
            constraint.name = f'Control: {key}'
            constraint.owner_space = 'WORLD' if control['space'] == 'global' else 'LOCAL'
            constraint.use_transform_limit = True
            for native_axis in 'xyz':
                if rotation:
                    setattr(constraint, 'use_limit_' + native_axis, True)
                else:
                    setattr(constraint, 'use_min_' + native_axis, True)
                    setattr(constraint, 'use_max_' + native_axis, True)
                setattr(constraint, 'min_' + native_axis, low if native_axis == axis else 0)
                setattr(constraint, 'max_' + native_axis, high if native_axis == axis else 0)
        else:
            create_driver(obj, control, key)
        obj['control_key'] = key
        obj['control_step_degrees' if rotation else 'control_step_metres'] = control['step']
        if 'round_decimals' in control and request.get('constraints'):
            obj['control_round_decimals'] = control['round_decimals']
        regenerated, _ = definition(obj)
        if any(regenerated[field] != control[field] for field in ('target_node', 'transform', 'space', 'axis', 'step')) or any(abs(regenerated[field]-control[field]) > 0.0001 for field in ('min', 'max')):
            raise ValueError(f'{key}: la constraint no reproduce la definición de entrada; no se guarda.')
    # Gallery placement is passthrough data, never a transform of Blender geometry.
    if request.get('presentation'):
        roots[0]['gallery_presentation'] = request['presentation']
    report = process(scene_name=scene.name, root_name=root_name)
    report['warnings'].extend(warnings)
    if report['errors']:
        return report
    path = Path(request['output']) / (request['name'] + '.blend')
    if path.exists():
        raise ValueError('La copia anotada ya existe; no se sobrescribe.')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    report['annotated_blend'] = str(path)
    return report
