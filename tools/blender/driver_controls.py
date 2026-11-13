"""Explicit authoring metadata and a narrowly recognized scalar preview driver."""
import math


def native_channel(control):
    axis, sign = {'x': ('x', 1), 'y': ('z', 1), 'z': ('y', -1)}[control['axis']]
    rotation = control['transform'] == 'rotation'
    return ('rotation_euler' if rotation else 'location', 'xyz'.index(axis),
            sign * (math.pi / 180 if rotation else 1))


def metadata_definition(obj):
    raw = obj.get('control_definition')
    if obj.get('control_definition_version') != 1 or not hasattr(raw, 'keys'):
        raise ValueError('control_definition v1 no válido')
    control = dict(raw)
    fields = {'target_node', 'transform', 'space', 'axis', 'min', 'max', 'step'}
    if not fields <= set(control) or set(control) - fields - {'round_decimals'} or control['target_node'] != obj.name:
        raise ValueError('control_definition incompleto o de otro objeto')
    if 'round_decimals' in control and (type(control['round_decimals']) is not int or not 0 <= control['round_decimals'] <= 15):
        raise ValueError('round_decimals debe ser entero entre 0 y 15')
    if control['transform'] not in ('rotation', 'position') or control['space'] not in ('local', 'global') or control['axis'] not in ('x', 'y', 'z'):
        raise ValueError('movimiento/espacio/eje de control_definition no soportado')
    if not all(isinstance(control[key], (int, float)) and not isinstance(control[key], bool)
               and math.isfinite(control[key]) for key in ('min', 'max', 'step')):
        raise ValueError('límites/paso de control_definition deben ser finitos')
    if not control['min'] <= 0 <= control['max'] or control['min'] >= control['max'] or control['step'] <= 0:
        raise ValueError('control_definition requiere rango con cero y paso positivo')
    if obj.constraints or obj.rotation_mode != 'XYZ':
        raise ValueError('control_definition exige Euler XYZ y ninguna constraint')
    if any(abs(v) > 1e-6 for v in [*obj.delta_location, *obj.delta_rotation_euler]) or any(abs(v-1) > 1e-6 for v in obj.delta_scale):
        raise ValueError('transformaciones delta no soportadas')
    _, index, _ = native_channel(control)
    if any(abs(v) > 1e-6 for i, v in enumerate(obj.rotation_euler)
           if control['transform'] != 'rotation' or i != index):
        raise ValueError('rotaciones ajenas al eje de control no soportadas')
    if control['transform'] == 'position':
        rest = rest_position(obj)
        if any(abs(v-rest[i]) > 1e-6 for i, v in enumerate(obj.location) if i != index):
            raise ValueError('traslaciones ajenas al eje de control no soportadas')
    if control['space'] == 'global':
        ancestor = obj.parent
        while ancestor:
            if ancestor.get('control_key') is not None or ancestor.constraints or ancestor.animation_data or any(abs(v) > 1e-6 for v in ancestor.matrix_world.to_euler('XYZ')):
                raise ValueError('WORLD requiere ancestros fijos alineados con el mundo')
            ancestor = ancestor.parent
        if control['transform'] == 'position':
            rest = obj.matrix_world.translation.copy()
            rest[index] -= obj.location[index]
            if any(abs(v) > 1e-6 for v in rest):
                raise ValueError('WORLD Location requiere reposo en el origen mundial')
    return control, 'xyz'[index]


def rest_position(obj):
    rest = list(obj.get('control_rest_position', (0, 0, 0)))
    if len(rest) != 3 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in rest):
        raise ValueError('control_rest_position no válido')
    return rest


def expression(control, *, offset=False):
    return f'min(max(value, lower), upper) * {native_channel(control)[2]!r}' + (' + rest' if offset else '')


def recognized_driver(obj, control):
    """No action/NLA, extra drivers, foreign targets or arbitrary expressions."""
    animation = obj.animation_data
    value = obj.get('control_value')
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return False
    if not animation or animation.action or animation.nla_tracks or len(animation.drivers) != 1:
        return False
    curve = animation.drivers[0]
    path, index, _ = native_channel(control)
    driver = curve.driver
    if curve.data_path != path or curve.array_index != index or curve.mute or curve.modifiers:
        return False
    offset = control['transform'] == 'position' and 'control_rest_position' in obj
    if driver.type != 'SCRIPTED' or driver.use_self or driver.expression != expression(control, offset=offset):
        return False
    expected = {'value': '["control_value"]', 'lower': '["control_definition"]["min"]',
                'upper': '["control_definition"]["max"]'}
    if offset:
        rest_position(obj)
        expected['rest'] = f'["control_rest_position"][{index}]'
    if len(driver.variables) != len(expected):
        return False
    for variable in driver.variables:
        if variable.name not in expected or variable.type != 'SINGLE_PROP':
            return False
        target = variable.targets[0]
        if target.id != obj or target.data_path != expected.pop(variable.name):
            return False
    return True


def create_driver(obj, control, key):
    obj['control_definition_version'] = 1
    obj['control_definition'] = control
    obj['control_value'] = 0.0
    offset = control['transform'] == 'position'
    if offset:
        obj['control_rest_position'] = list(obj.location)
    # Blender's numeric drag step is expressed in hundredths. Scale the UI
    # sensitivity with travel, independently of the exported sampling step.
    drag_step = 100 * max(control['step'], (control['max'] - control['min']) / 200)
    obj.id_properties_ui('control_value').update(min=control['min'], max=control['max'],
        soft_min=control['min'], soft_max=control['max'], default=0.0,
        step=drag_step,
        precision=min(control.get('round_decimals', 3), 6),
        description=f'{key}: ' + ('grados glTF' if control['transform'] == 'rotation' else 'metros glTF'))
    path, index, _ = native_channel(control)
    curve = obj.driver_add(path, index)
    for modifier in list(curve.modifiers):
        curve.modifiers.remove(modifier)
    driver = curve.driver
    driver.type = 'SCRIPTED'
    sources = [('value', '["control_value"]'), ('lower', '["control_definition"]["min"]'),
               ('upper', '["control_definition"]["max"]')]
    if offset:
        sources.append(('rest', f'["control_rest_position"][{index}]'))
    for name, source in sources:
        variable = driver.variables.new()
        variable.name = name
        variable.type = 'SINGLE_PROP'
        variable.targets[0].id = obj
        variable.targets[0].data_path = source
    driver.expression = expression(control, offset=offset)
    obj.update_tag()
