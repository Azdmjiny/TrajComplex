"""Screen the approved 26 candidates with unchanged production functions."""
from pathlib import Path
import gzip,hashlib,json,sys,time
R=Path(__file__).resolve().parent;B=R.parent
CODE=B/'vectoring-direction-repair/code';OUT=R/'screening'
sys.dont_write_bytecode=True
sys.path[:0]=[str(B/'evaluation-python-deps'),str(CODE)]
import numpy as np
import scipy,clarabel
import vectoring_population as population
import vectoring_path as path
from vectoring_inputs import llh_to_enu
from position_timeline import position_grid,resample_positions
from trajectory_quality import quality_reasons
from screen_vectoring_candidates import load_quality
from vectoring_reference import FIT_MODEL,DIRECTION_CERTIFICATE

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False),encoding='utf8')

proposal=read(B/'coverage-population-review/proposed-first-batch.json')
quality_summary=read(B/'coverage-nic-supplement/summary.json')
old_manifest=read(B/'vectoring-direction-repair/screening/manifest.json')
assert quality_summary['state']=='complete' and quality_summary['candidates_full_quality']==26
assert len(proposal['scenes'])==4
assert all(sha(CODE/name)==h for name,h in old_manifest['code_sha256'].items())
assert (FIT_MODEL,DIRECTION_CERTIFICATE,path.MODEL,path.NUMERICS)==tuple(old_manifest[k] for k in ['fit_model','direction_certificate','route_model','route_numerics'])
quality_file=B/'coverage-nic-supplement/point-evidence.jsonl.gz'
quality=load_quality(quality_file)
assert len(quality)==26 and sum(len(q) for q in quality.values())==2106
approved=set(quality)
assert {s for s,a in approved}=={s['scene'] for s in proposal['scenes']}
protected={str(p):sha(p) for folder in [B/'coverage-nic-supplement',B/'coverage-population-review',B/'vectoring-direction-repair',B/'vectoring-peak-feedback/screening']
           for p in folder.rglob('*') if p.is_file() and '__pycache__' not in str(p)}
for s in proposal['scenes']:
    p=B/'opensky-month-coverage/source-tracks'/(s['scene']+'.json.gz');protected[str(p)]=sha(p)
write(R/'before-hashes.json',protected)
OUT.mkdir(exist_ok=False);(OUT/'references').mkdir()
manifest=dict(state='running',scenes=[s['scene'] for s in proposal['scenes']],
    approved_candidates=[dict(scene=s,icao24=a) for s,a in sorted(approved)],
    input_sample_s=10,altitude_field='baroaltitude',
    code_directory=str(CODE),code_sha256=old_manifest['code_sha256'],driver_sha256=sha(Path(__file__)),
    source_paths={'quality':str(quality_file),'proposal':str(B/'coverage-population-review/proposed-first-batch.json')},
    source_sha256={'quality':sha(quality_file),'proposal':sha(B/'coverage-population-review/proposed-first-batch.json')},
    source_track_sha256={s['scene']:sha(B/'opensky-month-coverage/source-tracks'/(s['scene']+'.json.gz')) for s in proposal['scenes']},
    baseline_policy=old_manifest['baseline_policy'],
    candidate_scope='Only the 26 previously approved complete-quality candidates; all other basic-QC tracks retained as raw backgrounds',
    fit_model=FIT_MODEL,direction_certificate=DIRECTION_CERTIFICATE,route_model=path.MODEL,route_numerics=path.NUMERICS,
    thresholds=old_manifest['thresholds'],numerical=old_manifest['numerical'],
    versions=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,clarabel=clarabel.__version__),
    restrictions=dict(network_queries=0,scope_expansion=0,threshold_changes=0,missing_values_filled=0,
                      encoder_calls=0,D_calls=0,correlation_calls=0,holding_runs=0),
    source_loading='Reconstruct the same strict-10s grid from cached original basic-QC source rows; no new interpolation rule or archive selection')
