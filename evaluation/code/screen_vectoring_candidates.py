"""Screen original scenes and save frozen populations, without Encoder or D.

Usage: python screen_vectoring_candidates.py --data-zip ... --quality ...
       --output NEW_DIRECTORY
Quality accepts the retained reception audit's JSONL.gz, or JSON rows.
An existing output directory is refused so old results cannot be overwritten.
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
import zipfile
from pathlib import Path
import numpy as np
import scipy
import clarabel
from vectoring_inputs import read_scene
from vectoring_population import prepare_population, summarize, array_hash
from vectoring_reference import FIT_MODEL, DIRECTION_CERTIFICATE
import vectoring_path as path

SCENES = ['2026-09-01T01Z','2026-09-04T08Z','2026-09-07T10Z','2026-09-10T06Z',
          '2026-09-12T15Z','2026-09-15T06Z','2026-09-18T00Z','2026-09-20T04Z',
          '2026-09-23T10Z','2026-09-25T23Z','2026-09-28T07Z','2026-09-30T15Z']


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, data): p.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf8')


def load_quality(filename):
    lookup = {}
    if str(filename).endswith('.jsonl.gz'):
        with gzip.open(filename,'rt',encoding='utf8') as f:
            rows = [json.loads(line) for line in f]
    else: rows = json.loads(Path(filename).read_text(encoding='utf8'))
    for r in rows:
        key = (r['scene'],r['icao24'])
        dest = lookup.setdefault(key,{})
        if r['source_index'] in dest: raise ValueError('duplicate quality identity')
        dest[r['source_index']] = r
    return lookup


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-zip',required=True,type=Path)
    ap.add_argument('--quality',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args = ap.parse_args()
    quality = load_quality(args.quality)
    args.output.mkdir(parents=True,exist_ok=False)
    code = Path(__file__).resolve().parent
    code_names = ['screen_vectoring_candidates.py','vectoring_population.py','vectoring_reference.py',
                  'vectoring_inputs.py','vectoring_path.py','vectoring_certification.py','run_vectoring_eval.py',
                  'vectoring_uncertainty.py','trajectory_quality.py','position_timeline.py']
    manifest = dict(state='running',scenes=SCENES,input_sample_s=10,altitude_field='baroaltitude',
                    source_sha256={'data_zip':sha(args.data_zip),'quality':sha(args.quality)},
                    source_paths={'data_zip':str(args.data_zip.resolve()),'quality':str(args.quality.resolve())},
                    code_sha256={name:sha(code/name) for name in code_names},
                    fit_model=FIT_MODEL,direction_certificate=DIRECTION_CERTIFICATE,
                    route_model=path.MODEL,route_numerics=path.NUMERICS,
                    baseline_policy='basic-QC fixed members; failed fit raw background; successful fit frozen before route checks',
                    quality_scope='all real source points for length-qualified fit candidates; no metadata requirement for raw backgrounds',
                    thresholds=dict(horizontal_m_s=500,vertical_m_s=100,position_age_s=15,source_gap_s=20,
                                    status_each_side_s=10,offset_m=5000,duration_s=600,direction_deg=10,
                                    speed_retention=.5,longitudinal_m_s2=2,lateral_bank_proxy_deg=35),
                    numerical=dict(position_m=path.POSITION_TOL,speed_m_s=path.SPEED_TOL,
                                   acceleration_m_s2=path.ACCELERATION_TOL,heading_deg=float(np.rad2deg(path.HEADING_TOL)),
                                   reference_maxiter=200,reference_tol=1e-8,route_maxiter=path.SOLVER_MAXITER,
                                   verify_nodes=path.MAX_VERIFY_NODES),
                    versions=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,clarabel=clarabel.__version__),
                    restrictions=dict(encoder_calls=0,D_calls=0,correlation_calls=0,threshold_changes=0,missing_values_filled=0))
    write(args.output/'manifest.json',manifest)
    all_records = []; scenes = []; start_time = time.time()
    with zipfile.ZipFile(args.data_zip) as archive:
        for scene in SCENES:
            member = next(n for n in archive.namelist() if n==scene+'.csv.gz' or n.endswith('/'+scene+'.csv.gz'))
            sources = {}; basic_audit = []
            tracks = read_scene(archive,member,max_horizontal_speed=500.,audit=basic_audit,vectoring_source=sources)
            def progress(r):
                if r['fit_attempted']:
                    print(json.dumps(dict(scene=scene,icao24=r['icao24'],fit=r['fit_success'],
                                          reference=r['reference_pass'],injectable=r['injectable'],reasons=r['rejection_reasons'])),flush=True)
            population = prepare_population(tracks,sources,
                {a:quality.get((scene,a),{}) for a in tracks},progress=progress)
            arrays = {}; rows = []
            for r in population.records:
                r = dict(r,scene=scene); rows.append(r)
                a = r['icao24']; arrays[a+'_baseline'] = population.baseline[a]
                for side,q in population.injections.get(a,{}).items():
                    arrays[a+('_left' if side<0 else '_right')] = q
            np.savez_compressed(args.output/(scene+'-population.npz'),**arrays)
            write(args.output/(scene+'-records.json'),rows)
            write(args.output/(scene+'-basic-qc.json'),basic_audit)
            report = dict(scene=scene,**summarize(rows),population_sha256=sha(args.output/(scene+'-population.npz')))
            scenes.append(report); all_records.extend(rows)
            write(args.output/'summary.json',dict(state='running',scenes=scenes,totals=summarize(all_records)))
            print(json.dumps(report),flush=True)
    # Hard guard against accidental loading of inference or complexity modules.
    forbidden = [m for m in sys.modules if m=='torch' or m.startswith(('Encoder.','complexity.'))]
    if forbidden: raise RuntimeError('Forbidden evaluation import: '+str(forbidden))
    manifest.update(state='complete',elapsed_s=time.time()-start_time,forbidden_imports=forbidden)
    write(args.output/'manifest.json',manifest)
    write(args.output/'summary.json',dict(state='complete',scenes=scenes,totals=summarize(all_records),
                                        restrictions=manifest['restrictions']))
    print('SCREENING COMPLETE '+json.dumps(summarize(all_records)),flush=True)


if __name__=='__main__': main()
