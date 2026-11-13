"""Automatic normalization, scope and rejection without publishing unsafe blends."""
from pathlib import Path
import hashlib
import subprocess
import sys
from tempfile import TemporaryDirectory
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/blender'))
from annotate_model import annotate


def fixture():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = 'Root'
    return obj


with TemporaryDirectory(prefix='toolkit-scales-') as directory:
    obj = fixture()
    obj.scale = (2, 3, 4)
    obj.hide_select = True
    bpy.context.view_layer.update()
    before = [obj.matrix_world @ v.co for v in obj.data.vertices]
    unrelated = bpy.data.objects.new('Unrelated', None)
    bpy.context.scene.collection.objects.link(unrelated)
    unrelated.scale = (7, 8, 9)
    report = annotate(dict(controls={}, root='Root', output=directory, name='normalized'))
    assert not report['errors'], report
    assert tuple(obj.scale) == (1, 1, 1) and obj.hide_select
    assert tuple(unrelated.scale) == (7, 8, 9), 'Unrelated model changed'
    assert max((obj.matrix_world @ v.co - before[i]).length for i, v in enumerate(obj.data.vertices)) < 1e-5
    second = annotate(dict(controls={}, root='Root', output=directory, name='again'))
    assert not second['errors'] and not any('normalizadas' in w for w in second['warnings'])
    for kind in ('negative', 'zero', 'modifier', 'foreign-driver'):
        obj = fixture()
        obj.scale = (2, 2, 2)
        if kind == 'negative': obj.scale.x = -1
        if kind == 'zero': obj.scale.x = 0
        if kind == 'modifier': obj.modifiers.new('Unapplied', 'BEVEL')
        if kind == 'foreign-driver': obj.driver_add('location', 0)
        try:
            annotate(dict(controls={}, root='Root', output=directory, name=kind))
            raise AssertionError(f'{kind} accepted')
        except ValueError as error:
            assert 'escala' in str(error) or 'normalizar' in str(error), str(error)
        assert not (Path(directory) / f'{kind}.blend').exists(), 'Unsafe output published'
    # Real CLI transaction: a failed normalization must keep the source bytes.
    obj = fixture()
    obj.scale.x = 0
    source = Path(directory) / 'broken.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    controls = Path(directory) / 'controls.yaml'
    controls.write_text('models:\n  broken.glb:\n    controls:\n      turn:\n'
                        '        target_node: Root\n        transform: rotation\n'
                        '        space: local\n        axis: x\n        min: 0\n'
                        '        max: 90\n        step: 1\n')
    command = [str(Path(__file__).resolve().parents[1] / 'toolkit'), 'annotate', str(source),
               '--controls', str(controls), '--root', 'Root', '--output-dir', directory,
               '--blender', bpy.app.binary_path]
    failed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert failed.returncode != 0 and 'escala' in failed.stderr, failed.stdout + failed.stderr
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, 'Failed CLI replaced source'
print('PASS: automatic normalization, geometry, unit-scale no-op, subtree scope, visibility, rejected scales/modifiers/drivers')