assert manifest['versions']==old_manifest['versions']
write(OUT/'manifest.json',manifest)
all_records=[];scene_results=[];start_time=time.monotonic()
original_fit=population.fit_track
for info in proposal['scenes']:
    scene=info['scene'];source_file=B/'opensky-month-coverage/source-tracks'/(scene+'.json.gz')
    with gzip.open(source_file,'rt',encoding='utf8') as f:cached=json.load(f)
    sources={};tracks={};grids={}
    for t in cached:
        a=t['icao24'];raw=np.asarray(t['source_records'],float)
        grid=position_grid(raw,sample_s=10);enu=llh_to_enu(raw[:,1],raw[:,2],raw[:,3])
        assert not quality_reasons(raw[:,:4],enu,500.,position_times=raw[:,4])
        assert len(grid)==t['grid_points'] and len(grid)>=30 and np.all(np.diff(grid)==10)
        sample=resample_positions(raw,enu,grid);assert np.isfinite(sample).all()
        sources[a]=raw;tracks[a]=sample;grids[a]=grid
    assert len(tracks)==info['baseline_basic_qc']
    wanted={a for s,a in approved if s==scene}
    assert wanted<=set(tracks)
    # Save the exact fitted knots for future diagnosis. This observer delegates
    # unchanged arguments/results to the original solver and changes no decision.
    def save_fit(xy,times,radii,diagnostics=None):
        found=[a for a in wanted if np.array_equal(sources[a][:,4],times)]
        assert len(found)==1,'Ambiguous diagnostic source identity'
        a=found[0]
        np.testing.assert_array_equal(xy,llh_to_enu(sources[a][:,1],sources[a][:,2],sources[a][:,3])[:,:2])
        fitted=original_fit(xy,times,radii,diagnostics)
        np.savez_compressed(OUT/'references'/(scene+'-'+a+'.npz'),times=fitted.times,epoch=fitted.epoch,
            raw_xy=fitted.raw_xy,fitted_xy=fitted.fitted_xy,radii=fitted.radii,origin=fitted.origin,grid=grids[a])
        return fitted
    population.fit_track=save_fit
    def progress(r):
        if r['fit_attempted']:
            assert r['icao24'] in wanted
            print(json.dumps(dict(scene=scene,icao24=r['icao24'],fit=r['fit_success'],reference=r['reference_pass'],
                                  injectable=r['injectable'],reasons=r['rejection_reasons'])),flush=True)
    try:
        prepared=population.prepare_population(tracks,sources,{a:quality[(scene,a)] for a in wanted},progress=progress)
    finally:population.fit_track=original_fit
    rows=[];arrays={};original_arrays={}
    for row in prepared.records:
        a=row['icao24'];row=dict(row,scene=scene,in_approved_candidate_scope=a in wanted)
        assert row['fit_attempted']==(a in wanted)
        if a not in wanted:
            assert not row['fit_success'] and not row['injectable']
            np.testing.assert_array_equal(prepared.baseline[a],tracks[a])
        rows.append(row);arrays[a+'_baseline']=prepared.baseline[a];original_arrays[a]=tracks[a]
        for side,q in prepared.injections.get(a,{}).items():arrays[a+('_left' if side<0 else '_right')]=q
    np.savez_compressed(OUT/(scene+'-population.npz'),**arrays)
    np.savez_compressed(OUT/(scene+'-original-background.npz'),**original_arrays)
    write(OUT/(scene+'-records.json'),rows)
    result=dict(scene=scene,local_time=info['local_time'],approved_candidates=len(wanted),
                **population.summarize(rows),population_sha256=sha(OUT/(scene+'-population.npz')))
    scene_results.append(result);all_records.extend(rows)
    write(OUT/'summary.json',dict(state='running',scenes=scene_results,totals=population.summarize(all_records)))
    print(json.dumps(result),flush=True)
assert sum(r['fit_attempted'] for r in all_records)==26
assert len(all_records)==157
assert all(sha(p)==h for p,h in protected.items())
forbidden=[m for m in sys.modules if m=='torch' or m.startswith(('Encoder.','complexity.'))]
assert not forbidden
manifest.update(state='complete',elapsed_s=time.monotonic()-start_time,forbidden_imports=forbidden)
write(OUT/'manifest.json',manifest)
write(OUT/'summary.json',dict(state='complete',scenes=scene_results,totals=population.summarize(all_records),restrictions=manifest['restrictions']))
print('SCREENING COMPLETE '+json.dumps(population.summarize(all_records)),flush=True)
