"""Stable locations for topic code and saved study packages.

Historical manifests retain their original paths. Use study_path() for active
code and relocated_path() when reading those manifests. Neither modifies data.
"""
from pathlib import Path
import json
import os
import sys

EVALUATION_ROOT = Path(__file__).resolve().parents[1]
REPO = EVALUATION_ROOT.parent
LEGACY_RUNS = EVALUATION_ROOT / 'runs'
HISTORY_ROOT = EVALUATION_ROOT / 'histry'
ORGANIZATION_MAP = HISTORY_ROOT / 'organization-map.json'

STUDIES = {
    'strict-10s-reference': 'histry/strict-10s-reference',
    'holding-equal-duration': 'holding/controls/holding-equal-duration',
    'holding-equal-duration-old-cutoff': 'holding/controls/holding-equal-duration-old-cutoff',
    'vectoring-20s-repaired': 'vectoring/main/vectoring-20s-repaired',
    'vectoring-certificate-repair': 'vectoring/main/vectoring-certificate-repair',
    'vectoring-time-window-sensitivity': 'vectoring/controls/vectoring-time-window-sensitivity',
    'segmented-15km': 'vectoring/history/segmented-15km',
    'four-scene-vectoring-screen': 'vectoring/history/four-scene-vectoring-screen',
    'four-scene-vectoring-evaluation': 'vectoring/history/four-scene-vectoring-evaluation',
    'vectoring-existing-result-diagnosis': 'vectoring/history/vectoring-existing-result-diagnosis',
    'vectoring-fixed-baseline-scales': 'vectoring/history/vectoring-fixed-baseline-scales',
    'changi-hourly': 'hourly/main/changi-hourly',
    'changi-thresholds': 'hourly/controls/changi-thresholds',
    'changi-n-scaling': 'hourly/history/changi-n-scaling',
    'opensky-30d-no-gate': 'hourly/history/opensky-30d-no-gate',
}

def configure_imports():
    """Permit direct CLI execution and cross-topic shared helpers."""
    for path in [REPO, EVALUATION_ROOT/'code', *[EVALUATION_ROOT/t/'code' for t in ('holding','vectoring','hourly')]]:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

def study_path(name, runs=None):
    """Resolve a named package; explicit external legacy run roots still work."""
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Study name must be a relative package path')
    if runs is not None and Path(runs).resolve() not in (LEGACY_RUNS.resolve(), HISTORY_ROOT, EVALUATION_ROOT):
        return Path(runs) / relative
    key, *rest = relative.parts
    if key not in STUDIES:
        return HISTORY_ROOT / relative
    return EVALUATION_ROOT / STUDIES[key] / Path(*rest)

def relocated_path(relative):
    """Resolve a pre-organization path recorded relative to evaluation/."""
    rel=Path(relative).as_posix()
    data=json.loads(ORGANIZATION_MAP.read_text(encoding='utf-8'))
    if rel in data['moves']:
        return EVALUATION_ROOT/data['moves'][rel]
    for old,new in sorted(data['directory_aliases'].items(), key=lambda item:-len(item[0])):
        if rel==old or rel.startswith(old+'/'):
            return EVALUATION_ROOT/(new+rel[len(old):])
    return EVALUATION_ROOT/relative

def check_output_location(path):
    """Protect topic packages and legacy evidence from output overwrites."""
    path=Path(path).resolve()
    roots=[EVALUATION_ROOT/name for name in ('holding','vectoring','hourly','star','histry','report','runs','archive','code','figures')]
    if path==EVALUATION_ROOT or any(path==r or path.is_relative_to(r) for r in roots):
        raise ValueError('Published evaluation code and evidence are read-only; choose a new external output directory')
    return path

def report_link(target, output_directory):
    """Link a standalone generated report back to an existing source file."""
    target=Path(target).resolve()
    try:
        return os.path.relpath(target, Path(output_directory).resolve()).replace('\\', '/')
    except ValueError:
        return target.as_uri()
