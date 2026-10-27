"""Fit only newly quality-supported candidates with the frozen route pipeline.

Geometry is computed once for the union; 15/20 s masks then build separate
paired baseline populations. Historical arrays are copied without alteration.
"""
from pathlib import Path
from collections import Counter
import sys,json,gzip,hashlib,time,importlib.util
R=Path(__file__).resolve().parent;B=R.parent
CODE=B/'vectoring-direction-repair/code'
sys.dont_write_bytecode=True
sys.path[:0]=[str(B/'evaluation-python-deps'),str(CODE)]
import numpy as np
import vectoring_population as population
import vectoring_uncertainty as uncertainty
import vectoring_reference as reference
import vectoring_path as path
from position_timeline import position_grid

read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,obj):Path(p).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf8')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ACTIVE=B/'changi-publication-repo/evaluation/runs/segmented-15km'
SMOOTH=B/'vectoring-15km-star-2026-10-24/population-15km'
OLD_SCREEN=B/'four-scene-vectoring-screen/screening'
OUT=R/'screening';OUT.mkdir(exist_ok=True);(OUT/'references').mkdir(exist_ok=True)
old_manifest=read(OLD_SCREEN/'manifest.json')
for name,h in old_manifest['code_sha256'].items():assert sha(CODE/name)==h,(name,'frozen source changed')
SEGMENTED_SOURCE=B/'evaluation-10s/workspace/evaluation/code/vectoring_path.py'
spec=importlib.util.spec_from_file_location('segmented_source',SEGMENTED_SOURCE)
seg=importlib.util.module_from_spec(spec);sys.modules['segmented_source']=seg;spec.loader.exec_module(seg)
tasks=read(R/'tasks.json');quality_tracks={(t['scene'],t['icao24']):t for t in read(R/'candidate-quality.json')}
quality={}
with gzip.open(R/'point-evidence.jsonl.gz','rt',encoding='utf8') as f:
    for line in f:
        p=json.loads(line);quality.setdefault((p['scene'],p['icao24']),{})[p['source_index']]=p
sources={};originals={};grids={}
for sid in sorted({t['scene'] for t in tasks}):
    with gzip.open(B/'opensky-month-coverage/source-tracks'/(sid+'.json.gz'),'rt',encoding='utf8') as f:
        sources[sid]={t['icao24']:np.asarray(t['source_records'],float) for t in json.load(f)}
    originals[sid]=np.load(OLD_SCREEN/(sid+'-original-background.npz'))
    for a,raw in sources[sid].items():grids[sid,a]=position_grid(raw,sample_s=10)
protected={str(p):sha(p) for folder in [SMOOTH,ACTIVE/'population',OLD_SCREEN/'references'] for p in folder.glob('*') if p.is_file()}
write(OUT/'manifest.json',dict(state='running',status_union_window_s=20,shape_peak_m=15000,legacy_screen_peak_m=5000,
    code_sha256=old_manifest['code_sha256'],segmented_source_sha256=sha(SEGMENTED_SOURCE),policy=read(R/'policy.json'),protected_sources=protected))
uncertainty.STATUS_DISTANCE_S=20.
original_fit=population.fit_track
results=[]
for task in tasks:
    sid,a=task['scene'],task['icao24'];prefix=sid+'-'+a
    dest=OUT/(prefix+'-record.json');npz=OUT/(prefix+'-arrays.npz')
    if dest.exists():
        assert npz.exists();results.append(read(dest));continue
    started=time.monotonic();raw=sources[sid][a];original=np.asarray(originals[sid][a]);grid=grids[sid,a]
    assert quality_tracks[sid,a]['windows']['20']['full_quality_pass']
    captured=[]
    def capture(*args,**kwargs):
        fitted=original_fit(*args,**kwargs);captured.append(fitted)
        np.savez_compressed(OUT/'references'/(prefix+'.npz'),times=fitted.times,epoch=fitted.epoch,
            raw_xy=fitted.raw_xy,fitted_xy=fitted.fitted_xy,radii=fitted.radii,origin=fitted.origin,grid=grid)
        return fitted
    population.fit_track=capture;path.PEAK=5000.
    try:prepared=population.prepare_population({a:original},{a:raw},{a:quality[sid,a]})
    finally:population.fit_track=original_fit
    record=prepared.records[0]
    record.update(scene=sid,quality_windows=quality_tracks[sid,a]['windows'],smooth15_pass=False,segmented15_pass=False,
                  stage15_diagnostics={},stage15_reasons=[],segmented_reasons=[])
    arrays={'baseline':prepared.baseline[a]}
    if record['injectable']:
        for side,q in prepared.injections[a].items():arrays['screen5_'+('left' if side<0 else 'right')]=q
        assert len(captured)==1
        path.PEAK=15000.
        start=(len(original)-60)//2
        ref=reference.maneuver_reference(captured[0],grid,start)
        smooth={}
        for side,name in [(-1,'left'),(1,'right')]:
            detail={}
            try:
                xy=path.generate(ref,side,detail,sample_s=10)
                q=prepared.baseline[a].copy();q[start:start+61,:2]=xy
                assert np.array_equal(q[:,2],original[:,2])
                assert np.array_equal(q[:start],prepared.baseline[a][:start]) and np.array_equal(q[start+61:],prepared.baseline[a][start+61:])
                smooth[name]=q;detail['accepted']=True
            except (path.PathRejected,np.linalg.LinAlgError,FloatingPointError) as exc:
                detail.update(accepted=False,rejection_reason=str(exc));record['stage15_reasons'].append(f'{name}:{exc}')
            record['stage15_diagnostics'][name]=detail
        if len(smooth)==2:
            record['smooth15_pass']=True
            arrays.update({'smooth_'+k:v for k,v in smooth.items()})
            try:
                for side,name in [(-1,'left'),(1,'right')]:
                    xy=seg.generate_segmented(ref,side,peak=15000.,ramp_s=150.,plateau_end_s=450.,blend_s=30.,sample_s=10.)
                    q=prepared.baseline[a].copy();q[start:start+61,:2]=xy
                    assert np.isfinite(q).all() and np.array_equal(q[:,2],original[:,2])
                    arrays['segmented_'+name]=q
                record['segmented15_pass']=True
            except (seg.PathRejected,np.linalg.LinAlgError,FloatingPointError) as exc:
                record['segmented_reasons']=[str(exc)]
    record['paired_injectable']=record['smooth15_pass'] and record['segmented15_pass']
    record['elapsed_s']=time.monotonic()-started
    np.savez_compressed(npz,**arrays);record['arrays_sha256']=sha(npz)
    write(dest,record);results.append(record)
    print(json.dumps(dict(scene=sid,icao24=a,fit=record['fit_success'],reference=record['reference_pass'],screen5=record['injectable'],smooth15=record['smooth15_pass'],segmented15=record['segmented15_pass'],reasons=record['rejection_reasons']+record['stage15_reasons']+record['segmented_reasons'],elapsed_s=record['elapsed_s'])),flush=True)
    write(OUT/'progress.json',dict(completed=len(results),total=len(tasks)))
