"""Native scalar controls, metadata export, rest restoration and mode switching."""
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/blender'))
from annotate_model import annotate
from driver_controls import recognized_driver
from export_model import process
from exchange import verify_pair


def set_value(obj, value):
    obj['control_value'] = float(value)
    obj.update_tag()
    bpy.context.view_layer.update()


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1
bpy.ops.mesh.primitive_cube_add()
mount = bpy.context.object
mount.name = 'Montura'
bpy.ops.mesh.primitive_cube_add(location=(2, 0, 0))
leaf = bpy.context.object
leaf.name = 'Pieza'
leaf.parent = mount
controls = {'azimuth': dict(target_node='Montura', transform='rotation', space='global',
    axis='y', min=-300, max=300, step=1)}
with TemporaryDirectory(prefix='toolkit-drivers-') as directory:
    def apply(name, **options):
        report = annotate(dict(controls=controls, output=directory, name=name, **options))
        assert not report['errors'], report
        return report

    apply('constraints', constraints=True)
    # The original Altaz_C generator used this name before the shared annotator.
    mount.constraints[0].name = 'DOF - edit limits here'
    apply('drivers', update_existing=True)
    mount = bpy.data.objects['Montura']
    assert not mount.constraints and recognized_driver(mount, controls['azimuth'])
    assert mount.id_properties_ui('control_value').as_dict()['step'] == 300
    assert mount.animation_data.drivers[0].driver.is_simple_expression
    for value in (-400, -300, -270, -90, 0, 270, 300, 400):
        set_value(mount, value)
        expected = math.radians(max(-300, min(300, value)))
        assert abs(mount.rotation_euler.z - expected) < 1e-6, (value, mount.rotation_euler[:])
        point = leaf.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation
        assert abs(point.x - 2*math.cos(expected)) < 1e-5
        assert abs(point.y - 2*math.sin(expected)) < 1e-5
    set_value(mount, 270)
    exported = process(output_dir=directory, name='modelo', export_files=True)
    assert not exported['errors'], exported
    assert exported['controls'] == controls
    assert mount['control_value'] == 270
    assert abs(mount.rotation_euler.z-math.radians(270)) < 1e-6
    try:
        process(output_dir=directory, name='modelo', export_files=True)
        raise AssertionError('Expected existing output error')
    except ValueError as error:
        assert 'salida ya existe' in str(error)
    assert mount['control_value'] == 270
    assert abs(mount.rotation_euler.z-math.radians(270)) < 1e-6
    assert not mount.animation_data.drivers[0].mute
    assert verify_pair(Path(directory)/'modelo.glb', Path(directory)/'modelo.yaml')['controls'] == 1
    # A second scene export at zero has identical model bounds to the posed export.
    set_value(mount, 0)
    assert process()['geometry'] == exported['geometry']
    # File save/reopen retains the simple driver with autoexec disabled.
    bpy.ops.wm.open_mainfile(filepath=str(Path(directory)/'drivers.blend'), use_scripts=False)
    mount = bpy.data.objects['Montura']
    assert mount.id_properties_ui('control_value').as_dict()['step'] == 300
    set_value(mount, -270)
    assert abs(mount.rotation_euler.z-math.radians(-270)) < 1e-6
    controls['azimuth']['max'] = 280
    apply('updated', update_existing=True)
    assert len(mount.animation_data.drivers) == 1
    assert mount.id_properties_ui('control_value').as_dict()['max'] == 280
    # Arbitrary expressions must fail preflight and update, not run during export.
    curve = mount.animation_data.drivers[0]
    original = curve.driver.expression
    curve.driver.expression = 'value * 7'
    assert process()['errors']
    assert annotate(dict(controls=controls, output=directory, name='rejected', update_existing=True))['errors']
    curve.driver.expression = original
    mount.update_tag()
    bpy.context.view_layer.update()
    apply('back-to-constraints', constraints=True, update_existing=True)
    assert len(mount.constraints) == 1 and 'control_definition' not in mount
    assert not mount.animation_data
    # Default driver translation uses metres and the glTF Z -> Blender -Y sign.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1
    bpy.ops.mesh.primitive_cube_add()
    slider = bpy.context.object
    slider.name = 'Carro'
    controls = {'avance': dict(target_node='Carro', transform='position', space='local',
        axis='z', min=-1, max=2, step=0.01)}
    apply('translation')
    assert abs(slider.id_properties_ui('control_value').as_dict()['step'] - 1.5) < 1e-6
    set_value(slider, 1.25)
    assert abs(slider.location.y + 1.25) < 1e-6
    translated = process(output_dir=directory, name='carro', export_files=True)
    assert not translated['errors'], translated
    assert translated['geometry']['minimum'] == [-1, -1, -1]
    assert translated['geometry']['maximum'] == [1, 1, 1]
    assert abs(slider.location.y + 1.25) < 1e-6
    assert slider['control_value'] == 1.25
    apply('legacy-shutter-constraint', constraints=True, update_existing=True)
    slider.constraints[0].name = 'DOF - lateral opening (metres)'
    apply('legacy-shutter-driver', update_existing=True)
    assert not slider.constraints and recognized_driver(slider, controls['avance'])
    # A piece's mounted position is not the control's zero offset.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1
    bpy.ops.mesh.primitive_cube_add(location=(2, 3, 4))
    slider = bpy.context.object
    slider.name = 'Carro'
    controls['avance']['round_decimals'] = 4
    presentation = {'translation': [0., 1., 0.], 'rotation_degrees': [90., 0., 180.]}
    apply('offset', presentation=presentation)
    assert list(slider.location) == [2, 3, 4]
    assert list(slider.rotation_euler) == [0, 0, 0]
    assert slider.id_properties_ui('control_value').as_dict()['precision'] == 4
    set_value(slider, 1.25)
    assert abs(slider.location.y - 1.75) < 1e-6
    exported = process(output_dir=directory, name='offset-model', export_files=True)
    assert not exported['errors'], exported
    assert exported['geometry']['minimum'] == [1, 2, 3]
    assert exported['geometry']['maximum'] == [3, 4, 5]
    assert abs(slider.location.y - 1.75) < 1e-6
    assert verify_pair(Path(directory)/'offset-model.glb', Path(directory)/'offset-model.yaml')['controls'] == 1
    apply('offset-updated', update_existing=True)
    assert list(slider.location) == [2, 3, 4]
    assert list(slider['control_rest_position']) == [2, 3, 4]
    assert annotate(dict(controls=controls, output=directory, name='bad-native', constraints=True, update_existing=True))['errors']
print('PASS: default drivers, constraint conversion, scalar limits/multiple turns, hierarchy, persistence, rest export/restore, translation, foreign-driver rejection')
