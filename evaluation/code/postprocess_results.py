"""Aggregate saved dose records only: no Encoder, trajectory generation or D estimation.

The Holding aggregation is migrated from the original published analysis;
Vectoring uses the same accepted-D and correlation rules. No threshold changes.
"""
from pathlib import Path
from datetime import datetime, timedelta
import collections, json, shutil, hashlib
import numpy as np
from scipy.stats import rankdata
from truncation import finite_ok, curve_correlation
from evaluation_runtime import new_output

def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def write(p, value):
    Path(p).write_text(json.dumps(value,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n',encoding='utf8')

def med(x):
    x=[v for v in x if v is not None]
    return float(np.median(x)) if x else None
def fmt(x,dec=3):return 'NA' if x is None else f'{x:+.{dec}f}'
def local(s):return (datetime.strptime(s,'%Y-%m-%dT%HZ')+timedelta(hours=8)).strftime('%m-%d %H:%M')
def independent_rho(curve):
    rows=[p for p in curve if finite_ok(p)]
    if len(rows)<5 or len({p['dimension'] for p in rows})<2:return None
    return float(np.corrcoef(rankdata([p['injected_aircraft'] for p in rows]),rankdata([p['dimension'] for p in rows]))[0,1])
def rho_summary(values):
    values=[v for v in values if v is not None]
    return dict(valid=len(values),positive=sum(v>0 for v in values),negative=sum(v<0 for v in values),zero=sum(v==0 for v in values),median=med(values))

def holding_summaries(root):
    root=Path(root)
    results=read(root/'results/experiment-results.json')
    assignments=read(root/'assignments.json')
    manifest=read(root/'results/run-manifest.json')
    if manifest['state']!='complete': raise ValueError('Cannot summarize an incomplete run')
    repeat_rows=[]; pair_rows=[]; scene_rows=[]
    for selection in assignments:
        sid=selection["scene"]; trials=[t for t in results if t["scene"]==sid]
        for t in trials:
            hc=t['curves']['holding']; sc=t['curves']['straight']
            assert len(hc)==len(sc)
            jointly=[(h,s) for h,s in zip(hc,sc) if finite_ok(h) and finite_ok(s)]
            common={arm:curve_correlation([p[0 if arm=='holding' else 1] for p in jointly],'injected_aircraft') for arm in ['holding','straight']}
            for arm in ['holding','straight']:
                r=independent_rho([p[0 if arm=='holding' else 1] for p in jointly]); cr=common[arm]['rho']
                assert (r is None and cr is None) or (r is not None and cr is not None and abs(r-cr)<1e-12)
            excess=[]; dh=[]; ds=[]; baseline=hc[0]['dimension'] if finite_ok(hc[0]) else None
            for h,s in zip(hc,sc):
                k=h['injected_aircraft']; assert k==s['injected_aircraft']
                valid=finite_ok(h) and finite_ok(s)
                delta=h['dimension']-s['dimension'] if valid else None
                delta_h=h['dimension']-baseline if valid and baseline is not None else None
                delta_s=s['dimension']-baseline if valid and baseline is not None else None
                pair_rows.append(dict(scene=sid,replicate=t['replicate'],dose=k,holding_status=h['status'],holding_reason=h['reason'],
                    straight_status=s['status'],straight_reason=s['reason'],holding_D=h['dimension'],straight_D=s['dimension'],
                    jointly_valid=valid,holding_minus_straight=delta,holding_minus_baseline=delta_h,straight_minus_baseline=delta_s))
                if k>0 and valid:
                    excess.append(delta)
                    if baseline is not None: dh.append(delta_h); ds.append(delta_s)
            repeat_rows.append(dict(scene=sid,replicate=t['replicate'],baseline_D=baseline,
                arm_correlations=t['correlations'],common_correlations=common,
                joint_nonzero_doses=len(excess),paired_excess_median=med(excess),
                holding_baseline_change_median=med(dh),straight_baseline_change_median=med(ds),
                endpoint_excess=hc[-1]['dimension']-sc[-1]['dimension'] if finite_ok(hc[-1]) and finite_ok(sc[-1]) else None))
        rr=[r for r in repeat_rows if r['scene']==sid]
        pairs=[p for p in pair_rows if p['scene']==sid and p['dose']>0 and p['jointly_valid']]
        valid_counts={arm:sum(finite_ok(p) for t in trials for p in t['curves'][arm]) for arm in ['holding','straight']}
        scene_rows.append(dict(scene=sid,local_UTC8=local(sid),n_aircraft=trials[0]['n_aircraft'],eligible=trials[0]['n_eligible'],
            baseline_D=rr[0]['baseline_D'],baseline_reason=trials[0]['curves']['holding'][0]['reason'],
            dose_records_per_arm=sum(len(t['curves']['holding']) for t in trials),valid_counts=valid_counts,
            arm_correlations={arm:rho_summary([r['arm_correlations'][arm]['rho'] for r in rr]) for arm in ['holding','straight']},
            common_correlations={arm:rho_summary([r['common_correlations'][arm]['rho'] for r in rr]) for arm in ['holding','straight']},
            joint_nonzero_doses=len(pairs),paired_excess_median=med([r['paired_excess_median'] for r in rr]),
            holding_baseline_change_median=med([r['holding_baseline_change_median'] for r in rr]),
            straight_baseline_change_median=med([r['straight_baseline_change_median'] for r in rr]),
            endpoint_excess=rr[0]['endpoint_excess']))
    valid_scenes=[s for s in scene_rows if s['paired_excess_median'] is not None]
    baseline_scenes=[s for s in scene_rows if s['baseline_D'] is not None]
    counts={arm:dict(collections.Counter(p['reason'] or 'ok' for t in results for p in t['curves'][arm])) for arm in ['holding','straight']}
    summary=dict(scenes=len(scene_rows),background=manifest['n_background'],pair_eligible=manifest['n_eligible'],baseline_valid_scenes=len(baseline_scenes),
        arm_counts=counts,arm_correlations={arm:rho_summary([r['arm_correlations'][arm]['rho'] for r in repeat_rows]) for arm in ['holding','straight']},
        common_correlations={arm:rho_summary([r['common_correlations'][arm]['rho'] for r in repeat_rows]) for arm in ['holding','straight']},
        baseline_ok_common_correlations={arm:rho_summary([r['common_correlations'][arm]['rho'] for r in repeat_rows if r['baseline_D'] is not None]) for arm in ['holding','straight']},
        joint_nonzero_doses=sum(r['joint_nonzero_doses'] for r in repeat_rows),
        scenes_with_paired_data=len(valid_scenes),scenes_positive_paired_median=sum(s['paired_excess_median']>0 for s in valid_scenes),
        equal_scene_median_paired_excess=med([s['paired_excess_median'] for s in valid_scenes]),
        baseline_ok_scene_median_paired_excess=med([s['paired_excess_median'] for s in baseline_scenes]),
        baseline_ok_scene_median_changes={arm:med([s[arm+'_baseline_change_median'] for s in baseline_scenes]) for arm in ['holding','straight']},
        aggregation='Median across scenes of medians across repeats of medians across jointly valid nonzero doses; no independence claim',
        scene_details=scene_rows)
    return {'summary.json':summary,'paired-dose-records.json':pair_rows,'repeat-summary.json':repeat_rows}

def vectoring_summaries(root):
    from run_analysis import summarize
    root=Path(root)
    manifest=read(root/'results/run-manifest.json')
    if manifest['state']!='complete': raise ValueError('Cannot summarize an incomplete run')
    trials=read(root/'results/experiment-results.json')['qc500_safe']['vectoring']['scenes']
    summary,selection=summarize(trials,'vectoring',truncate=False)
    scene_results=[]
    for scene in manifest['scenes']:
        tt=[t for t in trials if t['scene_id']==scene]
        pp=[p for t in tt for p in t['dose_curve']]
        rho=[c['rho'] for t in tt if (c:=curve_correlation(t['dose_curve'],'vectoring_aircraft'))['rho'] is not None]
        rs=[p['r_squared'] for p in pp if p['r_squared'] is not None]
        local_time=(datetime.strptime(scene,'%Y-%m-%dT%HZ')+timedelta(hours=8)).strftime('%Y-%m-%d %H:00')
        scene_results.append(dict(scene=scene,local_time=local_time,n_aircraft=tt[0]['n_aircraft'],eligible=tt[0]['n_vectoring_eligible'],
            attempted_D=len(pp),valid_D=int(sum(finite_ok(p) for p in pp)),D_reasons=dict(collections.Counter(p['reason'] or 'ok' for p in pp)),
            r_squared_range=[min(rs),max(rs)] if rs else [None,None],baseline_D=pp[0]['dimension'],baseline_r_squared=pp[0]['r_squared'],
            rho=rho,rho_median=med(rho),positive=sum(r>0 for r in rho),negative=sum(r<0 for r in rho)))
    return {'summary.json':summary,'point-selection.json':selection,'scene-summary.json':scene_results}

def process(kind,source,destination):
    """Write summaries and a run-specific report; never overwrite prior files."""
    source=Path(source).resolve();destination=Path(destination).resolve()
    from evaluation_runtime import RUNS
    if destination==RUNS.resolve() or RUNS.resolve() in destination.parents:
        raise ValueError('Published evidence is read-only')
    products=(holding_summaries if kind=='holding' else vectoring_summaries)(source)
    copies=[]
    if source!=destination:
        copies=[Path('results/experiment-results.json'),Path('results/run-manifest.json'),Path('assignments.json')]
        if kind=='vectoring': copies+=list(p.relative_to(source) for p in (source/'results').glob('*-embeddings.npz'))
        copies+=[Path('policy.json')]
        if any(not (source/p).is_file() for p in copies): raise FileNotFoundError('Completed source inputs are missing')
    targets=[destination/'results'/name for name in products]+[destination/'report.md',destination/'postprocessing-manifest.json']+[destination/p for p in copies]
    if any(p.exists() for p in targets): raise FileExistsError('Postprocessing refuses to overwrite existing outputs')
    (destination/'results').mkdir(parents=True,exist_ok=True)
    for relative in copies:
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/relative,target)
    for name,value in products.items():write(destination/'results'/name,value)
    source_files=[Path('results/experiment-results.json'),Path('results/run-manifest.json'),Path('assignments.json')]
    write(destination/'postprocessing-manifest.json',dict(kind=kind,source=str(source),
        source_sha256={p.as_posix():hashlib.sha256((source/p).read_bytes()).hexdigest() for p in source_files},
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        copied_inputs=[p.as_posix() for p in copies],derived_files=list(products),
        trajectory_generation=0,encoder_calls=0,D_estimation=0,threshold_changes=0,
        provenance='Copied execution manifests retain original paths and hashes; this separate manifest records postprocessing.'))
    lines=[f'# {kind.title()} saved-record summary','',
        'Aggregated from completed dose records. No trajectory generation, Encoder inference, D estimation, threshold change or peak selection. Invalid D remains unavailable. Orders are dependent repeats.','']
    if kind=='holding':
        s=products['summary.json']
        lines+=['| Scope | Holding median rho | Straight median rho | Matched orders |','|---|---:|---:|---:|']
        for label,key in [('Complete range','common_correlations'),('Baseline-valid scenes','baseline_ok_common_correlations')]:
            v=s[key];lines.append(f"| {label} | {fmt(v['holding']['median'])} | {fmt(v['straight']['median'])} | {v['holding']['valid']} |")
        lines+=['',f"Background: {s['background']}; pair-eligible: {s['pair_eligible']}; baseline-valid scenes: {s['baseline_valid_scenes']}. Equal-scene median Holding-minus-Straight D: {fmt(s['equal_scene_median_paired_excess'],5)}.",
            '', 'Both arms append the same duration at the endpoint. This supports a matched geometry/location comparison, not elimination of length confounding or validation of operational complexity.']
    else:
        lines+=['| Scene UTC | Background | Injectable | Accepted / attempted D | Order correlations |','|---|---:|---:|---:|---|']
        for s in products['scene-summary.json']:
            lines.append(f"| {s['scene']} | {s['n_aircraft']} | {s['eligible']} | {s['valid_D']} / {s['attempted_D']} | {', '.join(fmt(r) for r in s['rho']) or 'Unavailable'} |")
        lines+=['','All scenes and full dose ranges are retained. Route acceptance does not establish monotonic D response.']
    lines+=['','## Machine-readable outputs','']+[f'- [{name}](results/{name})' for name in products]
    (destination/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    return products

def cli(argv=None):
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('kind',choices=['holding','vectoring'])
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(argv)
    process(args.kind,args.input,new_output(args.output))

if __name__=='__main__':cli()
