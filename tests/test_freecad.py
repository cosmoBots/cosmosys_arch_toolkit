"""Optional integration test. Run with FREECAD_BIN pointing to FreeCAD 1.1+."""
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from cli import find_freecad
from exchange import read_glb_json, sha256


@unittest.skipUnless(os.environ.get('FREECAD_BIN'), 'Define FREECAD_BIN para probar FreeCAD real.')
class FreeCADTest(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.directory = Path(workspace.name)
        self.env = dict(os.environ, APPIMAGE_EXTRACT_AND_RUN='1',
                        TOOLKIT_MODELOS_DIR=str(self.directory / 'models'),
                        TOOLKIT_OUTPUT_DIR='', XDG_CACHE_HOME=str(self.directory / 'cache'),
                        XDG_CONFIG_HOME=str(self.directory / 'config'),
                        XDG_DATA_HOME=str(self.directory / 'data'))
        with patch.dict(os.environ, self.env):
            executable = find_freecad(None)
        command = [executable]
        if Path(executable).name == 'AppRun' or executable.lower().endswith('.appimage'):
            command.append('freecadcmd')
        program = f'''
import FreeCAD as App
import Part
import Import
doc = App.newDocument("Native")
root = doc.addObject("App::Part", "Assembly")
root.Placement.Base = App.Vector(1000, 0, 2000)
pivot = root.newObject("App::Part", "Pivot")
pivot.Placement.Base = App.Vector(10, 200, 30)
piece = pivot.newObject("Part::Feature", "Piece")
piece.Shape = Part.makeBox(10, 20, 30)
piece.Placement.Base = App.Vector(20, 30, 40)
piece.Placement.Rotation = App.Rotation(App.Vector(0, 0, 1), 90)
second = doc.addObject("Part::Feature", "Second")
second.Shape = Part.makeBox(10, 20, 30)
doc.recompute()
doc.saveAs({str(self.directory / 'native.FCStd')!r})
Import.export([root, second], {str(self.directory / 'native.step')!r})
'''
        result = subprocess.run([*command, '--console', '--safe-mode'],
                                input=f'exec({program!r})\n', env=self.env, text=True,
                                capture_output=True, timeout=120, check=True)
        self.assertTrue((self.directory / 'native.step').is_file(), result.stderr)

    def toolkit(self, *args, success=True):
        result = subprocess.run([sys.executable, str(ROOT / 'tools/cli.py'), *map(str, args)],
                                env=self.env, text=True, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return result

    def test_freecad_path_with_step_and_gltf_roundtrip(self):
        project = self.directory / 'models' / 'demo'
        source = project / '1_FreeCAD' / 'demo.FCStd'
        self.toolkit('init', 'demo', '--from', self.directory / 'native.FCStd')
        original = sha256(source)
        yaml = self.directory / 'controls.yaml'
        yaml.write_text('''models:
  demo.glb:
    controls:
      turn: {target_node: Pivot, transform: rotation, space: local, axis: y, min: -10, max: 20, step: 0.1}
''')
        self.toolkit('annotate', source, '--controls', yaml)
        self.assertEqual(sha256(source), original)
        self.toolkit('check', source)
        self.toolkit('export', source)
        output = project / '2_export'
        self.toolkit('verify', output)
        glb = output / 'demo.glb'
        document = read_glb_json(glb)
        self.assertEqual([document['nodes'][i]['name'] for i in document['scenes'][0]['nodes']],
                         ['Assembly', 'Second'])
        assembly, pivot, piece, second = document['nodes']
        self.assertEqual(assembly['children'], [1])
        self.assertEqual(pivot['children'], [2])
        self.assertEqual(assembly['translation'], [1, 2, 0])
        self.assertEqual(pivot['translation'], [0.01, 0.03, -0.2])
        self.assertEqual(piece['translation'], [0.02, 0.04, -0.03])
        self.assertAlmostEqual(piece['rotation'][1], 2 ** -0.5)
        self.assertEqual(pivot['extras']['cosmosys_controls']['turn']['axis'], 'y')
        self.assertNotIn('mesh', assembly)
        self.assertNotIn('mesh', pivot)
        self.assertEqual(len(document['meshes']), 2)
        self.assertEqual((piece['mesh'], second['mesh']), (0, 1))
        position = document['accessors'][document['meshes'][0]['primitives'][0]['attributes']['POSITION']]
        for actual, expected in zip(position['max'], [0.01, 0.03, 0]):
            self.assertAlmostEqual(actual, expected)

        for file, options in ((self.directory / 'native.step', ()), (glb, ('--backend', 'freecad'))):
            imported = self.directory / file.suffix[1:]
            self.toolkit('import', file, *options, '--output-dir', imported)
            report = json.loads((imported / 'import-informe.json').read_text())
            self.assertEqual(report['geometry']['triangles'], 24)
            with ZipFile(imported / f'{file.stem}.FCStd') as archive:
                model = ElementTree.fromstring(archive.read('Document.xml'))
                gui = ElementTree.fromstring(archive.read('GuiDocument.xml'))
            visible = {provider.get('name') for provider in gui.findall('./ViewProviderData/ViewProvider')
                       if provider.find('./Properties/Property[@name="Visibility"]/Bool').get('value') == 'true'}
            geometry = {obj.get('name') for obj in model.findall('./Objects/Object')
                        if obj.get('type') in ('App::Part', 'Part::Feature', 'Mesh::Feature')}
            self.assertTrue(geometry)
            self.assertLessEqual(geometry, visible)
            self.assertIsNotNone(gui.find('./Camera'))

        scaled = self.directory / 'scaled.gltf'
        binary = glb.read_bytes()
        json_size = struct.unpack_from('<I', binary, 12)[0]
        (scaled.parent / 'geometry.bin').write_bytes(binary[28 + json_size:])
        document['buffers'][0]['uri'] = 'geometry.bin'
        document['nodes'][0]['scale'] = [2, 3, 4]
        scaled.write_text(json.dumps(document))
        scaled_dir = self.directory / 'scaled'
        self.toolkit('import', scaled, '--backend', 'freecad', '--output-dir', scaled_dir)
        self.toolkit('export', scaled_dir / 'scaled.FCStd', '--output-dir', scaled_dir)
        baked = read_glb_json(scaled_dir / 'scaled.glb')
        self.assertEqual(baked['nodes'][1]['translation'], [0.02, 0.09, -0.8])
        self.assertEqual(baked['nodes'][2]['translation'], [0.04, 0.12, -0.12])
        position = baked['accessors'][baked['meshes'][0]['primitives'][0]['attributes']['POSITION']]
        for actual, expected in zip(position['max'], [0.04, 0.09, 0]):
            self.assertAlmostEqual(actual, expected)
        self.assertTrue(all('scale' not in node for node in baked['nodes']))

        document['nodes'][0]['scale'] = [-1, 1, 1]
        scaled.write_text(json.dumps(document))
        result = self.toolkit('import', scaled, '--backend', 'freecad', success=False)
        self.assertIn('Assembly: Las escalas glTF deben ser finitas y positivas.', result.stderr)

        yaml.write_text(yaml.read_text().replace('target_node: Pivot', 'target_node: Missing'))
        annotation = source.with_suffix('.controls.json')
        annotation_hash = sha256(annotation)
        self.toolkit('annotate', source, '--controls', yaml, '--update-existing', success=False)
        self.assertEqual(sha256(annotation), annotation_hash)
