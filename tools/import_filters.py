"""CSV import policies, shared by the CLI and the bounded Blender process."""
import csv
from pathlib import Path
import re


def read_filters(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        rows = csv.reader(stream)
        if next(rows, None) != ['search', 'pattern', 'action']:
            raise ValueError('El CSV debe empezar por search,pattern,action.')
        rules = []
        for line, row in enumerate(rows, 2):
            if not row:
                continue
            if len(row) != 3:
                raise ValueError(f'CSV fila {line}: se esperan tres columnas.')
            search, pattern, action = row
            if search not in ('text', 'regex') or action not in ('include', 'exclude', 'atomic'):
                raise ValueError(f'CSV fila {line}: search text/regex; action include/exclude/atomic.')
            if not pattern or len(pattern) > 256:
                raise ValueError(f'CSV fila {line}: patrón vacío o mayor de 256 caracteres.')
            if search == 'regex':
                try:
                    re.compile(pattern, re.IGNORECASE)
                except re.error as error:
                    raise ValueError(f'CSV fila {line}: expresión regular inválida: {error}') from error
            rules.append(dict(search=search, pattern=pattern, action=action, line=line))
    return rules


def classify(names, rules):
    """Return each name's last matching policy and every rule's direct matches."""
    modes = ['include'] * len(names)
    evidence = []
    for rule in rules:
        regex = re.compile(rule['pattern'], re.IGNORECASE) if rule['search'] == 'regex' else None
        matches = [i for i, name in enumerate(names)
                   if (regex.search(name) if regex else rule['pattern'].lower() in name.lower())]
        for index in matches:
            modes[index] = rule['action']
        evidence.append(dict(rule, matches=matches))
    return modes, evidence
