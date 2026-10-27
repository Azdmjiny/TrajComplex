"""Diagnose stored results only: no Encoder, D refit or counterfactual route."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,sys
R=Path(__file__).resolve().parent;B=R.parent;E=B/'four-scene-vectoring-evaluation'
sys.dont_write_bytecode=True;sys.path.insert(0,str(B/'evaluation-python-deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,obj):(R/name).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf8')
protected={str(p):sha(p) for folder in [E,B/'four-scene-vectoring-screen',B/'coverage-nic-supplement']
           for p in folder.rglob('*') if p.is_file() and '__pycache__' not in str(p)}
write('before-hashes.json',protected)
trials=read(E/'results/experiment-results.json')['qc500_safe']['vectoring']['scenes']
scene_summary=read(E/'results/scene-summary.json')
config=read(E/'results/run-manifest.json')['config']
baseline_details=[]
for info in scene_summary:
    tt=[t for t in trials if t['scene_id']==info['scene']];p=tt[0]['dose_curve'][0]
    assert all(t['dose_curve'][0]==p for t in tt)
    ix=np.asarray(p['fit_indices']);r=np.asarray(p['radii'])[ix];c=np.asarray(p['correlation'])[ix]
    # Inspect the original stored line and residuals. Do not choose a new range
    # or fit alternative slopes to make a formerly rejected D pass.
    residual=np.log(c)-(p['intercept']+p['fit_slope']*np.log(r))
    allpoints=[q for t in tt for q in t['dose_curve']]
    baseline_details.append(dict(scene=info['scene'],local_time=info['local_time'],
        n_aircraft=p['n_samples'],n_unique=p['n_unique'],zero_distance_pairs=p['zero_distance_pairs'],pair_count=p['n_pairs'],
        baseline_status=p['status'],baseline_reason=p['reason'],baseline_r_squared=p['r_squared'],
        radius_span_ratio=float(r[-1]/r[0]),fit_scale_count=len(ix),selected_pair_count_range=[p['pair_counts'][int(ix[0])],p['pair_counts'][int(ix[-1])]],
        log_residuals=residual.tolist(),selected_radii=r.tolist(),selected_C=c.tolist(),
        all_dose_reasons=dict(Counter(q['reason'] or 'ok' for q in allpoints)),
        all_dose_r_squared_range=[min(q['r_squared'] for q in allpoints),max(q['r_squared'] for q in allpoints)],
        all_dose_fit_scale_range=[min(len(q['fit_indices']) for q in allpoints),max(len(q['fit_indices']) for q in allpoints)]))

target='2026-09-27T05Z';tt=[t for t in trials if t['scene_id']==target];steps=[]
with np.load(E/'results'/(target+'-embeddings.npz')) as z:
    ids=z['aircraft_ids'].tolist();base=z['baseline'];left=z['left'];right=z['right']
    for t in tt:
        current=base.astype(np.float64)
        for dose,assignment in enumerate(t['assignments'],1):
            pre,post=t['dose_curve'][dose-1:dose+1];j=assignment['baseline_index']
            # These are only the exact configurations already evaluated.
            olddist=np.linalg.norm(current-current[j],axis=1)
            current[j]=(left if assignment['side']<0 else right)[j]
            newdist=np.linalg.norm(current-current[j],axis=1)
            changed=[i for i,(a,b) in enumerate(zip(pre['pair_counts'],post['pair_counts'])) if a!=b]
            added=sorted(set(post['fit_indices'])-set(pre['fit_indices']))
            removed=sorted(set(pre['fit_indices'])-set(post['fit_indices']))
            boundaries=[]
            for i in added+removed:
                radius=pre['radii'][i];crossings=[]
                for k in range(len(ids)):
                    if k!=j and bool(olddist[k]<radius)!=bool(newdist[k]<radius):
                        crossings.append(dict(other_aircraft=ids[k],distance_before=float(olddist[k]),distance_after=float(newdist[k]),
                                              entered=bool(newdist[k]<radius)))
                assert sum(1 if x['entered'] else -1 for x in crossings)==post['pair_counts'][i]-pre['pair_counts'][i]
                boundaries.append(dict(radius_index=i,radius=radius,old_pair_count=pre['pair_counts'][i],new_pair_count=post['pair_counts'][i],
                    old_C=pre['correlation'][i],new_C=post['correlation'][i],added=i in added,incident_pair_crossings=crossings))
            steps.append(dict(replicate=t['replicate'],dose=dose,icao24=assignment['icao24'],side=assignment['side'],
                D_before=pre['dimension'],D_after=post['dimension'],delta_D=post['dimension']-pre['dimension'],
                changed_radius_counts=changed,fit_indices_added=added,fit_indices_removed=removed,boundary_events=boundaries,
                interpretation='Observed sequential change conditional on the preceding aircraft/side assignments; not an isolated causal effect'))
assert len(steps)==25
effects=[]
for aircraft,side in sorted({(s['icao24'],s['side']) for s in steps}):
    group=[s for s in steps if (s['icao24'],s['side'])==(aircraft,side)]
    effects.append(dict(icao24=aircraft,side=side,observed_steps=len(group),delta_range=[min(s['delta_D'] for s in group),max(s['delta_D'] for s in group)],
                        replicas=[s['replicate'] for s in group]))
write('diagnosis.json',dict(config=config,baselines=baseline_details,observed_steps=steps,conditional_aircraft_side_effects=effects,
    restrictions=dict(new_encoder_calls=0,new_D_estimates=0,new_dose_combinations=0,new_routes=0,threshold_changes=0,experiments_added=0)))

F=R/'figures';F.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.titlesize':11,'savefig.dpi':180})
fig,axs=plt.subplots(4,2,figsize=(12.5,13.8),layout='constrained')
fig.suptitle('Existing baseline fits and residuals\nStored fit lines only; rejected slopes are not accepted D',fontsize=15)
for row,d in enumerate(baseline_details):
    p=next(t for t in trials if t['scene_id']==d['scene'])['dose_curve'][0]
    x=np.asarray(d['selected_radii']);y=np.asarray(d['selected_C']);fit=np.exp(p['intercept']+p['fit_slope']*np.log(x))
    color='#2a7a47' if p['status']=='ok' else '#a33c32'
    ax=axs[row,0];ax.loglog(x,y,'o-',color=color,ms=3,lw=1,label='Observed C(r)');ax.loglog(x,fit,'--',color='black',lw=1.3,label='Original fitted line')
    ax.set_title(f"{d['local_time']} (UTC+08): N={d['n_aircraft']}, R²={d['baseline_r_squared']:.5f}\n{'Accepted' if p['status']=='ok' else 'Rejected: R² < 0.98'}")
    ax.set_xlabel('Radius in embedding space');ax.set_ylabel('Correlation integral C(r)');ax.grid(alpha=.18,which='both')
    ax=axs[row,1];ax.semilogx(x,d['log_residuals'],'o-',color=color,ms=3,lw=1);ax.axhline(0,color='black',ls='--',lw=1)
    ax.set_title(f"Residuals of the same fit: {d['fit_scale_count']} scales\nObserved − fitted log C(r)")
    ax.set_xlabel('Radius in embedding space');ax.set_ylabel('Log residual');ax.grid(alpha=.18,which='both')
fig.legend(handles=[Line2D([0],[0],color='#a33c32',marker='o',label='Observed C(r) (rejected example)'),Line2D([0],[0],color='black',ls='--',label='Stored fitted line')],loc='outside lower center',ncol=2,frameon=False)
fig.savefig(F/'baseline-fit-residuals.png');fig.savefig(F/'baseline-fit-residuals.svg');plt.close(fig)

fig,axs=plt.subplots(5,1,figsize=(11.5,12),layout='constrained',sharey=True)
fig.suptitle('September 27: changes along the five already evaluated orders\nBars are conditional step changes, not isolated aircraft effects',fontsize=14)
rhos=scene_summary[-1]['rho']
for rep,ax in enumerate(axs):
    ss=[s for s in steps if s['replicate']==rep]
    ax.bar(range(1,6),[s['delta_D'] for s in ss],color=['#356c9e' if s['side']<0 else '#d37d29' for s in ss])
    ax.axhline(0,color='black',lw=.8);ax.set_ylim(-.03,.015);ax.set_ylabel('Change in D')
    ax.set_title(f'Order {rep+1}: Spearman rho = {rhos[rep]:+.3f}',loc='left')
    ax.set_xticks(range(1,6),[f"{s['icao24']}\n{'Left' if s['side']<0 else 'Right'}" for s in ss]);ax.grid(axis='y',alpha=.2)
fig.savefig(F/'observed-injection-steps.png');fig.savefig(F/'observed-injection-steps.svg');plt.close(fig)

lines=['# Diagnosis using the existing four-scene Vectoring results','',
'## Scope','',
'This is an analysis of already saved dose curves, embeddings, pair counts, fitting-scale indexes, assignment sequences and fit diagnostics. No new D estimates, alternate estimator, sample-size subsample, left/right swap, trajectory, threshold change or correlation experiment was performed.','',
'## Why the first three scenes fail','',
'The immediate cause is the existing log–log fit quality gate: all 95 attempted D records in those scenes have R² below 0.98. Their zero-injection baselines also fail, so Vectoring injection did not create the initial failure. The number of tracks, distinct embeddings, pair counts and fitting scales satisfy their respective numerical requirements.','',
'| Local baseline time UTC+08 | Aircraft / unique embeddings | Pairs | Fit scales | Radius span ratio | Baseline R² |','|---|---:|---:|---:|---:|---:|']
for d in baseline_details:lines.append(f"| {d['local_time']} | {d['n_aircraft']} / {d['n_unique']} | {d['pair_count']} | {d['fit_scale_count']} | {d['radius_span_ratio']:.2f} | {d['baseline_r_squared']:.5f} |")
lines+=['','The original line does not approximate the selected log C(r) curve closely enough. Residual plots show where that approximation fails; no better-looking subrange was searched. This is evidence that a single accepted power-law slope is not established over the existing selected scales, not proof that the aircraft data or Encoder are invalid.','',
'Sample size cannot be assigned as the sole cause from these records: the scene with 32 aircraft passes, whereas those with 38, 47 and 40 do not. This disproves a simple ordering by aircraft count, but it does not prove that finite-sample effects are absent. More or differently distributed points could affect the staircase of pair counts; no new sample-size experiment was run to test that possibility.','',
'![Existing baseline fits and residuals](figures/baseline-fit-residuals.png)','',
'## Why the fourth scene changes correlation sign','',
'All 30 D records pass the existing quality gates, but the five orders also use different left/right assignments. The stored sequences show that aircraft `750579` is assigned Right in both negative-rho orders, and Left in all three positive-rho orders. This identifies a concrete observed turning point, not a universal rule that Right decreases D.','',
'| Order | rho | `750579` side | D change at its injection | Fitting-scale event |','|---|---:|---|---:|---|']
for rep in range(5):
    s=next(x for x in steps if x['replicate']==rep and x['icao24']=='750579')
    event='one scale removed' if s['fit_indices_removed'] else 'one scale added' if s['fit_indices_added'] else 'same scales'
    lines.append(f"| {rep+1} | {rhos[rep]:+.6f} | {'Left' if s['side']<0 else 'Right'} | {s['delta_D']:+.6f} | {event} |")
lines+=['','In each negative order, that right-side injection changes the count at radius 10.6217104 from **10 pairs to 9 pairs**. With 32 aircraft there are 496 pairs, so C(r) changes from **10/496 = 0.0201613** to **9/496 = 0.0181452**. That point simultaneously falls below the unchanged minimum of ten pairs and the C(r) lower bound of 0.02, and is therefore removed from the fitting scales. The associated accepted D drops by about 0.0257 or 0.0264. This is a visible finite-count boundary event in the estimator, not a missing value or a manual truncation.','',
'The radius grid itself stays fixed. The subset of radii eligible for fitting can change with the point-cloud pair counts, as required by the existing estimator. Aircraft/side-induced distance changes and the estimator boundary therefore act together. D measures the geometry of a whole embedding cloud; changing one aircraft can move it toward or away from other aircraft rather than guaranteeing an increase in D.','',
'Some steps change pair counts only outside the selected fitting scales, leaving D exactly unchanged. Some left/right choices give different signs, and the same choice can have different magnitudes depending on preceding injections. These observations explain why a small number of discrete steps can produce different Spearman signs.','',
'![Observed sequential injection changes](figures/observed-injection-steps.png)','',
'## What can and cannot be concluded','',
'Confirmed: the first three scenes fail the R² gate even at baseline; the fourth has mixed signs; specific aircraft/side changes cross fitting-scale count boundaries. The direction and magnitude of observed sequential changes depend on the current scene state.','',
'Not isolated: how much of the first three failures is finite sample size versus the underlying embedding distribution, how an alternative estimator would behave, or the pure causal effect of side separated from order. Those require additional controlled comparisons. No such experiments were added or used to rescue a positive conclusion.','',
'The current evidence supports diagnosing estimator applicability and discrete sensitivity. It does not support claiming a stable strong positive Vectoring relationship.','',
'## Evidence','',
'`diagnosis.json` retains every observed step, changed count, scale boundary and the incident aircraft-pair crossing, alongside the existing baseline diagnostics. Figures display the original stored fits, including rejected fits explicitly labeled as such. Previous files are unchanged.','']
(R/'report.md').write_text('\n'.join(lines),encoding='utf8')
assert all(sha(p)==h for p,h in protected.items())
write('verification.json',dict(all_old_files_unchanged=True,protected_files=len(protected),
    saved_baselines_analyzed=4,existing_step_changes_analyzed=25,new_D_estimates=0,new_encoder_calls=0,new_experiments=0,threshold_changes=0))
print(json.dumps(dict(baseline_diagnostics=[{k:d[k] for k in ['scene','n_aircraft','baseline_r_squared','baseline_reason']} for d in baseline_details],effects=effects),indent=2))
