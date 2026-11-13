"""Run with python3 -m unittest discover -s tests -v from toolkit root."""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cli
from exchange import verify_pair, yaml_text
from yaml_controls import read_controls


class WorkspaceTest(unittest.TestCase):
    def test_yaml_annotation_input(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML sólo es necesario para annotate')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'controls.yaml'
            controls = {'giro': dict(target_node='Eje', transform='rotation', space='global', axis='y', min=-300, max=300, step=1)}
            path.write_text(yaml_text('nombre-antiguo.glb', controls))
            _, model, parsed = read_controls(path)
            self.assertEqual(model, 'nombre-antiguo.glb')
            self.assertEqual(parsed, controls)
            controls['giro']['round_decimals'] = 4
            pose = {'translation': [0, 1, 0], 'rotation_degrees': [90, 0, 180]}
            path.write_text(yaml_text('modelo.glb', controls, pose))
            self.assertEqual(read_controls(path, include_model=True)[2:], (controls, pose))
            controls['giro']['round_decimals'] = -1
            path.write_text(yaml_text('modelo.glb', controls))
            with self.assertRaisesRegex(ValueError, 'round_decimals'):
                read_controls(path)
            del controls['giro']['round_decimals']
            path.write_text('models: {}\nmodels: {}\n')
            with self.assertRaisesRegex(ValueError, 'repetirse'):
                read_controls(path)
            controls['giro']['space'] = 'other'
            path.write_text(yaml_text('modelo.glb', controls))
            with self.assertRaisesRegex(ValueError, 'espacio'):
                read_controls(path)

    def test_names(self):
        for value in ('', '.', '..', '../bad', 'a/b', 'a\\b', '\x00'):
            with self.assertRaises(ValueError):
                cli.safe_name(value)
        self.assertEqual(cli.safe_name('Mi modelo'), 'Mi modelo')

    def test_fixed_stage_layout(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'TOOLKIT_MODELOS_DIR': directory, 'TOOLKIT_OUTPUT_DIR': ''}):
            original = Path(directory) / 'original.blend'
            original.write_bytes(b'source')
            cli.init_model(argparse.Namespace(name='demo', from_file=str(original)))
            source = Path(directory) / 'demo/1_blender/demo.blend'
            self.assertEqual(source.read_bytes(), b'source')
            first, second = cli.allocate_run(source), cli.allocate_run(source)
            self.assertEqual(first, Path(directory) / 'demo/2_export')
            self.assertEqual(first, second)
            self.assertEqual(cli.allocate_run(source, action='annotate'), source.parent)
            self.assertTrue((source.parent.parent / '0_import').is_dir())
            with self.assertRaises(FileExistsError):
                cli.init_model(argparse.Namespace(name='demo', from_file=str(original)))
            with patch.dict(os.environ, {'TOOLKIT_OUTPUT_DIR': str(Path(directory) / 'results')}):
                self.assertEqual(cli.allocate_run(source), Path(directory) / 'results/demo/2_export')

    def test_missing_blender_is_actionable(self):
        with self.assertRaisesRegex(ValueError, 'BLENDER_BIN'):
            cli.find_blender('/missing/blender')

    def test_annotation_replaces_working_blend_only_after_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'TOOLKIT_MODELOS_DIR': directory, 'TOOLKIT_OUTPUT_DIR': ''}):
            stage = Path(directory) / 'demo/1_blender'
            stage.mkdir(parents=True)
            source = stage / 'demo.blend'
            source.write_bytes(b'original')
            controls = stage.parent / '0_import/demo.yaml'
            controls.parent.mkdir()
            controls.write_text(yaml_text('demo.glb', {'giro': dict(target_node='Eje', transform='rotation', space='local', axis='x', min=-90, max=90, step=1)}))
            args = argparse.Namespace(action='annotate', source=str(source), name=None,
                blender=None, controls=str(controls), model_key=None,
                output_dir=None, scene=None, root=None, timeout=10)
            fail = False

            def backend(command, *, timeout, log):
                job = json.loads(Path(command[-1]).read_text())
                self.assertEqual(source.read_bytes(), b'annotated' if fail else b'original')
                output = Path(job['output']) / 'demo.blend'
                output.write_bytes(b'broken' if fail else b'annotated')
                Path(job['response']).write_text(json.dumps(dict(errors=['rejected'] if fail else [], warnings=[], annotated_blend=str(output))))
                Path(log).write_text('test')
                return 0

            with patch.object(cli, 'find_blender', return_value=('/blender', 'test')), patch.object(cli, 'bounded', side_effect=backend):
                self.assertEqual(cli.run_model(args), 0)
                self.assertEqual(source.read_bytes(), b'annotated')
                report = json.loads((stage / 'annotate-informe.json').read_text())
                self.assertEqual(report['annotated_blend'], str(source))
                fail = True
                self.assertEqual(cli.run_model(args), 1)
                self.assertEqual(source.read_bytes(), b'annotated')
                self.assertEqual(json.loads((stage / 'annotate-informe.json').read_text())['status'], 'failed')
            self.assertEqual(sorted(path.name for path in stage.iterdir()), ['annotate-conversion.log', 'annotate-informe.json', 'demo.blend'])

    def test_timeout_reaps_process(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(subprocess.TimeoutExpired):
                cli.bounded([sys.executable, '-c', 'import time; time.sleep(30)'],
                            timeout=0.05, log=Path(directory) / 'log')

    def test_canonical_pair_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            glb, yaml = Path(directory) / 'modelo.glb', Path(directory) / 'modelo.yaml'
            control = dict(target_node='Pivote', transform='rotation', space='local', axis='z', min=-90, max=0, step=1)
            controls = {'giro: cénit': control}
            document = {'asset': {'version': '2.0'}, 'scenes': [{'nodes': [0]}], 'nodes': [dict(name='Pivote', extras={
                'cosmosys_model': {'schema': 'cosmosys.cad.controls', 'version': 1}, 'cosmosys_controls': controls})]}
            data = json.dumps(document).encode()
            data += b' ' * (-len(data) % 4)
            glb.write_bytes(struct.pack('<4s4I', b'glTF', 2, 20+len(data), len(data), 0x4E4F534A) + data)
            yaml.write_text(yaml_text(glb.name, controls), encoding='utf8')
            self.assertEqual(verify_pair(glb, yaml)['controls'], 1)
            yaml.write_text('models: {}', encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'YAML'):
                verify_pair(glb, yaml)
            glb.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'truncado'):
                verify_pair(glb, yaml)

    def test_env_is_literal_and_environment_wins(self):
        # Exercise a temporary launcher copy, never create/overwrite the user's .env.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'toolkit').write_bytes((ROOT / 'toolkit').read_bytes())
            (root / 'tools').mkdir()
            (root / 'tools/cli.py').write_text('import os; print(os.environ["BLENDER_BIN"])')
            sentinel = root / 'must-not-exist'
            value = '$(touch ' + str(sentinel) + ')'
            (root / '.env').write_text(f'PYTHON_BIN="{sys.executable}"\nBLENDER_BIN={value}\n')
            environment = dict(os.environ)
            environment.pop('BLENDER_BIN', None)
            environment.pop('PYTHON_BIN', None)
            command = ['bash', str(root / 'toolkit')]
            result = subprocess.run(command, env=environment, text=True, capture_output=True, check=True, cwd='/tmp')
            self.assertEqual(result.stdout.strip(), value)
            self.assertFalse(sentinel.exists())
            environment['BLENDER_BIN'] = '/explicit/path'
            self.assertEqual(subprocess.check_output(command, env=environment, text=True).strip(), '/explicit/path')
            (root / '.env').write_text('EVIL=anything\n')
            self.assertNotEqual(subprocess.run(command, env=environment, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
