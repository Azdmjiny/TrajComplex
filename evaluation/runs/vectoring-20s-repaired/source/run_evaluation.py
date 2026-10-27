"""Frozen 20 s before/after comparison; full ranges, both existing shapes.

Only the screened 3c6709 intervention is added. Baselines, old interventions,
master assignments, Encoder, radii and D rules are unchanged. No route solving.
"""
from pathlib import Path
from dataclasses import asdict
from collections import Counter
import sys,json,hashlib,shutil
R=Path(__file__).resolve().parent;B=R.parent
OLD=B/'vectoring-time-window-sensitivity-2026-10-27'
REPAIR=B/'vectoring-certificate-repair-2026-10-27'
sys.dont_write_bytecode=True
sys.path[:0]=[str(B/'evaluation-python-deps'),str(B/'encoder-10s/source'),str(B/'evaluation-10s/workspace')]
import numpy as np
import torch
from scipy.spatial.distance import pdist
from scipy.stats import spearmanr
from trajectory_encoder.inference import FrozenEncoder
from complexity.calculator import ComplexityConfig,estimate_complexity

read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf8')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
canonical=lambda v:json.dumps(v,sort_keys=True,allow_nan=False)
def summarize(trials):
    curves=[]
    for t in trials:
        good=[d for d in t['dose_curve'] if d['status']=='ok' and d['dimension'] is not None and np.isfinite(d['dimension'])]
        reason=None;rho=None
        if len(good)<5:reason='fewer_than_five_valid_doses'
        elif np.ptp([d['dimension'] for d in good])==0:reason='constant_D'
        else:rho=float(spearmanr([d['vectoring_aircraft'] for d in good],[d['dimension'] for d in good]).statistic)
        curves.append(dict(scene=t['scene_id'],replicate=t['replicate'],rho=rho,reason=reason,valid=len(good),total=len(t['dose_curve'])))
    def stats(rows):
        vals=[r['rho'] for r in rows if r['rho'] is not None]
        return dict(estimable=len(vals),positive=sum(v>0 for v in vals),negative=sum(v<0 for v in vals),zero=sum(v==0 for v in vals),
            median=float(np.median(vals)) if vals else None,valid_D=sum(r['valid'] for r in rows),attempted_D=sum(r['total'] for r in rows))
    return dict(curves=curves,scenes=[dict(scene=s,**stats([r for r in curves if r['scene']==s])) for s in sorted({r['scene'] for r in curves})],all=stats(curves))

assert not (R/'run-manifest.json').exists(),'Refuse to overwrite a previous evaluation.'
screen=read(REPAIR/'screening-final/summary.json');validation=read(REPAIR/'verification.json')
assert screen['state']=='complete' and validation['accepted_after']==26
accepted=[r for r in screen['records'] if r['paired_injectable']]
new=[r for r in accepted if not r['old_paired_injectable']]
assert len(new)==1 and new[0]['icao24']=='3c6709' and new[0]['quality_windows']['20']['full_quality_pass']
sid_new=new[0]['scene'];a_new=new[0]['icao24']
old_manifest=read(OLD/'window-20s/segmented/results/run-manifest.json')
checkpoint=B/'encoder-10s/encoder/encoder.pt'
assert sha(checkpoint)==old_manifest['checkpoint_sha256']
assert sha(OLD/'assignments.json')==old_manifest['assignment_sha256']
assignments={a['scene']:a for a in read(OLD/'assignments.json')}
cfg=ComplexityConfig(**old_manifest['config']);assert cfg.min_r_squared==.94 and cfg.n_radii==64
protected={str(p):sha(p) for directory in [OLD/'window-20s',REPAIR/'screening-final'] for p in directory.rglob('*') if p.is_file()}
protected[str(OLD/'assignments.json')]=sha(OLD/'assignments.json')
device='cuda' if torch.cuda.is_available() else 'cpu'
encoder=FrozenEncoder(checkpoint,pooling='sum',device=device)
assert len(encoder.preprocess['mean'])==9 and encoder.preprocess['preprocessing']['stride_s']==10
calls=0;d_calls=0;replays=0;reproduction=[];comparisons={};paired_checks=[];shared={}
write(R/'run-manifest.json',dict(state='running',window_s=20,old_candidates=25,new_candidates=26,background_N=157,
    sample_s=10,peak_m=15000,route_prerequisite_m=5000,config=asdict(cfg),checkpoint_sha256=sha(checkpoint),device=device,
    assignment_sha256=sha(OLD/'assignments.json'),screening_manifest_sha256=sha(REPAIR/'screening-final/manifest.json'),
    protected_sources=protected,code_sha256={str(p):sha(p) for p in [Path(__file__),B/'evaluation-10s/workspace/complexity/calculator.py',B/'encoder-10s/source/trajectory_encoder/inference.py']},
    design='Same 157 baselines, same old 25 interventions, frozen master orders/sides and exact old baseline radius grids; add screened 3c6709; both existing shapes; complete doses; NA on failure; no selection.'))

