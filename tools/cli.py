"""Local workspace CLI. Standard library only; Blender runs in a separate process."""
import sys

if sys.version_info < (3, 10):
    print('Se necesita Python 3.10 o posterior. Configura PYTHON_BIN=/ruta/a/python3.', file=sys.stderr)
    sys.exit(1)

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile

from exchange import sha256, verify_pair

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'tools/blender/run_job.py'


def configured_directory(key, default=None):
    value = os.environ.get(key)
    if not value:
        return default
    path = Path(value).expanduser()
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def models_directory():
    return configured_directory('TOOLKIT_MODELOS_DIR', ROOT / 'modelos')


def bounded(command, *, timeout, log):
    """Bound/reap the process group even on timeout or interruption."""
    with Path(log).open('w', encoding='utf8') as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                   start_new_session=(os.name == 'posix'))
        try:
            return process.wait(timeout=timeout)
        except BaseException:
            try:
                if os.name == 'posix':
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    if os.name == 'posix':
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass
                process.wait()
            raise


def find_blender(explicit=None):
    chosen = explicit or os.environ.get('BLENDER_BIN')
    candidates = [chosen] if chosen else [shutil.which('blender'), *sorted(Path.home().glob('soft/blender*/blender'), reverse=True)]
    for candidate in candidates:
        if not candidate:
            continue
        candidate = Path(candidate).expanduser()
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            continue
        try:
            version = subprocess.run([str(candidate), '--version'], capture_output=True, text=True, timeout=10, check=True).stdout.splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError) as error:
            raise ValueError(f'No se puede ejecutar Blender: {candidate}: {error}') from error
        match = re.search(r'Blender (\d+)\.(\d+)', version)
        if not match or tuple(map(int, match.groups())) < (4, 5):
            raise ValueError(f'{version}: se necesita Blender 4.5 o posterior. Configura --blender o BLENDER_BIN.')
        return str(candidate.resolve()), version
    raise ValueError('No encuentro Blender 4.5+. Instálalo desde blender.org o indica --blender /ruta/blender, BLENDER_BIN o añádelo al PATH. No se instala nada automáticamente.')


def safe_name(value):
    if not value or value in ('.', '..') or '/' in value or '\\' in value or '\x00' in value:
        raise ValueError('El nombre debe ser un único nombre de fichero/carpeta, sin rutas.')
    return value


def source_file(value):
    source = Path(value).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != '.blend':
        raise ValueError('La entrada debe ser un fichero .blend guardado.')
    return source


def interchange_file(value):
    source = Path(value).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in {'.glb', '.gltf', '.obj', '.stl', '.ply', '.fbx'}:
        raise ValueError('Entrada admitida: GLB/glTF, OBJ, STL, PLY o FBX. Para .blend usa check/annotate/export.')
    return source


def allocate_run(source, output_dir=None, action='export'):
    try:
        relative = source.relative_to(models_directory())
        project = relative.parts[0] if len(relative.parts) > 1 else source.stem
    except ValueError:
        project = source.stem
    project = re.sub(r'[^\w.-]+', '_', project).strip('.') or 'modelo'
    configured_output = configured_directory('TOOLKIT_OUTPUT_DIR')
    stage = '1_blender' if action in ('import', 'annotate') else '2_export'
    parent = (Path(output_dir).expanduser().resolve() if output_dir else
              configured_output / project / stage if configured_output else models_directory() / project / stage)
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def write_report(path, report):
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf8')


def blender_command(executable, request):
    return [executable, '--background', '--factory-startup', '--disable-autoexec', '-noaudio',
            '--python-exit-code', '1', '--python', str(BACKEND), '--', str(request)]


def doctor(args):
    executable, version = find_blender(args.blender)
    print(f'Python: {sys.version.split()[0]} ({sys.executable})\nBlender: {version} ({executable})', flush=True)
    print(f'Modelos: {models_directory()}\nResultados: {configured_directory("TOOLKIT_OUTPUT_DIR") or "<modelo>/1_blender y 2_export"}', flush=True)
    print('PyYAML (sólo annotate): ' + ('disponible' if importlib.util.find_spec('yaml') else 'no disponible; instala python3-yaml o ajusta PYTHON_BIN'), flush=True)
    with tempfile.TemporaryDirectory(prefix='arch-toolkit-doctor-') as directory:
        request = Path(directory) / 'request.json'
        response = Path(directory) / 'response.json'
        write_report(request, {'action': 'doctor', 'response': str(response)})
        log = Path(directory) / 'doctor.log'
        result = bounded(blender_command(executable, request), timeout=args.timeout, log=log)
        if result != 0 or not response.exists():
            raise ValueError('No se pudo comprobar Blender/glTF:\n' + log.read_text(encoding='utf8')[-3000:])
        report = json.loads(response.read_text(encoding='utf8'))
        if report['errors']:
            raise ValueError('\n'.join(report['errors']))
    print('OK: exportador glTF disponible. No se necesitan pip, Ruby, Node ni Redmine para check/export/verify.')
    return 0


