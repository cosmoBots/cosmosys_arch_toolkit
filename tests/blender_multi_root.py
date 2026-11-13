"""Multiple scene roots need no artificial container or extra imported item."""
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/blender'))
from annotate_model import annotate
from export_model import process
from exchange import verify_pair

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1
for name, x in [('Building', -3), ('Telescope', 3)]:
    bpy.ops.mesh.primitive_cube_add()
    bpy.context.object.name = name
    bpy.context.object.location.x = x
controls = {'azimuth': dict(target_node='Telescope', transform='rotation', space='local',
                           axis='y', min=-300, max=300, step=1)}
with TemporaryDirectory(prefix='toolkit-roots-') as directory:
    report = annotate(dict(controls=controls, output=directory, name='multi'))
    assert not report['errors'], report
    assert set(report['roots']) == {'Building', 'Telescope'} and report['root'] is None
    assert len(bpy.data.objects) == 2, 'Annotation created a synthetic root'
    report = process(output_dir=directory, name='multi', export_files=True)
    assert not report['errors'], report
    assert verify_pair(Path(directory)/'multi.glb', Path(directory)/'multi.yaml')['controls'] == 1
    raw = (Path(directory)/'multi.glb').read_bytes()
    size = struct.unpack_from('<I', raw, 12)[0]
    document = json.loads(raw[20:20+size])
    nodes = document['nodes']
    assert len(nodes) == 2
    assert {nodes[i]['name'] for i in document['scenes'][0]['nodes']} == {'Building', 'Telescope'}
    assert sum('cosmosys_model' in node.get('extras', {}) for node in nodes) == 1
    one = process(root_name='Building', output_dir=directory, name='one', export_files=True)
    assert not one['errors'] and one['objects'] == 1
print('PASS: multiple roots, no synthetic container, shared contract, controls and explicit subtree export')
