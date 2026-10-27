"""Validate saved full-dose calculations and create clear, complete figures."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timedelta
import hashlib,json,sys
R=Path(__file__).resolve().parent;B=R.parent;OUT=R/'results'
WS=B/'evaluation-10s/workspace';sys.dont_write_bytecode=True
sys.path[:0]=[str(B/'evaluation-python-deps'),str(WS),str(WS/'evaluation/code')]
import numpy as np
from scipy.stats import rankdata
from complexity.calculator import ComplexityConfig,estimate_complexity
from truncation import finite_ok,curve_correlation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False),encoding='utf8')

m=read(OUT/'run-manifest.json');assert m['state']=='complete'
policy=read(R/'policy.json');assignments=read(R/'assignments.json')
trials=read(OUT/'experiment-results.json')['qc500_safe']['vectoring']['scenes']
summary=read(OUT/'summary.json');selection=read(OUT/'point-selection.json')
assert len(trials)==20 and len(selection)==125 and len(m['scenes'])==4
assert sha(R/'policy.json')==m['policy_sha256'] and sha(R/'assignments.json')==m['assignments_sha256']
assert policy['cutoff'] is None and policy['restrictions']['scene_exclusions']==0
assert all(s['within_retained_range'] and s['cutoff'] is None for s in selection)
cfg=ComplexityConfig(**m['config']);rows=[];verified=0;reasons=Counter()
for sel in assignments:
    scene=sel['scene'];tt=[t for t in trials if t['scene_id']==scene]
    assert len(tt)==5
    with np.load(OUT/(scene+'-embeddings.npz')) as embeddings:
        assert embeddings['aircraft_ids'].tolist()==sel['aircraft_ids']
        for rep,t in enumerate(tt):
            fixed=sel['repeats'][rep];assert t['assignments']==fixed['assignments']
            assert len(t['dose_curve'])==len(sel['eligible_indices'])+1
            assert len({a['icao24'] for a in fixed['assignments']})==len(sel['eligible_indices'])
            rng=np.random.default_rng(43019+sel['scene_index']*997+rep)
            order=rng.permutation(sel['eligible_indices'])
            expected=[dict(icao24=sel['aircraft_ids'][int(j)],baseline_index=int(j),side=int(rng.choice([-1,1]))) for j in order]
            assert fixed['assignments']==expected
            current=embeddings['baseline'].copy()
            for dose,p in enumerate(t['dose_curve']):
                if dose:
                    a=fixed['assignments'][dose-1];current[a['baseline_index']]=embeddings['left' if a['side']<0 else 'right'][a['baseline_index']]
                assert p['vectoring_aircraft']==dose
                check=estimate_complexity(current,config=cfg,radii=embeddings['radii'],scene_id=scene).to_dict()
                # Exact replay from saved embeddings verifies paired replacements,
                # radii, every gate, and failure preservation without re-encoding.
                assert json.loads(json.dumps(check))=={k:v for k,v in p.items() if k!='vectoring_aircraft'}
                verified+=1;reasons[p['reason'] or 'ok']+=1
            corr=curve_correlation(t['dose_curve'],'vectoring_aircraft')
            good=[p for p in t['dose_curve'] if finite_ok(p)]
            if corr['rho'] is not None:
                manual=float(np.corrcoef(rankdata([p['vectoring_aircraft'] for p in good]),rankdata([p['dimension'] for p in good]))[0,1])
                assert abs(manual-corr['rho'])<1e-14
            rows.append(dict(scene=scene,replicate=rep,**corr))
assert verified==125
protected=read(R/'before-hashes.json');assert all(sha(p)==h for p,h in protected.items())
assert all(sha(p)==h for p,h in m['source_sha256'].items())
scene_results=[]
for scene in m['scenes']:
    tt=[t for t in trials if t['scene_id']==scene];pp=[p for t in tt for p in t['dose_curve']]
    cr=[r for r in rows if r['scene']==scene];rho=[r['rho'] for r in cr if r['rho'] is not None]
    local=(datetime.strptime(scene,'%Y-%m-%dT%HZ')+timedelta(hours=8)).strftime('%Y-%m-%d %H:00')
    scene_results.append(dict(scene=scene,local_time=local,n_aircraft=tt[0]['n_aircraft'],eligible=tt[0]['n_vectoring_eligible'],
        attempted_D=len(pp),valid_D=int(sum(finite_ok(p) for p in pp)),D_reasons=dict(Counter(p['reason'] or 'ok' for p in pp)),
        r_squared_range=[min(p['r_squared'] for p in pp),max(p['r_squared'] for p in pp)],
        baseline_D=pp[0]['dimension'],baseline_r_squared=pp[0]['r_squared'],rho=rho,
        rho_median=float(np.median(rho)) if rho else None,positive=sum(r>0 for r in rho),negative=sum(r<0 for r in rho)))
verification=dict(all_passed=True,saved_dose_records_replayed=125,correlations_independently_rank_checked=5,
    complete_scenes=4,complete_curves=20,invalid_D_records_retained=sum(not finite_ok(p) for t in trials for p in t['dose_curve']),
    no_truncation=True,no_scene_exclusions=True,original_files_unchanged=len(protected),
    fixed_assignments_verified=True,fixed_checkpoint_and_preprocessor=True,old_results_unchanged=True)
write(R/'verification.json',verification);write(OUT/'scene-summary.json',scene_results)

FIG=R/'figures';FIG.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.titlesize':11,'axes.labelsize':10,'figure.dpi':150,'savefig.dpi':200})
colors=plt.get_cmap('tab10').colors[:5]
handles=[Line2D([0],[0],color=colors[i],marker='o',markersize=4,label=f'Order {i+1}') for i in range(5)]
valid_D=[p['dimension'] for t in trials for p in t['dose_curve'] if finite_ok(p)]
lo,hi=min(valid_D),max(valid_D);pad=max((hi-lo)*.2,.003)
fig,axes=plt.subplots(2,2,figsize=(12.8,8.8),layout='constrained')
fig.suptitle('Vectoring: complete dose range, all four scenes\nAccepted D estimates only; no truncation or scene exclusion',fontsize=15)
for ax,s in zip(axes.flat,scene_results):
    tt=[t for t in trials if t['scene_id']==s['scene']]
    ax.set_title(f"{s['local_time']} (UTC+08)\nN = {s['n_aircraft']} aircraft; {s['eligible']} injectable candidates",pad=10)
    ax.set_xlabel('Number of aircraft with fixed 5 km vectoring');ax.set_ylabel('Accepted geometric dimension D')
    ax.set_xlim(-.15,s['eligible']+.15);ax.set_xticks(range(s['eligible']+1));ax.grid(alpha=.2)
    if s['valid_D']:
        ax.set_ylim(lo-pad,hi+pad)
        for i,t in enumerate(tt):
            x=[p['vectoring_aircraft'] for p in t['dose_curve']]
            y=[p['dimension'] if finite_ok(p) else np.nan for p in t['dose_curve']]
            ax.plot(x,y,'o-',color=colors[i],lw=1.6,ms=4,alpha=.9)
        ax.text(.02,.98,f"Valid D: {s['valid_D']}/{s['attempted_D']}\n3 positive / 2 negative orders",transform=ax.transAxes,va='top',fontsize=9,
                bbox=dict(facecolor='white',alpha=.85,edgecolor='none'))
    else:
        ax.set_facecolor('#f5f5f5');ax.set_yticks([])
        ax.text(.5,.52,f"D not estimable\n0 / {s['attempted_D']} attempted estimates accepted\n\nAll fail the unchanged R² ≥ 0.98 gate\nObserved R²: {s['r_squared_range'][0]:.4f}–{s['r_squared_range'][1]:.4f}",
                ha='center',va='center',transform=ax.transAxes,fontsize=11,linespacing=1.6)
fig.legend(handles=handles,loc='outside lower center',ncol=5,frameon=False)
fig.savefig(FIG/'vectoring-full-dose.png');fig.savefig(FIG/'vectoring-full-dose.svg');plt.close(fig)

fig,axes=plt.subplots(2,2,figsize=(12.8,8.8),layout='constrained',sharey=True)
fig.suptitle('Why D was accepted or rejected\nFit R² at every dose and random order; threshold unchanged',fontsize=15)
for ax,s in zip(axes.flat,scene_results):
    ax.set_title(f"{s['local_time']} (UTC+08)\nValid D estimates: {s['valid_D']} / {s['attempted_D']}",pad=10)
    for i,t in enumerate(t for t in trials if t['scene_id']==s['scene']):
        ax.plot([p['vectoring_aircraft'] for p in t['dose_curve']],[p['r_squared'] for p in t['dose_curve']],
                'o-',color=colors[i],lw=1.5,ms=4,alpha=.9)
    ax.axhline(.98,color='black',ls='--',lw=1.3)
    ax.set_ylim(.944,.993);ax.set_xlim(-.15,s['eligible']+.15);ax.set_xticks(range(s['eligible']+1))
    ax.set_xlabel('Number of aircraft with fixed 5 km vectoring');ax.set_ylabel('Log–log fit R²');ax.grid(alpha=.2)
fig.legend(handles=handles+[Line2D([0],[0],color='black',ls='--',label='Required R² = 0.98')],loc='outside lower center',ncol=6,frameon=False)
fig.savefig(FIG/'vectoring-fit-quality.png');fig.savefig(FIG/'vectoring-fit-quality.svg');plt.close(fig)

lines=['# Four-scene Vectoring correlation evaluation','',
'## Main conclusion','',
'**These results do not establish a stable positive relationship between injected Vectoring count and D.** Three scenes have no accepted D estimates under the existing fit-quality gate. The remaining scene has three positive and two negative Spearman correlations across its five random orders. Its median rho is 0.5768, but the orders are within-scene repeats, not five independent scenes. No negative or unestimable scene/order was removed.','',
'## Frozen scope and method','',
'The four previously screened scenes and all 21 accepted candidate pairs were fixed before inference. Saved paired baselines and accepted left/right routes are used directly; no fit, route generation, resampling, quality relaxation, alternative scene, extra experimental arm, or Holding run was added. Fixed 5 km peak, 600-second maneuver, strict 10-second inputs, barometric-height convention and all screening thresholds remain unchanged.','',
'The same frozen 10-second epoch-90 Encoder checkpoint, training mean/std, nine input features, sum pooling, 16-dimensional embeddings and unnormalized Euclidean distances are used. The checkpoint SHA-256 is `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`. The existing D estimator/configuration is unchanged: 64 baseline-derived fixed radius values per scene, at least 30 aircraft, at least eight fitting scales, at least ten pairs, C(r) bounds 0.02–0.3, radius span at least 2, and R² at least 0.98.','',
'Five orders per scene use the original seed formula `43019 + scene_index*997 + replicate`, with scenes in the disclosed chronological order (one-based index) and replicates 0–4. Orders and left/right assignments were written before loading the Encoder. Every integer dose from zero through all eligible candidates is included. Correlation uses the existing full-range Spearman function on finite, status-ok D values, requiring at least five valid doses. Invalid values remain null with explicit reasons; they are never replaced by zero.','',
'## Results by scene','',
'Times are local UTC+08. D counts include five copies of the common zero-dose baseline, one in each displayed curve; they are not independent measurements.','',
'| Local scene start | Background aircraft | Injectable | D accepted / attempted | Fit R² range | Estimable orders | Median rho |','|---|---:|---:|---:|---|---:|---|']
for s in scene_results:
    med=f"{s['rho_median']:.4f}" if s['rho_median'] is not None else 'Not estimable'
    lines.append(f"| {s['local_time']} | {s['n_aircraft']} | {s['eligible']} | {s['valid_D']} / {s['attempted_D']} | {s['r_squared_range'][0]:.4f}–{s['r_squared_range'][1]:.4f} | {len(s['rho'])} / 5 | {med} |")
lines+=['','All 95 rejected dose records fail `poor_linear_fit`; there are enough fitting scales (28–34) but R² is below 0.98. The failure is in dimension estimation, not candidate trajectory screening or a lack of attempted dose levels. Baselines of those three scenes also fail. The threshold was not reduced, and rejected slopes were not relabeled as D.','',
'For September 27 at 13:00, the five full-range Spearman coefficients are: **+0.5768, −0.4058, +0.7537, +0.7714, −0.8286**. All six doses in each order have accepted D. The common baseline D is **1.37962**; accepted D across all orders/doses ranges from **1.35727 to 1.39673**. Positive and negative outcomes are both retained.','',
'The overall median among computable curves is +0.5768, but all five computable curves come from that single scene. Reporting only this median as broad evidence of positive correlation would omit the three unestimable scenes and the two negative orders. This run neither demonstrates a robust positive association nor proves that no positive association exists.','',
'## Complete figures','',
'![Full dose range and explicit unestimable scenes](figures/vectoring-full-dose.png)','',
'![Fit quality for all attempted doses](figures/vectoring-fit-quality.png)','',
'Coincident lines/markers represent identical recorded values; no jitter, smoothing or outcome-based cut is applied. SVG copies are also provided for export.','',
'## Every order, including unestimable ones','',
'| Scene UTC | Order | Valid doses / total | Spearman rho | Reason if unavailable |','|---|---:|---:|---|---|']
for r in rows:
    rho=f"{r['rho']:+.6f}" if r['rho'] is not None else 'Not estimable'
    lines.append(f"| {r['scene']} | {r['replicate']+1} | {r['valid']} / {r['total']} | {rho} | {r['reason'] or 'None'} |")
lines+=['','## Verification and interpretation limits','',
'All 125 displayed dose records were independently replayed from saved embeddings using the fixed assignments and baseline radii; every result and rejection matched exactly. Computable Spearman values were independently checked using tied ranks. The four scenes, all 20 curves, every attempted dose, and unchanged checkpoint/source files were verified. The original evaluation used 199 trajectory encodings and 109 D calculations because each baseline was computed once and reused across five orders. Verification required no re-encoding, new route, parameter tuning or alternate experiment.','',
'Saved screening populations keep 157 fixed members in total; successful candidate fits are used consistently in both zero-dose baselines and corresponding injections. Rejected injection candidates remain background members. Backgrounds without candidate quality evidence use their unchanged basic-QC inputs, following the approved separation policy.','',
'This is a conditional synthetic-perturbation evaluation with four coverage-selected scenes. Candidate geometry and quality verification do not guarantee a scaling regime in the resulting embedding cloud. Five injection orders are dependent repeats. No confirmatory p-values, extra statistical model, threshold adjustment, or new sample-selection rule was introduced. Holding equal-duration control remains unrun.','',
'## Files and preservation','',
'`policy.json` and `assignments.json` freeze the protocol before inference. `results/experiment-results.json` contains full D diagnostics for all doses; `results/point-selection.json` records inclusion status without truncation; `results/*-embeddings.npz` stores baseline and paired route embeddings with fixed radii. `results/run-manifest.json` records source/checkpoint hashes and settings. `verification.json` verifies replay and preservation. All previous screening, evaluation and Holding outputs remain untouched.','']
(R/'report.md').write_text('\n'.join(lines),encoding='utf8')
print(json.dumps(dict(verification=verification,scene_results=scene_results),indent=2))
