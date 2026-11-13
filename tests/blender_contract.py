"""Native Blender integration; temporary geometry only, no user files touched."""
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/blender'))
from export_model import definition, process
from exchange import verify_pair

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = 'Banco independiente'
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
root = bpy.data.objects.new('Raíz propia', None)
scene.collection.objects.link(root)
pivot = bpy.data.objects.new('Eje arbitrario', None)
scene.collection.objects.link(pivot)
pivot.parent = root
pivot['control_key'] = 'giro: cénit'
pivot.rotation_mode = 'XYZ'
limit = pivot.constraints.new('LIMIT_ROTATION')
limit.owner_space = 'LOCAL'
for axis in 'xyz':
    setattr(limit, 'use_limit_' + axis, True)
limit.min_y, limit.max_y = 0, math.pi / 2
pivot.rotation_euler.y = 0.4
bpy.ops.mesh.primitive_cube_add()
mesh = bpy.context.object
mesh.parent = pivot
mesh.location = (0, 0, 2)

with TemporaryDirectory(prefix='toolkit-contract-') as directory:
    report = process(output_dir=directory, name='independiente', export_files=True)
    assert not report['errors'], report
    assert report['controls']['giro: cénit']['axis'] == 'z'
    assert report['controls']['giro: cénit']['min'] == -90
    assert report['controls']['giro: cénit']['max'] == 0
    assert abs(pivot.rotation_euler.y - 0.4) < 1e-6, 'Pose not restored'
    assert 'cosmosys_controls' not in pivot and 'cosmosys_model' not in root
    assert verify_pair(Path(directory)/'independiente.glb', Path(directory)/'independiente.yaml')['controls'] == 1
    try:
        process(output_dir=directory, name='independiente', export_files=True)
        raise AssertionError('Output overwrite accepted')
    except ValueError as error:
        assert 'ya existe' in str(error)
    pivot['control_step_degrees'] = 0
    report = process()
    assert any('paso' in error for error in report['errors'])
    del pivot['control_step_degrees']
    mesh['control_key'] = pivot['control_key']
    assert any('único' in error for error in process()['errors'])
    del mesh['control_key']
    mesh.scale.x = 2
    assert any('escala' in error for error in process()['errors'])
    mesh.scale.x = 1
    bpy.data.scenes['csysArch'].unit_settings.scale_length = 0.01
    assert any('metros' in error for error in process()['errors'])
    bpy.data.scenes['csysArch'].unit_settings.scale_length = 1
    limit.use_limit_x = False
    assert any('tres ejes' in error for error in process()['errors'])
    pivot.constraints.remove(limit)
    del pivot['control_key']
    static = process(output_dir=directory, name='estático', export_files=True)
    assert not static['errors'] and any('estático' in warning for warning in static['warnings'])
    pivot['control_key'] = 'traslación'
    location = pivot.constraints.new('LIMIT_LOCATION')
    location.owner_space = 'LOCAL'
    for axis in 'xyz':
        setattr(location, 'use_min_' + axis, True)
        setattr(location, 'use_max_' + axis, True)
    location.max_z = 3
    result, axis = definition(pivot)
    assert result['axis'] == 'y' and result['max'] == 3 and axis == 'z'
    # Other user scenes must not displace the toolkit default.
    bpy.data.scenes.new('Otra escena')
    assert process()['scene'] == 'csysArch'
    try:
        process(scene_name='Escena inexistente')
        raise AssertionError('Missing explicit scene accepted')
    except ValueError as error:
        assert '--scene' in str(error)
print('PASS: generic names, axes/sign, static model, limits, scale, units, pose restoration, no overwrite and scene selection')