def init_model(args):
    project = models_directory() / safe_name(args.name)
    source = source_file(args.from_file) if args.from_file else None
    project.parent.mkdir(parents=True, exist_ok=True)
    project.mkdir(exist_ok=False)
    for stage in ('0_import', '1_blender', '2_export'):
        (project / stage).mkdir()
    if source:
        shutil.copy2(source, project / '1_blender' / (args.name + '.blend'))
    print(f'Proyecto: {project}\nEtapas: 0_import → 1_blender → 2_export')
    print('Conserva texturas y dependencias del modelo junto a la fuente; no se copian automáticamente.')
    return 0


def run_model(args):
    source = interchange_file(args.source) if args.action == 'import' else source_file(args.source)
    name = safe_name(args.name or source.stem)
    executable, version = find_blender(args.blender)
    annotation = None
    if args.action == 'annotate':
        from yaml_controls import read_controls
        yaml_path, model_key, controls, presentation = read_controls(args.controls, args.model_key, include_model=True)
        annotation = dict(controls=controls, model_key=model_key,
                          update_existing=getattr(args, 'update_existing', False),
                          constraints=getattr(args, 'constraints', False), presentation=presentation)
    destination = allocate_run(source, args.output_dir, args.action)
    # Work privately until validation completes, including when annotating the input
    # Blender in place. A failed run must not replace the user's working model.
    workspace = tempfile.TemporaryDirectory(prefix='.toolkit-', dir=destination)
    run = Path(workspace.name)
    report_path = run / 'informe.json'
    report = {'schema': 'cosmosys.arch.toolkit.report', 'version': 1, 'action': args.action,
              'status': 'running', 'source': str(source), 'source_sha256': sha256(source),
              'blender': {'path': executable, 'version': version}, 'errors': [], 'warnings': [],
              'scene': args.scene, 'root': args.root, 'output_name': name,
              'exporter_sha256': sha256(ROOT / 'tools/blender/export_model.py')}
    if annotation:
        report['input_yaml'] = str(yaml_path)
        report['input_yaml_sha256'] = sha256(yaml_path)
        report['input_model_key'] = model_key
    write_report(report_path, report)
    request = run / '.request.json'
    response = run / '.response.json'
    job = {'action': args.action, 'source': str(source), 'scene': args.scene,
           'root': args.root, 'name': name, 'output': str(run), 'response': str(response)}
    job.update(annotation or {})
    if args.action == 'import':
        job['scale'] = args.scale
    write_report(request, job)
    print(f'Destino: {destination} (se sustituyen los resultados anteriores)', flush=True)
    try:
        status = bounded(blender_command(executable, request), timeout=args.timeout, log=run / 'conversion.log')
        if response.exists():
            report.update(json.loads(response.read_text(encoding='utf8')))
        if status != 0 or not response.exists():
            report['errors'].append(f'Blender terminó con código {status}. Consulta {args.action}-conversion.log.')
        if sha256(source) != report['source_sha256']:
            report['errors'].append('La fuente cambió durante la ejecución; repite el proceso.')
        if annotation and sha256(yaml_path) != report['input_yaml_sha256']:
            report['errors'].append('El YAML cambió durante la ejecución; repite el proceso.')
        if not report['errors'] and args.action == 'export':
            report['verification'] = verify_pair(run / f'{name}.glb', run / f'{name}.yaml')
        if not report['errors'] and args.action == 'annotate':
            report['annotated_blend_sha256'] = sha256(run / f'{name}.blend')
        if not report['errors'] and args.action == 'import':
            report['imported_blend_sha256'] = sha256(run / f'{name}.blend')
    except subprocess.TimeoutExpired:
        report['errors'].append(f'Tiempo máximo de {args.timeout}s agotado; proceso detenido.')
    except KeyboardInterrupt:
        report['errors'].append('Operación cancelada; proceso detenido.')
    except (OSError, ValueError, KeyError) as error:
        report['errors'].append(str(error))
    report['status'] = 'failed' if report['errors'] else 'ok'
    for key in ('annotated_blend', 'imported_blend'):
        if key in report:
            report[key] = str(destination / (name + '.blend'))
    write_report(report_path, report)
    report_name = 'informe.json' if args.action == 'export' else f'{args.action}-informe.json'
    if report['status'] == 'ok':
        suffixes = { 'export': ('.glb', '.yaml'), 'import': ('.blend',), 'annotate': ('.blend',), 'check': () }
        for suffix in suffixes[args.action]:
            (run / (name + suffix)).replace(destination / (name + suffix))
    for filename, target in (('informe.json', report_name), ('conversion.log', f'{args.action}-conversion.log')):
        if (run / filename).exists():
            (run / filename).replace(destination / target)
    workspace.cleanup()
    for warning in report['warnings']:
        print(f'Aviso: {warning}')
    for error in report['errors']:
        print(f'Error: {error}', file=sys.stderr)
    print(f'{report["status"].upper()}: {destination / report_name}')
    return 1 if report['errors'] else 0


