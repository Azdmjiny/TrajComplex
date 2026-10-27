"""Read-only structural audit; no model, optimizer, D or plotting imports."""
from pathlib import Path
import ast
import hashlib
import json
import re
from urllib.parse import unquote
from evaluation_layout import EVALUATION_ROOT as ROOT, STUDIES, ORGANIZATION_MAP

def audit():
    manifest=json.loads(ORGANIZATION_MAP.read_text(encoding='utf8'))
    errors=[]
    for row in manifest['immutable_files']:
        p=ROOT/row['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            errors.append('Changed/missing evidence: '+row['path'])
    for row in manifest.get('configuration_changes',[]):
        p=ROOT/row['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            errors.append('Changed/missing recorded configuration: '+row['path'])
    star=json.loads((ROOT/'star/history/local-source-map.json').read_text(encoding='utf8'))
    for row in star['copies']:
        p=ROOT/row['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            errors.append('Changed/missing STAR snapshot: '+row['path'])
    for name,path in STUDIES.items():
        if not (ROOT/path).is_dir(): errors.append('Missing study: '+name)
    links=0
    for p in ROOT.rglob('*.md'):
        # This archive is an immutable historical snapshot, including its old links.
        if 'legacy-before-workflow-integration' in p.parts: continue
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
            if '://' in target or target.startswith(('#','mailto:')): continue
            value=unquote(target.strip('<>').split('#')[0])
            if not value: continue
            if not (p.parent/value).exists():
                errors.append(f'Broken link: {p.relative_to(ROOT)} -> {target}')
            links+=1
    syntax=0
    for directory in ('code','holding/code','vectoring/code','hourly/code'):
        for p in (ROOT/directory).glob('*.py'):
            try: ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
            except SyntaxError as exc: errors.append(str(exc))
            syntax+=1
    return dict(ok=not errors,errors=errors,immutable_files_checked=len(manifest['immutable_files']),
                star_snapshots_checked=len(star['copies']),local_links_checked=links,
                active_python_files_checked=syntax,experiments_run=0)

if __name__=='__main__':
    result=audit()
    print(json.dumps(result,indent=2,ensure_ascii=True))
    raise SystemExit(0 if result['ok'] else 1)
