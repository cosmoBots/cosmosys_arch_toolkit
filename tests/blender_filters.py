"""Run with Blender --background --python tests/blender_filters.py."""
from pathlib import Path
import sys
import tempfile
import json
import struct

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/blender'))
from import_model import import_model, filter_objects
from export_model import process

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1
parent = bpy.data.objects.new('Kit', None)
bpy.context.collection.objects.link(parent)
for name in ['Visible', 'DIN912-M3X12', 'Child', 'Keep']:
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = name
    if name == 'Visible':
        obj.parent = parent
    if name == 'Child':
        obj.parent = bpy.data.objects['DIN912-M3X12']
rules = [dict(search='regex', pattern='^DIN[0-9]', action='exclude'),
         dict(search='text', pattern='Kit', action='atomic'),
         dict(search='text', pattern='Child', action='include')]
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory)
    assert not process(output_dir=output, name='source', export_files=True)['errors']
    request = dict(source=str(output/'source.glb'), output=directory, name='filtered', scale=1, filters=rules)
    report = import_model(dict(request, preflight=True))
    assert set(report['filtering']['excluded']) == {'DIN912-M3X12', 'Child'}, report
    assert not (output/'filtered.blend').exists()
    bpy.data.objects['DIN912-M3X12']['control_key'] = 'protected'
    blocked = filter_objects(bpy.context.scene, rules, preflight=True)
    assert blocked['errors'] and 'controles anotados' in blocked['errors'][0]
    assert 'DIN912-M3X12' in bpy.data.objects, 'Preflight changed geometry'
    report = import_model(request)
    assert report['meshes'] == 2, report
    assert 'Child' not in bpy.data.objects
    assert bpy.data.objects['Kit']['cosmosys_import']['mode'] == 'atomic'
    assert len(bpy.data.meshes) == 2
    assert not process(output_dir=output, name='result', export_files=True)['errors']
    data = (output/'result.glb').read_bytes()
    length = struct.unpack_from('<I', data, 12)[0]
    document = json.loads(data[20:20+length])
    kit = next(node for node in document['nodes'] if node.get('name') == 'Kit')
    assert kit['extras']['cosmosys_import'] == dict(version=1, mode='atomic')
    assert kit['children'], 'Atomic geometry was removed'
    imported_again = import_model(dict(request, source=str(output/'result.glb'), name='again', filters=[]))
    assert not imported_again['errors']
    assert bpy.data.objects['Kit']['cosmosys_import']['mode'] == 'atomic', 'Reimport lost preference'
    try:
        import_model(dict(request, name='empty', filters=[dict(search='regex', pattern='.', action='exclude')]))
        raise AssertionError('Empty model accepted')
    except ValueError as error:
        assert 'todas las superficies' in str(error)
    assert not (output/'empty.blend').exists()
print('PASS: subtree exclusion, orphan geometry cleanup, preflight, atomic GLB extras, empty rejection')
