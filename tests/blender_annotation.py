"""Annotation regression on synthetic geometry, no NRT or plugin dependencies."""
import math
from pathlib import Path
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
bpy.ops.mesh.primitive_cube_add()
mount = bpy.context.object
mount.name = 'Montura'
mount.scale = (0.1, 0.1, 0.1)
parent = bpy.data.objects.new('Conjunto', None)
bpy.context.scene.collection.objects.link(parent)
mount.parent = parent
bpy.ops.mesh.primitive_cube_add()
leaf = bpy.context.object
leaf.name = 'Hoja'
leaf.parent = mount
leaf.scale = (2, 2, 2)
bpy.context.view_layer.update()
controls = {
    'azimuth': dict(target_node='Montura', transform='rotation', space='global', axis='y', min=-300, max=300, step=1),
    'hoja': dict(target_node='Hoja', transform='rotation', space='local', axis='z', min=-90, max=30, step=0.5),
}
with TemporaryDirectory(prefix='toolkit-annotation-') as directory:
    report = annotate(dict(constraints=True, controls=controls, output=directory, name='anotado'))
    assert not report['errors'], report
    assert any('automáticamente' in warning for warning in report['warnings']), report
    assert (Path(directory)/'anotado.blend').exists()
    assert mount.constraints[0].owner_space == 'WORLD'
    assert mount.constraints[0].use_transform_limit
    assert abs(mount.constraints[0].max_z-math.radians(300)) < 1e-6
    assert abs(leaf.constraints[0].min_y-math.radians(-30)) < 1e-6
    assert abs(leaf.constraints[0].max_y-math.radians(90)) < 1e-6
    # Reopen to prove constraints/properties are actually persisted in the copy.
    bpy.ops.wm.open_mainfile(filepath=str(Path(directory)/'anotado.blend'), use_scripts=False)
    assert tuple(bpy.data.objects['Montura'].lock_rotation) == (True, True, False)
    assert tuple(bpy.data.objects['Hoja'].lock_rotation) == (True, False, True)
    for name in ('Montura', 'Hoja'):
        assert all(bpy.data.objects[name].lock_location)
        assert all(bpy.data.objects[name].lock_scale)
    exported = process(root_name='Conjunto', output_dir=directory, name='modelo', export_files=True)
    assert not exported['errors'], exported
    assert exported['controls'] == controls
    assert verify_pair(Path(directory)/'modelo.glb', Path(directory)/'modelo.yaml')['controls'] == 2
    failed = annotate(dict(constraints=True, controls=controls, output=directory, name='rejected'))
    assert failed['errors'] and not (Path(directory)/'rejected.blend').exists()
    controls['hoja']['min'] = 0
    updated = annotate(dict(constraints=True, controls=controls, output=directory, name='actualizado', update_existing=True))
    assert not updated['errors'], updated
    assert len(bpy.data.objects['Hoja'].constraints) == 1
    assert updated['controls'] == controls
    assert tuple(bpy.data.objects['Hoja'].lock_rotation) == (True, False, True)
    # A non-toolkit constraint must never be replaced, even with explicit update.
    foreign = bpy.data.objects['Hoja'].constraints.new('COPY_LOCATION')
    rejected = annotate(dict(constraints=True, controls=controls, output=directory, name='ajeno', update_existing=True))
    assert rejected['errors'] and not (Path(directory)/'ajeno.blend').exists()
    assert len(bpy.data.objects['Hoja'].constraints) == 2
    bpy.data.objects['Hoja'].constraints.remove(foreign)
    parent = bpy.data.objects['Conjunto']
    parent.rotation_euler.z = math.radians(20)
    bpy.context.view_layer.update()
    assert any('WORLD' in error for error in process(root_name='Conjunto')['errors'])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1
    bpy.ops.mesh.primitive_cube_add()
    slider = bpy.context.object
    slider.name = 'Carro'
    translated = annotate(dict(constraints=True, controls={'avance': dict(target_node='Carro', transform='position',
        space='local', axis='z', min=-1, max=2, step=0.01)}, output=directory, name='traslacion'))
    assert not translated['errors'], translated
    assert tuple(slider.lock_location) == (True, False, True)
    assert all(slider.lock_rotation) and all(slider.lock_scale)
print('PASS: YAML annotation, world/local axes and signs, scale preservation, persistence, re-export, existing controls and rotated world parent rejection')
