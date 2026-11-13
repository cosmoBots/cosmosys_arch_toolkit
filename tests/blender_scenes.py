"""Toolkit scene membership is created once, then controlled by the user."""
from pathlib import Path
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/blender'))
from export_model import choose_scene

bpy.ops.wm.read_factory_settings(use_empty=True)
original = bpy.context.scene
original.name = 'User scene'
original.unit_settings.system = 'METRIC'
original.unit_settings.scale_length = 1
obj = bpy.data.objects.new('Shared', None)
original.collection.objects.link(obj)
obj['control_value'] = 0.0
curve = obj.driver_add('rotation_euler', 0)
curve.driver.expression = '0.0'
other = bpy.data.scenes.new('Variant')
extra = bpy.data.objects.new('Other variant', None)
other.collection.objects.link(extra)
scene = choose_scene(None)
assert scene.name == 'csysArch'
assert set(scene.objects) == {obj, extra}
assert original.objects.get(obj.name) == obj and other.objects.get(extra.name) == extra
assert scene.objects[obj.name].animation_data.drivers[0] == curve
assert scene.unit_settings.system == 'METRIC' and scene.unit_settings.scale_length == 1
scene.collection.objects.unlink(extra)
later = bpy.data.objects.new('Added by user later', None)
original.collection.objects.link(later)
assert choose_scene(None) == scene
assert extra.name not in scene.objects and later.name not in scene.objects
assert choose_scene('Variant') == other
print('PASS: shared objects/drivers, preserved scenes, copied units, no membership resync, explicit scene')
