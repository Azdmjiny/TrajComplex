"""Full-dose evaluation of saved accepted pairs; never refit or generate routes."""
from pathlib import Path
import hashlib,json,sys,time
R=Path(__file__).resolve().parent;B=R.parent
WS=B/'evaluation-10s/workspace';SCREEN=B/'four-scene-vectoring-screen/screening'
sys.dont_write_bytecode=True
sys.path[:0]=[str(B/'evaluation-python-deps'),str(WS),str(WS/'evaluation/code')]
import numpy as np
import scipy,torch
from scipy.spatial.distance import pdist
from Encoder.trajectory_encoder.inference import FrozenEncoder
from complexity.calculator import ComplexityConfig,estimate_complexity
from run_analysis import summarize
from truncation import curve_correlation

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False),encoding='utf8')
def arrhash(a):return hashlib.sha256(np.ascontiguousarray(a,dtype='<f8').tobytes()).hexdigest()

OUT=R/'results';OUT.mkdir(exist_ok=False)
screen=read(SCREEN/'manifest.json');ss=read(SCREEN/'summary.json')
previous=read(WS/'evaluation/results/run-manifest.json')
assert screen['state']==ss['state']=='complete' and ss['totals']['injectable']==21
checkpoint=B/'encoder-10s/encoder/encoder.pt'
assert sha(checkpoint)==previous['checkpoint_sha256']=='bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976'
cfg=ComplexityConfig(normalize=False)
assert json.loads(json.dumps(cfg.__dict__))==previous['config']
protected={str(p):sha(p) for folder in [B/'four-scene-vectoring-screen',B/'coverage-nic-supplement',
              WS/'evaluation',WS/'complexity',WS/'Encoder/trajectory_encoder',B/'encoder-10s/encoder',
              B/'vectoring-direction-repair/screening',B/'vectoring-direction-repair/code']
           for p in folder.rglob('*') if p.is_file() and '__pycache__' not in str(p)}
write(R/'before-hashes.json',protected)
selections=[];records={}
for index,scene in enumerate(screen['scenes'],1):
    rows=read(SCREEN/(scene+'-records.json'));records[scene]=rows
    ids=sorted(r['icao24'] for r in rows)
    eligible=[i for i,a in enumerate(ids) if next(r for r in rows if r['icao24']==a)['injectable']]
    assert len(eligible)==ss['scenes'][index-1]['injectable']
    repeats=[]
    for rep in range(5):
        seed=43019+index*997+rep;rng=np.random.default_rng(seed)
        order=rng.permutation(eligible)
        assignments=[dict(icao24=ids[int(j)],baseline_index=int(j),side=int(rng.choice([-1,1]))) for j in order]
        repeats.append(dict(replicate=rep,seed=seed,assignments=assignments))
    selections.append(dict(scene=scene,scene_index=index,aircraft_ids=ids,eligible_indices=eligible,repeats=repeats))
# Frozen before loading the model or calculating any embedding or D.
policy=dict(scenes=screen['scenes'],candidates=21,repeats_per_scene=5,cutoff=None,
    scene_selection='Exactly the four already screened scenes; none added, removed or selected by D/correlation',
    seed_formula='43019 + chronological one-based scene_index * 997 + replicate (0..4); original vectoring RNG formula',
    doses='Every integer from 0 through all accepted candidates; one additional saved route replacement per dose',
    pairing='Reuse saved frozen baseline and corresponding accepted left/right arrays; no resampling, refitting or regeneration',
    encoder='Frozen strict-10s epoch-90 checkpoint; training normalization; sum pooling; unnormalized scene distances',
    radii='64 geometric scales from positive baseline embedding distances; fixed within a scene across every dose and repeat',
    D_config=cfg.__dict__,correlation='Existing Spearman function; status=ok and finite D only; at least 5 valid doses; no truncation',
    invalid_D='Keep every attempted dose and reason; never fill or zero; retain scenes with no estimable correlation',
    independence='Five random orders are within-scene repeats, not independent scenes; no confirmatory p-values',
    restrictions=dict(holding_runs=0,threshold_changes=0,new_fits=0,new_generated_routes=0,new_data_downloads=0,scene_exclusions=0,truncations=0))
write(R/'policy.json',policy);write(R/'assignments.json',selections)
torch.set_num_threads(2)
enc=FrozenEncoder(checkpoint,pooling='sum',device='cuda' if torch.cuda.is_available() else 'cpu')
assert enc.preprocess['preprocessing']['stride_s']==10 and enc.preprocess['preprocessing']['include_endpoint'] is False
assert enc.preprocess['preprocessor_id']==previous['encoder_preprocessor_id']
assert str(enc.device)==previous['device']
manifest=dict(state='running',screening_manifest_sha256=sha(SCREEN/'manifest.json'),
    screening_populations_sha256={s:sha(SCREEN/(s+'-population.npz')) for s in screen['scenes']},
    checkpoint_sha256=sha(checkpoint),checkpoint_path=str(checkpoint),preprocessor_id=enc.preprocess['preprocessor_id'],
    input_sample_s=10,pooling='sum',device=str(enc.device),torch=torch.__version__,numpy=np.__version__,scipy=scipy.__version__,
    config=cfg.__dict__,scenes=screen['scenes'],screening_thresholds=screen['thresholds'],screening_numerical=screen['numerical'],
    fit_model=screen['fit_model'],direction_certificate=screen['direction_certificate'],route_model=screen['route_model'],route_numerics=screen['route_numerics'],
    policy_sha256=sha(R/'policy.json'),assignments_sha256=sha(R/'assignments.json'),
    source_sha256={str(p):sha(p) for p in [Path(__file__),WS/'complexity/calculator.py',WS/'evaluation/code/truncation.py',WS/'evaluation/code/run_analysis.py',
                  *sorted((WS/'Encoder/trajectory_encoder').glob('*.py'))]},
    restrictions=policy['restrictions'])
