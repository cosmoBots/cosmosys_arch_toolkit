"""Trusted subprocess entry point; input .blend text blocks are not executed."""
import json
from pathlib import Path
import sys
import traceback

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_model import gltf_available, process

request = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf8'))
report = {'errors': [], 'warnings': []}
try:
    if request['action'] == 'doctor':
        gltf_available()
    elif request['action'] == 'import':
        from import_model import import_model
        report = import_model(request)
    else:
        bpy.ops.wm.open_mainfile(filepath=request['source'], load_ui=False, use_scripts=False)
        if request['action'] == 'annotate':
            from annotate_model import annotate
            report = annotate(request)
        else:
            report = process(scene_name=request['scene'], root_name=request['root'],
                             output_dir=request['output'], name=request['name'],
                             export_files=request['action'] == 'export')
except Exception as error:
    report['errors'].append(str(error))
    traceback.print_exc()
Path(request['response']).write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf8')
