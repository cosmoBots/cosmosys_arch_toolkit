"""Reopen the candidate and verify native metres, export, and readiness to edit."""
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory

import bpy

assert bpy.context.scene.name == 'Observatory'
assert bpy.context.view_layer.objects.active.name == 'DOF_Shutter'
shutter=bpy.data.objects['DOF_Shutter']
assert shutter.parent.name == 'DOF_Dome_Azimuth'
assert shutter.constraints[0].type == 'LIMIT_LOCATION'
assert abs(shutter.location.x)<1e-7
assert shutter.constraints[0].max_x == 3.6 or abs(shutter.constraints[0].max_x-3.6)<1e-6
shutter.location.x=4
bpy.context.view_layer.update()
actual=shutter.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_local.to_translation().x
assert abs(actual-3.6)<1e-6
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'blender'))
from export_model import export
with TemporaryDirectory(prefix='altaz-lateral-export-') as directory:
    controls=export(directory, scene_name='Observatory', root_name='Observatory_Root', name='Altaz_C')
    assert controls['shutter_open']['transform']=='position'
    assert controls['shutter_open']['max']==3.6
    binary=(Path(directory)/'Altaz_C.glb').read_bytes()
    length=struct.unpack_from('<I',binary,12)[0]
    doc=json.loads(binary[20:20+length])
    node=next(n for n in doc['nodes'] if n['name']=='DOF_Shutter')
    assert abs(node.get('translation',[0,0,0])[0])<1e-7, 'Export is not closed at zero'
    assert shutter.location.x==4, 'Inspection position not restored'
print('PASS: candidate reopens with shutter selected; native position clamps 4m to 3.6m; common exporter resets and restores position')
