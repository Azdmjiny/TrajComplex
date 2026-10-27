"""Run both authorized time-window versions without changing Encoder or D gates."""
from pathlib import Path
import sys,json,hashlib
from dataclasses import asdict
R=Path(__file__).resolve().parent;B=R.parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(B/'evaluation-python-deps'),str(B/'encoder-10s/source'),str(B/'evaluation-10s/workspace')]
import numpy as np
import torch
from scipy.spatial.distance import pdist
from scipy.stats import spearmanr
from trajectory_encoder.inference import FrozenEncoder
from complexity.calculator import ComplexityConfig,estimate_complexity

read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
write=lambda p,v:Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf8')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def array_sha(a):return hashlib.sha256(np.ascontiguousarray(a,dtype='<f8').tobytes()).hexdigest()
ACTIVE=B/'changi-publication-repo/evaluation/runs/segmented-15km'
OLD_SMOOTH=B/'vectoring-15km-star-2026-10-24/population-15km'
assert read(R/'screening/summary.json')['state']=='complete'
frozen=read(ACTIVE/'results/segmented/run-manifest.json')
checkpoint=B/'encoder-10s/encoder/encoder.pt'
assert sha(checkpoint)==frozen['checkpoint_sha256']
cfg=ComplexityConfig(**frozen['config']);assert cfg.min_r_squared==.94
assignments={t['scene']:t for t in read(R/'assignments.json')}
device='cuda' if torch.cuda.is_available() else 'cpu'
encoder=FrozenEncoder(checkpoint,pooling='sum',device=device)
assert len(encoder.preprocess['mean'])==9 and encoder.preprocess['preprocessing']['stride_s']==10
cache={};calls=0;d_calls=0;reproduction=[]
protected={str(p):sha(p) for folder in [ACTIVE/'results/segmented',ACTIVE/'results/smooth-control'] for p in folder.glob('*') if p.is_file()}
def encode(p):
    global calls
    key=array_sha(p)
    if key not in cache:
        cache[key]=np.asarray(encoder.encode(p,resample_from_1hz=False)['embedding']);calls+=1
    return cache[key]
def estimate(embedding,radii,sid):
    global d_calls
    d_calls+=1
    return estimate_complexity(embedding,config=cfg,radii=radii,scene_id=sid).to_dict()
def summarize(trials):
    curves=[]
    for t in trials:
        good=[p for p in t['dose_curve'] if p['status']=='ok' and p['dimension'] is not None and np.isfinite(p['dimension'])]
        reason=None;value=None
        if len(good)<5:reason='fewer_than_five_valid_doses'
        elif np.ptp([p['dimension'] for p in good])==0:reason='constant_D'
        else:value=float(spearmanr([p['vectoring_aircraft'] for p in good],[p['dimension'] for p in good]).statistic)
        curves.append(dict(scene=t['scene_id'],replicate=t['replicate'],rho=value,reason=reason,valid=len(good),total=len(t['dose_curve'])))
    def stats(cc):
        vv=[c['rho'] for c in cc if c['rho'] is not None]
        return dict(estimable=len(vv),positive=sum(v>0 for v in vv),negative=sum(v<0 for v in vv),median=float(np.median(vv)) if vv else None,
            valid_D=sum(c['valid'] for c in cc),attempted_D=sum(c['total'] for c in cc))
    scenes=[dict(scene=s,**stats([c for c in curves if c['scene']==s])) for s in sorted({c['scene'] for c in curves})]
    return dict(curves=curves,scenes=scenes,all=stats(curves))
# Exact cache reuse for unchanged arrays. Validate the current inference stack
# on one saved baseline per scene, before mixing old and new embeddings.
for sid in sorted(assignments):
    with np.load(ACTIVE/'results/segmented'/(sid+'-embeddings.npz')) as z:
        ids=list(map(str,z['ids']));baseline=z['baseline'].copy()
    with np.load(ACTIVE/'population'/(sid+'-population.npz')) as pop:
        probe=encoder.encode(pop[ids[0]+'_baseline'],resample_from_1hz=False)['embedding'];calls+=1
        maxdiff=float(np.max(np.abs(probe-baseline[0])))
        if not np.allclose(probe,baseline[0],rtol=1e-6,atol=1e-6):raise RuntimeError('Frozen Encoder reproduction failed: '+sid)
        for a,v in zip(ids,baseline):cache[array_sha(pop[a+'_baseline'])]=v
    for shape,result_name,pop_dir in [('segmented','segmented',ACTIVE/'population'),('smooth','smooth-control',OLD_SMOOTH)]:
        with np.load(ACTIVE/'results'/result_name/(sid+'-embeddings.npz')) as z,np.load(pop_dir/(sid+'-population.npz')) as pop:
            np.testing.assert_array_equal(z['baseline'],baseline)
            for key in z.files:
                if key not in ['baseline','ids']:cache[array_sha(pop[key])]=z[key]
    old_diag=next(x for x in read(ACTIVE/'results/segmented/scene-diagnostics.json') if x['scene']==sid)
    check=estimate(baseline,np.asarray(old_diag['radii']),sid)
    assert check['status']==old_diag['baseline_status'] and abs(check['dimension']-old_diag['baseline_D'])<1e-12
    reproduction.append(dict(scene=sid,encoder_max_abs_difference=maxdiff,baseline_D_reproduced=True))
