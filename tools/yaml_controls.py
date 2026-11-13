"""Optional YAML input for annotation; no YAML dependency for normal exports."""
import math
from pathlib import Path


def read_controls(path, model_key=None, *, include_model=False):
    try:
        import yaml
    except ImportError as error:
        raise ValueError('annotate necesita PyYAML en el Python del toolkit. Instala el paquete python3-yaml de tu sistema o configura PYTHON_BIN con un Python que lo tenga. check/export no lo necesitan.') from error

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=True)
            if not isinstance(key, str) or key in result:
                raise ValueError('Las claves YAML deben ser texto y no repetirse.')
            result[key] = loader.construct_object(value_node, deep=True)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    path = Path(path).expanduser().resolve(strict=True)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('El YAML de controles supera 2 MiB.')
    try:
        document = yaml.load(path.read_text(encoding='utf8'), Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise ValueError(f'YAML inválido: {error}') from error
    if not isinstance(document, dict) or set(document) != {'models'} or not isinstance(document['models'], dict):
        raise ValueError('Se esperaba únicamente un bloque models con definiciones de modelos.')
    models = document['models']
    if model_key is None and len(models) == 1:
        model_key = next(iter(models))
    if model_key not in models:
        raise ValueError('Indica --model-key. Modelos del YAML: ' + ', '.join(models))
    model = models[model_key]
    if not isinstance(model, dict) or set(model) - {'rotation_order', 'controls', 'rotation_degrees', 'translation'} or model.get('rotation_order', 'XYZ') != 'XYZ':
        raise ValueError('Sólo se admite rotation_order XYZ, controls, rotation_degrees y translation.')
    pose = {}
    for field in ('rotation_degrees', 'translation'):
        if field not in model:
            continue
        vector = model[field]
        if not isinstance(vector, list) or len(vector) != 3 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in vector):
            raise ValueError(f'{field}: se requieren tres números finitos.')
        pose[field] = vector
    controls = model.get('controls')
    if not isinstance(controls, dict) or not controls:
        raise ValueError('El YAML debe definir algún control.')
    targets = set()
    fields = {'target_node', 'transform', 'space', 'axis', 'min', 'max', 'step'}
    for key, control in controls.items():
        if not key.strip() or not isinstance(control, dict) or not fields <= set(control) or set(control) - fields - {'round_decimals'}:
            raise ValueError(f'{key}: campos de control incompletos o no soportados.')
        if 'round_decimals' in control and (type(control['round_decimals']) is not int or not 0 <= control['round_decimals'] <= 15):
            raise ValueError(f'{key}: round_decimals debe ser un entero entre 0 y 15.')
        target = control['target_node']
        if not isinstance(target, str) or not target or target in targets:
            raise ValueError(f'{key}: se admite un único control por objeto, con target_node no vacío.')
        targets.add(target)
        if control['transform'] not in ('rotation', 'position') or control['space'] not in ('local', 'global') or control['axis'] not in ('x', 'y', 'z'):
            raise ValueError(f'{key}: movimiento/espacio/eje no soportado.')
        values = [control[field] for field in ('min', 'max', 'step')]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
            raise ValueError(f'{key}: límites/paso deben ser números finitos.')
        low, high, step = values
        if not low <= 0 <= high or low >= high or step <= 0:
            raise ValueError(f'{key}: rango debe incluir cero y paso debe ser positivo.')
    return (path, model_key, controls, pose) if include_model else (path, model_key, controls)