def verify_run(args):
    run = Path(args.directory).expanduser().resolve(strict=True)
    report = json.loads((run / 'informe.json').read_text(encoding='utf8'))
    if report.get('action') != 'export' or report.get('status') != 'ok':
        raise ValueError('La carpeta no corresponde a una exportación terminada correctamente.')
    name = safe_name(report['output_name'])
    verified = verify_pair(run / f'{name}.glb', run / f'{name}.yaml')
    if verified != report.get('verification'):
        raise ValueError('Los resultados difieren de los hashes o del inventario guardados.')
    print(f'OK: {verified["nodes"]} nodos; {verified["controls"]} controles; GLB/YAML y hashes coinciden.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Architecture Toolkit: entorno local de modelos Blender.')
    commands = parser.add_subparsers(dest='action', required=True)
    diagnosis = commands.add_parser('doctor', help='Localizar dependencias y comprobar glTF.')
    diagnosis.set_defaults(handler=doctor)
    new = commands.add_parser('init', help='Crear un cajón privado para un modelo.')
    new.add_argument('name')
    new.add_argument('--from', dest='from_file', help='Copiar un .blend, sin cambiar el original.')
    new.set_defaults(handler=init_model)
    for action in ('check', 'export', 'annotate', 'import'):
        command = commands.add_parser(action, help={'check': 'Validar', 'export': 'Validar y exportar GLB/YAML.', 'annotate': 'Anotar controles desde YAML: drivers por defecto, --constraints opcional.', 'import': 'Importar un modelo de intercambio a un .blend nuevo.'}[action])
        command.add_argument('source', help='Ruta al modelo de entrada.')
        command.add_argument('--scene', help='Escena explícita; por defecto csysArch (se crea con todos los objetos si falta).')
        command.add_argument('--root', help='Limitar a un objeto raíz sin padre; por defecto se procesan todas las raíces con mallas de la escena.')
        command.add_argument('--name', help='Nombre base de salida; por defecto, nombre del .blend.')
        command.add_argument('--output-dir', help='Carpeta destino alternativa; sustituye los resultados anteriores, sin histórico.')
        command.set_defaults(handler=run_model)
        if action == 'annotate':
            command.add_argument('--constraints', action='store_true', help='Crear constraints nativas en vez de controles con driver (por defecto).')
            command.add_argument('--update-existing', action='store_true', help='Actualizar o convertir controles del toolkit con la misma clave/objeto; rechaza rigs ajenos.')
            command.add_argument('--controls', required=True, help='YAML existente de controles glTF.')
            command.add_argument('--model-key', help='Clave dentro de models (obligatoria si hay varias).')
        if action == 'import':
            command.add_argument('--scale', type=float, default=1, help='Factor de escala de importación (positivo, defecto 1).')
    verify = commands.add_parser('verify', help='Comprobar una carpeta de exportación del toolkit.')
    verify.add_argument('directory')
    verify.set_defaults(handler=verify_run)
    for command in (diagnosis, *[commands.choices[action] for action in ('check', 'export', 'annotate', 'import')]):
        command.add_argument('--blender', help='Ruta al ejecutable; también BLENDER_BIN, PATH o ~/soft/blender*/blender.')
        command.add_argument('--timeout', type=int, default=120, help='Plazo máximo en segundos (1..3600; defecto 120).')
    args = parser.parse_args(argv)
    if hasattr(args, 'timeout') and not 1 <= args.timeout <= 3600:
        parser.error('--timeout debe estar entre 1 y 3600 segundos.')
    if hasattr(args, 'scale') and (not math.isfinite(args.scale) or args.scale <= 0):
        parser.error('--scale debe ser finito y positivo.')
    try:
        return args.handler(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Cancelado.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