all_summaries={}
for window in [15,20]:
    shared={}
    for shape in ['segmented','smooth']:
        folder=R/f'window-{window}s'/shape;out=folder/'results';out.mkdir(exist_ok=False)
        popdir=folder/'population';generation=read(popdir/'summary.json')
        trials=[];diagnostics=[];start_calls=calls;start_d=d_calls
        for s in generation['scenes']:
            sid=s['scene'];eligible=s['injectable']
            with np.load(popdir/(sid+'-population.npz')) as pop:
                ids=sorted(k[:-9] for k in pop.files if k.endswith('_baseline'))
                assert len(ids)==s['background']
                base=np.asarray([encode(pop[a+'_baseline']) for a in ids])
                injected={a:{side:encode(pop[a+'_'+side]) for side in ['left','right']} for a in eligible}
            distances=pdist(base);positive=distances[distances>0]
            radii=np.geomspace(positive.min(),positive.max(),cfg.n_radii)
            base_D=estimate(base,radii,sid)
            if shape=='segmented':shared[sid]=(base.copy(),radii.copy(),list(eligible))
            else:
                np.testing.assert_array_equal(base,shared[sid][0]);np.testing.assert_array_equal(radii,shared[sid][1]);assert eligible==shared[sid][2]
            for repeat in assignments[sid]['repeats']:
                chosen=[a for a in repeat['assignments'] if a['icao24'] in eligible]
                assert len(chosen)==len(eligible) and len({a['icao24'] for a in chosen})==len(eligible)
                current=base.copy();curve=[dict(vectoring_aircraft=0,**base_D)]
                for dose,a in enumerate(chosen,1):
                    current[ids.index(a['icao24'])]=injected[a['icao24']]['left' if a['side']<0 else 'right']
                    curve.append(dict(vectoring_aircraft=dose,**estimate(current,radii,sid)))
                trials.append(dict(scene_id=sid,replicate=repeat['replicate'],seed=repeat['seed'],n_aircraft=len(ids),n_vectoring_eligible=len(eligible),assignments=chosen,dose_curve=curve))
            diagnostics.append(dict(scene=sid,N=len(ids),candidates=len(eligible),baseline_D=base_D['dimension'],baseline_status=base_D['status'],radii=radii.tolist(),fitted_baselines_updated=s['fitted_baselines_updated']))
            np.savez_compressed(out/(sid+'-embeddings.npz'),baseline=base,ids=np.asarray(ids),**{a+'_'+side:value for a,row in injected.items() for side,value in row.items()})
            print(json.dumps(dict(window_s=window,shape=shape,scene=sid,candidates=len(eligible),baseline_D=base_D['dimension'],baseline_status=base_D['status'])),flush=True)
        summary=summarize(trials)
        write(out/'experiment-results.json',dict(window_s=window,shape=shape,scenes=trials))
        write(out/'summary.json',summary);write(out/'scene-diagnostics.json',diagnostics)
        write(out/'run-manifest.json',dict(state='complete',window_s=window,shape=shape,peak_m=15000.,checkpoint_sha256=sha(checkpoint),
            config=asdict(cfg),new_encoder_calls=calls-start_calls,new_D_calls=d_calls-start_d,device=device,
            assignment_sha256=sha(R/'assignments.json'),population_hashes={p.name:sha(p) for p in popdir.glob('*') if p.is_file()},
            method='Full-range replacement from each variant paired baseline; shared candidate identities, order, sides and radii between shapes; no truncation',
            independent_scenes=4,order_repeats_per_scene=5))
        all_summaries[f'{window}s-{shape}']=summary
        print('RESULT '+json.dumps(dict(window_s=window,shape=shape,**summary['all'])),flush=True)
for shape,name in [('segmented','segmented'),('smooth','smooth-control')]:
    old=read(ACTIVE/'results'/name/'experiment-results.json')
    trials=old['qc500_safe']['vectoring']['scenes']
    all_summaries['10s-'+shape]=summarize(trials)
assert all(sha(p)==h for p,h in protected.items())
write(R/'evaluation-summary.json',dict(state='complete',comparisons=all_summaries,total_new_encoder_calls=calls,total_new_D_calls=d_calls,
    reproduction_checks=reproduction,old_results_unchanged=True,protected_source_hashes=protected))
print('EVALUATION COMPLETE',flush=True)