uncertainty.STATUS_DISTANCE_S=10.;path.PEAK=5000.
# Copy the unchanged original arrays; change only newly quality-supported
# fitted backgrounds and route replacements for each explicitly labelled arm.
comparison=[]
for window in [15,20]:
    folders={shape:R/f'window-{window}s'/shape/'population' for shape in ['smooth','segmented']}
    for folder in folders.values():folder.mkdir(parents=True,exist_ok=True)
    rows_summary=[]
    for sid in sorted(sources):
        old_records=read(ACTIVE/'population'/(sid+'-records.json'))
        byid={t['icao24']:t for t in results if t['scene']==sid}
        with np.load(SMOOTH/(sid+'-population.npz')) as z:smooth={k:z[k] for k in z.files}
        with np.load(ACTIVE/'population'/(sid+'-population.npz')) as z:segmented={k:z[k] for k in z.files}
        assert set(k for k in smooth if k.endswith('_baseline'))==set(k for k in segmented if k.endswith('_baseline'))
        for k in smooth:
            if k.endswith('_baseline'):np.testing.assert_array_equal(smooth[k],segmented[k])
        old_eligible=[r['icao24'] for r in old_records if r['segmented_injectable']]
        eligible=list(old_eligible);changed=[];new_rows=[]
        for old in old_records:
            a=old['icao24'];row=dict(old,sensitivity_window_s=window,screening_origin='cached_10s')
            t=byid.get(a)
            if t and t['quality_windows'][str(window)]['full_quality_pass']:
                row=dict(t,sensitivity_window_s=window,screening_origin='new_quality_window',new_injectable=t['paired_injectable'],segmented_injectable=t['paired_injectable'])
                with np.load(OUT/(sid+'-'+a+'-arrays.npz')) as z:
                    smooth[a+'_baseline']=z['baseline'];segmented[a+'_baseline']=z['baseline']
                    if t['fit_success']:changed.append(a)
                    if t['paired_injectable']:
                        eligible.append(a)
                        for side in ['left','right']:
                            smooth[a+'_'+side]=z['smooth_'+side];segmented[a+'_'+side]=z['segmented_'+side]
            new_rows.append(row)
        for shape,arrays in [('smooth',smooth),('segmented',segmented)]:
            np.savez_compressed(folders[shape]/(sid+'-population.npz'),**arrays)
            write(folders[shape]/(sid+'-records.json'),new_rows)
        row=dict(scene=sid,background=len(old_records),injectable_before=len(old_eligible),injectable_after=len(eligible),injectable=sorted(eligible),
            new_quality=sum(t['scene']==sid and t['quality_windows'][str(window)]['full_quality_pass'] for t in results),
            new_fit_success=len(changed),fitted_baselines_updated=changed,new_injectable=len(eligible)-len(old_eligible))
        rows_summary.append(row);comparison.append(dict(window_s=window,**row))
    for shape,folder in folders.items():write(folder/'summary.json',dict(peak_m=15000.,window_s=window,shape=shape,scenes=rows_summary,
        totals=dict(background=sum(t['background'] for t in rows_summary),injectable_after=sum(t['injectable_after'] for t in rows_summary))))
assert all(sha(p)==h for p,h in protected.items())
write(OUT/'summary.json',dict(state='complete',new_candidates=results,comparison=comparison,
    new_20s_quality=len(results),new_20s_fit_success=sum(r['fit_success'] for r in results),
    new_20s_5km=sum(r['injectable'] for r in results),new_20s_15km=sum(r['paired_injectable'] for r in results),
    rejection_counts=dict(Counter(e for r in results for e in set(r['rejection_reasons']+r['stage15_reasons']+r['segmented_reasons'])))))
m=read(OUT/'manifest.json');m['state']='complete';m['protected_sources_unchanged']=True;write(OUT/'manifest.json',m)
print('SCREENING COMPLETE '+json.dumps(comparison),flush=True)
