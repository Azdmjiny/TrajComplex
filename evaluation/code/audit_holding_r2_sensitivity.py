"""Apply a disclosed R2=0.94 sensitivity gate to saved midpoint fits.

No refitting, resampling, or changed cutoffs. Original acceptance is preserved.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from plot_holding_midpoint_response import ROOT, sha, label


def rho(x,y):
    valid=np.isfinite(y)
    if valid.sum()<5 or np.ptp(y[valid])==0:return None
    return float(spearmanr(x[valid],y[valid]).statistic)


def stats(values):
    v=[x for x in values if x is not None]
    return dict(n=len(v),positive=sum(x>0 for x in v),median=float(np.median(v)) if v else None)


def run(out):
    folder=ROOT/'runs/strict-10s-reference/results'
    files=[folder/x for x in ['experiment-results.json','summary.json','run-manifest.json']]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    raw,summary,manifest=[json.loads(p.read_text(encoding='utf8')) for p in files]
    assert manifest['config']['min_r_squared']==.98
    new_config=dict(manifest['config'],min_r_squared=.94)
    runs=raw['qc500']['holding']['scenes'];summary=summary['qc500']['holding']
    scenes=[];records=[];aggregates={f'{gate}_{scope}':[] for gate in ['old','sensitivity'] for scope in ['full','retained']}
    for s in summary['scenes']:
        rows=sorted([r for r in runs if r['scene_id']==s['scene_id']],key=lambda r:r['replicate'])
        counts=[0,0];arrays=[[],[]];rs={key:[] for key in aggregates}
        for row in rows:
            xs=[];old=[];new=[]
            for p in row['dose_curve']:
                original=p['status']=='ok'
                recovered=(p['reason']=='poor_linear_fit' and p['r_squared'] is not None and p['r_squared']>=.94
                           and p['slope'] is not None and p['slope']>0)
                accepted=original or recovered
                # Recover only fits that reached the final R2 gate; all upstream failures stay rejected.
                if recovered:
                    assert p['n_samples']>=new_config['min_samples']
                    assert p['n_fit_scales']>=new_config['min_fit_points']
                    assert p['fit_radius_range'][1]/p['fit_radius_range'][0]>=new_config['min_radius_ratio']
                x=p['holding_aircraft'];xs.append(x)
                old.append(p['dimension'] if original else np.nan)
                new.append(p['dimension'] if original else p['slope'] if recovered else np.nan)
                counts[0]+=original;counts[1]+=accepted
                records.append(dict(scene=s['scene_id'],replicate=row['replicate'],dose=x,
                                    original_status=p['status'],original_reason=p['reason'],
                                    r_squared=p['r_squared'],sensitivity_accepted=accepted,
                                    sensitivity_dimension=new[-1] if accepted else None,
                                    newly_accepted=recovered))
            x=np.array(xs);a=np.array(old);b=np.array(new);arrays[0].append(a);arrays[1].append(b)
            for gate,values in [('old',a),('sensitivity',b)]:
                for scope in ['full','retained']:
                    if scope=='retained' and s['cutoff'] is None:continue
                    mask=np.ones(len(x),bool) if scope=='full' else x<=s['cutoff']
                    v=rho(x[mask],values[mask]);rs[f'{gate}_{scope}'].append(v);aggregates[f'{gate}_{scope}'].append(v)
        diag={}
        for gate,arr in zip(['old','sensitivity'],arrays):
            y=np.array(arr)
            if s['cutoff'] is None:continue
            y=y[:,:s['cutoff']+1]
            m=np.array([np.mean(c[np.isfinite(c)]) if np.isfinite(c).any() else np.nan for c in y.T])
            valid_steps=np.isfinite(m[:-1])&np.isfinite(m[1:]);diff=np.diff(m)
            diag[gate]=dict(valid_adjacent_steps=int(valid_steps.sum()),downward_steps=int(np.sum(diff[valid_steps]<0)),
                            mean_absolute_step=float(np.mean(np.abs(diff[valid_steps]))) if valid_steps.any() else None,
                            complete_orders=int(np.isfinite(y).all(axis=1).sum()))
        scenes.append(dict(scene=s['scene_id'],local=label(s),N=s['n_aircraft'],cutoff=s['cutoff'],
                           attempts=sum(len(r['dose_curve']) for r in rows),old_accepted=counts[0],sensitivity_accepted=counts[1],
                           old_baseline=bool(np.isfinite(arrays[0][0][0])),sensitivity_baseline=bool(np.isfinite(arrays[1][0][0])),
                           correlations={key:stats(v) for key,v in rs.items()},roughness=diag))
    totals=dict(attempts=len(records),old_accepted=sum(r['old_accepted'] for r in scenes),
                sensitivity_accepted=sum(r['sensitivity_accepted'] for r in scenes),
                old_baselines=sum(r['old_baseline'] for r in scenes),sensitivity_baselines=sum(r['sensitivity_baseline'] for r in scenes),
                correlations={key:stats(v) for key,v in aggregates.items()})
    for key in ['full','retained']:
        assert np.isclose(totals['correlations']['old_'+key]['median'],summary['all'][key]['median'])
    result=dict(scope='Saved adaptive-scale midpoint fits re-screened at R2 >= 0.94; not a fixed-scale diagnostic',
                threshold_basis='Existing 0.94 policy in the other repository studies; engineering sensitivity, not proof of a universally valid cutoff',
                old_config=manifest['config'],sensitivity_config=new_config,totals=totals,scenes=scenes)
    (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf8')
    (out/'screened-fit-records.json').write_text(json.dumps(records,indent=2,allow_nan=False)+'\n',encoding='utf8')
    fmt=lambda x:'NA' if x is None else f'{x:.3f}'
    table='\n'.join(f'| {s["local"]} | {s["N"]} | {s["old_accepted"]}/{s["attempts"]} | {s["sensitivity_accepted"]}/{s["attempts"]} | {fmt(s["correlations"]["old_retained"]["median"])} | {fmt(s["correlations"]["sensitivity_retained"]["median"])} |' for s in scenes)
    report='''# Holding R² threshold sensitivity — saved fits only

Only the final fit-quality threshold changes, from R² >= 0.98 to R² >= 0.94. The original source records, primary reports, thresholds and cutoffs remain unchanged. This is a separate local sensitivity analysis authorized to assess greater acceptance, not a replacement selected for its correlation.

The 0.94 value has an existing engineering precedent in the other evaluation studies. It is not a literature-derived guarantee of dimension validity, nor a minimum optimized to produce positive correlations. No threshold below 0.94 is searched. Aircraft QC, N>=30, >=8 fitting scales, >=10 pairs, C(r) in [0.02,0.3], radius ratio >=2, grid and five injection orders remain unchanged.

Only records originally rejected for poor_linear_fit, with saved positive slopes and R² >= 0.94, are recovered. No position imputation or new trajectory is introduced. The archived adaptive fit windows stay as they were. This is NOT the proposed fixed-scale recomputation; candidate aircraft counts do not change.

'''+f'Accepted order-dose fits: {totals["old_accepted"]}/{totals["attempts"]} -> {totals["sensitivity_accepted"]}/{totals["attempts"]}. Accepted baselines: {totals["old_baselines"]}/12 -> {totals["sensitivity_baselines"]}/12. Baseline repetitions across five orders are not independent fits.\n\n'+'''| Local UTC+08 | N | Accepted at 0.98 | Accepted at 0.94 | Original pre-peak median order rho | Sensitivity pre-peak median order rho |
|---|---:|---:|---:|---:|---:|
'''+table+'\n\n## Aggregate correlations\n\n'
    for key,value in totals['correlations'].items():report+=f'- {key}: {value["positive"]}/{value["n"]} positive; median {fmt(value["median"])}.\n'
    report+='''
All old peak cutoffs remain unchanged and outcome-selected; no peak is assigned to a scene that lacked one. Increased availability changes the set of included dose points and may change correlations in either direction. Fit R² is linearity of log C(r) versus log radius; it is not the dose–D Spearman coefficient. Lower R² does not mathematically imply stronger dose response.

No new D fit, Encoder call, repetition, fixed-scale calculation or Git push was performed. Saved slopes are reclassified under the explicit sensitivity gate, with original statuses preserved alongside them. Derived records remain local. Further fixed-scale computation must preserve its own documented gates and report failures rather than search for a more favorable range.
'''
    (out/'report.md').write_text(report,encoding='utf8')
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    (out/'manifest.json').write_text(json.dumps(dict(source_sha256=hashes,new_D_fits=0,new_encoder_calls=0,new_draws=0,changed_cutoffs=0,sensitivity_r_squared=.94),indent=2)+'\n',encoding='utf8')
    print(json.dumps(totals,indent=2));print('SCENE DETAILS',json.dumps(scenes,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Choose a new directory; old results are protected.')
    a.output.mkdir(parents=True);run(a.output)