def estimate(e,radii,s):
    global d_calls
    d_calls+=1
    return estimate_complexity(e,config=cfg,radii=radii,scene_id=s).to_dict()

for shape in ['segmented','smooth']:
    old=OLD/'window-20s'/shape;folder=R/shape
    popout=folder/'population';out=folder/'results';popout.mkdir(parents=True,exist_ok=False);out.mkdir(exist_ok=False)
    old_generation=read(old/'population/summary.json')
    old_trials=read(old/'results/experiment-results.json')['scenes']
    old_diags={r['scene']:r for r in read(old/'results/scene-diagnostics.json')}
    assert read(old/'results/run-manifest.json')['config']==old_manifest['config']
    trials=[];diagnostics=[];population_rows=[];old_by={(t['scene_id'],t['replicate']):t for t in old_trials}
    start_calls=calls;start_d=d_calls
    for s in old_generation['scenes']:
        sid=s['scene'];old_eligible=s['injectable']
        eligible=sorted(r['icao24'] for r in accepted if r['scene']==sid)
        assert set(old_eligible)<=set(eligible)
        with np.load(old/'population'/(sid+'-population.npz')) as z:pop={k:z[k].copy() for k in z.files}
        original_keys=set(pop)
        with np.load(old/'results'/(sid+'-embeddings.npz')) as z:emb={k:z[k].copy() for k in z.files}
        ids=list(map(str,emb['ids']));base=emb['baseline'];radii=np.asarray(old_diags[sid]['radii'])
        assert ids==sorted(k[:-9] for k in pop if k.endswith('_baseline'))
        assert len(ids)==s['background']
        positive=pdist(base);positive=positive[positive>0]
        np.testing.assert_array_equal(radii,np.geomspace(positive.min(),positive.max(),cfg.n_radii))
        if shape=='segmented':
            probe=np.asarray(encoder.encode(pop[ids[0]+'_baseline'],resample_from_1hz=False)['embedding']);calls+=1
            np.testing.assert_allclose(probe,base[0],rtol=1e-6,atol=1e-6)
            reproduction.append(dict(scene=sid,encoder_max_abs_difference=float(np.max(np.abs(probe-base[0])))))
            shared[sid]=(base.copy(),radii.copy(),eligible.copy())
        else:
            np.testing.assert_array_equal(base,shared[sid][0]);np.testing.assert_array_equal(radii,shared[sid][1]);assert eligible==shared[sid][2]
        if sid==sid_new:
            baseline=pop[a_new+'_baseline'];start=(len(baseline)-60)//2
            with np.load(REPAIR/'screening-final'/(sid+'-'+a_new+'-routes.npz')) as z:
                for side in ['left','right']:
                    q=baseline.copy();key=('segmented_' if shape=='segmented' else '15000_')+side
                    assert z[key].shape==(61,2)
                    q[start:start+61,:2]=z[key]
                    np.testing.assert_array_equal(q[:,2:],baseline[:,2:])
                    np.testing.assert_array_equal(q[:start],baseline[:start]);np.testing.assert_array_equal(q[start+61:],baseline[start+61:])
                    assert np.isfinite(q).all() and q.shape==baseline.shape
                    pop[a_new+'_'+side]=q
                    emb[a_new+'_'+side]=np.asarray(encoder.encode(q,resample_from_1hz=False)['embedding']);calls+=1
        # Every pre-existing population array is preserved bit for bit.
        with np.load(old/'population'/(sid+'-population.npz')) as z:
            for key in original_keys:np.testing.assert_array_equal(pop[key],z[key])
        np.savez_compressed(popout/(sid+'-population.npz'),**pop)
        np.savez_compressed(out/(sid+'-embeddings.npz'),**emb)
        base_D=estimate(base,radii,sid)
        assert base_D['status']==old_diags[sid]['baseline_status']
        assert base_D['dimension']==old_diags[sid]['baseline_D']
        for repeat in assignments[sid]['repeats']:
            previous=old_by[sid,repeat['replicate']]
            assert previous['seed']==repeat['seed']
            old_order=[a for a in repeat['assignments'] if a['icao24'] in old_eligible]
            chosen=[a for a in repeat['assignments'] if a['icao24'] in eligible]
            assert old_order==previous['assignments']
            assert [a for a in chosen if a['icao24'] in old_eligible]==old_order
            assert len(chosen)==len(eligible) and len({a['icao24'] for a in chosen})==len(eligible)
            # Replay every old dose from its frozen embeddings. Compare full
            # diagnostics, not just rounded D or the correlation coefficient.
            current=base.copy();replay=[dict(vectoring_aircraft=0,**base_D)]
            for dose,a in enumerate(old_order,1):
                current[ids.index(a['icao24'])]=emb[a['icao24']+('_left' if a['side']<0 else '_right')]
                replay.append(dict(vectoring_aircraft=dose,**estimate(current,radii,sid)))
            assert canonical(replay)==canonical(previous['dose_curve']),(shape,sid,repeat['replicate'],'old D mismatch')
            replays+=len(replay)
            current=base.copy();curve=[dict(vectoring_aircraft=0,**base_D)]
            for dose,a in enumerate(chosen,1):
                current[ids.index(a['icao24'])]=emb[a['icao24']+('_left' if a['side']<0 else '_right')]
                curve.append(dict(vectoring_aircraft=dose,**estimate(current,radii,sid)))
            if sid!=sid_new:assert canonical(curve)==canonical(previous['dose_curve'])
            else:
                added_at=next(i for i,a in enumerate(chosen,1) if a['icao24']==a_new)
                assert canonical(curve[:added_at])==canonical(previous['dose_curve'][:added_at])
            paired_checks.append(dict(shape=shape,scene=sid,replicate=repeat['replicate'],old_curve_reproduced=True,
                unchanged_curve_or_pre_addition_prefix=True,added_aircraft_at_dose=added_at if sid==sid_new else None))
            trials.append(dict(scene_id=sid,replicate=repeat['replicate'],seed=repeat['seed'],n_aircraft=len(ids),n_vectoring_eligible=len(eligible),assignments=chosen,dose_curve=curve))
        population_rows.append(dict(scene=sid,background=len(ids),injectable_before=len(old_eligible),injectable_after=len(eligible),injectable=eligible,
            baselines_changed=0,old_routes_changed=0,added_candidates=sorted(set(eligible)-set(old_eligible))))
        diagnostics.append(dict(scene=sid,N=len(ids),candidates=len(eligible),baseline_D=base_D['dimension'],baseline_status=base_D['status'],radii=radii.tolist(),radius_grid_source='unchanged original 20 s baseline grid'))
        print(json.dumps(dict(shape=shape,scene=sid,N=len(ids),candidates=len(eligible),baseline_D=base_D['dimension'])),flush=True)
    summary=summarize(trials);previous_summary=summarize(old_trials)
    write(out/'experiment-results.json',dict(window_s=20,shape=shape,scenes=trials))
    write(out/'summary.json',summary);write(out/'scene-diagnostics.json',diagnostics)
    write(popout/'summary.json',dict(window_s=20,peak_m=15000.,shape=shape,scenes=population_rows,totals=dict(background=157,injectable=26)))
    write(out/'run-manifest.json',dict(state='complete',window_s=20,shape=shape,checkpoint_sha256=sha(checkpoint),config=asdict(cfg),
        device=device,new_encoder_calls=calls-start_calls,new_D_calls_including_old_replay=d_calls-start_d,
        assignment_sha256=sha(OLD/'assignments.json'),population_hashes={p.name:sha(p) for p in popout.glob('*') if p.is_file()},
        full_dose_range=True,negative_and_failed_results_retained=True,independent_scenes=4,orders_per_scene=5))
    comparisons[shape]=dict(before=previous_summary,after=summary)
    print('RESULT '+json.dumps(dict(shape=shape,before=previous_summary['all'],after=summary['all'])),flush=True)
assert all(sha(p)==h for p,h in protected.items())
write(R/'screening-exclusions.json',dict(source_sha256=sha(REPAIR/'screening-final/summary.json'),records=[r for r in screen['records'] if not r['paired_injectable']]))
write(R/'evaluation-summary.json',dict(state='complete',comparisons=comparisons,new_encoder_calls=calls,new_D_calls=d_calls,
    old_dose_records_exactly_reproduced=replays,old_results_unchanged=True,reproduction_checks=reproduction,paired_checks=paired_checks))
m=read(R/'run-manifest.json');m.update(state='complete',new_encoder_calls=calls,new_D_calls=d_calls,old_dose_records_exactly_reproduced=replays,
    protected_sources_unchanged=True,new_route_generation_calls=0,new_reference_fits=0)
write(R/'run-manifest.json',m)
print('EVALUATION COMPLETE',flush=True)
