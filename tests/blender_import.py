"""Interchange import regression: generated fixtures only, no external models."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/blender'))
from export_model import process
from import_model import import_model

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1
bpy.ops.mesh.primitive_cube_add()
bpy.context.object.name = 'Cube_Import_Test'
with TemporaryDirectory(prefix='toolkit-import-') as directory:
    output = Path(directory)
    report = process(output_dir=output, name='source', export_files=True)
    assert not report['errors'], report
    source = output/'source.glb'
    original = source.read_bytes()
    imported = import_model(dict(source=str(source), output=directory, name='imported', scale=1))
    assert not imported['errors'] and imported['meshes'] == 1
    assert source.read_bytes() == original
    assert (output/'imported.blend').exists()
    try:
        import_model(dict(source=str(source), output=directory, name='imported', scale=1))
        raise AssertionError('Existing output overwritten')
    except ValueError as error:
        assert 'existe' in str(error)
    fixture = output/'triangle.obj'
    fixture.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
    obj = import_model(dict(source=str(fixture), output=directory, name='obj', scale=0.001))
    assert obj['warnings'] and 'Import_Scale' not in bpy.data.objects
    assert all(item.scale.x < 0.002 for item in bpy.context.scene.objects if item.parent is None)
    fixture = output/'triangle.stl'
    fixture.write_text('solid test\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid test\n')
    stl = import_model(dict(source=str(fixture), output=directory, name='stl', scale=1))
    assert stl['meshes'] == 1
    fixture = output/'triangle.ply'
    fixture.write_text('ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nelement face 1\nproperty list uchar int vertex_indices\nend_header\n0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n')
    ply = import_model(dict(source=str(fixture), output=directory, name='ply', scale=1))
    assert ply['meshes'] == 1
print('PASS: GLB, OBJ, STL, PLY imports, unit warning, scaling, unchanged input and no overwrite')