write(OUT/'run-manifest.json',manifest)
trials=[];scene_details=[];encoding_calls=0;D_calls=0;started=time.monotonic()
for sel in selections:
    scene=sel['scene'];ids=sel['aircraft_ids'];rowmap={r['icao24']:r for r in records[scene]}
    with np.load(SCREEN/(scene+'-population.npz')) as saved:
        base=[];left=[];right=[]
        for a in ids:
            p=saved[a+'_baseline'];r=rowmap[a]
            assert arrhash(p)==r['baseline_sha256']
            z=enc.encode(p)['embedding'];encoding_calls+=1
            assert z.shape==(16,) and np.isfinite(z).all()
            base.append(z);left.append(z.copy());right.append(z.copy())
            if r['injectable']:
                start=(len(p)-60)//2;end=start+61
                for label,arr in [('left',left),('right',right)]:
                    q=saved[a+'_'+label]
                    assert q.shape==p.shape
                    np.testing.assert_array_equal(q[:,2],p[:,2]);np.testing.assert_array_equal(q[:start],p[:start]);np.testing.assert_array_equal(q[end:],p[end:])
                    zz=enc.encode(q)['embedding'];encoding_calls+=1
                    assert zz.shape==(16,) and np.isfinite(zz).all()
                    arr[-1]=zz
        base=np.asarray(base);left=np.asarray(left);right=np.asarray(right)
    # Same vectoring dtype and baseline-scale construction as the existing run.
    positive=pdist(base);positive=positive[positive>0]
    if not len(positive) or positive.min()==positive.max():raise RuntimeError('Baseline has no fixed positive distance-scale range; no automatic fallback')
    radii=np.geomspace(positive.min(),positive.max(),64)
    def estimate(embedding):
        global D_calls
        result=estimate_complexity(embedding,config=cfg,radii=radii,scene_id=scene).to_dict();D_calls+=1
        return result
    baseline=estimate(base)
    np.savez_compressed(OUT/(scene+'-embeddings.npz'),baseline=base,left=left,right=right,radii=radii,aircraft_ids=np.asarray(ids))
    current_trials=[]
    for repeat in sel['repeats']:
        current=base.copy();curve=[dict(vectoring_aircraft=0,**baseline)]
        for dose,assignment in enumerate(repeat['assignments'],1):
            j=assignment['baseline_index'];current[j]=(left if assignment['side']<0 else right)[j]
            curve.append(dict(vectoring_aircraft=dose,**estimate(current)))
        trial=dict(scene_id=scene,replicate=repeat['replicate'],seed=repeat['seed'],n_aircraft=len(ids),n_vectoring_eligible=len(sel['eligible_indices']),
                   assignments=repeat['assignments'],dose_curve=curve)
        trials.append(trial);current_trials.append(trial)
    diagnostics=dict(scene=scene,n_aircraft=len(ids),eligible=len(sel['eligible_indices']),baseline_status=baseline['status'],baseline_reason=baseline['reason'],baseline_D=baseline['dimension'],
        correlations=[curve_correlation(t['dose_curve'],'vectoring_aircraft') for t in current_trials])
    scene_details.append(diagnostics)
    write(OUT/'experiment-results.json',dict(qc500_safe=dict(vectoring=dict(kind='vectoring',variant='qc500_safe',scenes=trials))))
    print(json.dumps(diagnostics),flush=True)
summary,selection=summarize(trials,'vectoring',truncate=False)
write(OUT/'summary.json',summary);write(OUT/'point-selection.json',selection)
write(OUT/'scene-diagnostics.json',scene_details)
assert len(trials)==20 and sum(len(t['dose_curve']) for t in trials)==125
assert encoding_calls==199 and D_calls==109
assert all(sha(p)==h for p,h in protected.items())
manifest.update(state='complete',elapsed_s=time.monotonic()-started,encoding_calls=encoding_calls,D_calls=D_calls,
                dose_records=125,curves=20,old_files_unchanged=True)
write(OUT/'run-manifest.json',manifest)
print('EVALUATION COMPLETE '+json.dumps(dict(all_curves=summary['all']['full'],hour_level=summary['hour_level']['full'],baseline_ok=summary['baseline_ok']['full'])),flush=True)
