"""Apply archived QC500 Holding cutoffs to both saved terminal-control arms.

No Encoder, trajectory generator, D estimator or peak selector is imported.
"""
from pathlib import Path
from datetime import datetime,timedelta
import csv,hashlib,json,sys
from evaluation_runtime import REPO, RUNS, new_output
R=None; B=RUNS; SOURCE=RUNS/'holding-equal-duration'; OLD=RUNS/'strict-10s-reference/results'
import numpy as np
from scipy.stats import rankdata,spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf8')
def med(x):
    v=[float(a) for a in x if a is not None]
    return float(np.median(v)) if v else None
def ok(p):return p['status']=='ok' and p['dimension'] is not None and bool(np.isfinite(p['dimension']))
def fmt(x,d=3):return 'NA' if x is None else f'{x:+.{d}f}'
def local(s):return (datetime.strptime(s,'%Y-%m-%dT%HZ')+timedelta(hours=8)).strftime('%m-%d %H:%M')
def corr(curve):
    valid=[p for p in curve if ok(p)]
    rho=None;reason=None
    if len(valid)<5:reason='fewer_than_5_valid_doses'
    elif len({p['dimension'] for p in valid})<2:reason='constant_D'
    else:
        x=[p['injected_aircraft'] for p in valid];y=[p['dimension'] for p in valid]
        rho=float(spearmanr(x,y).statistic)
        independent=float(np.corrcoef(rankdata(x),rankdata(y))[0,1])
        assert np.isfinite(rho) and abs(rho-independent)<1e-12
    return dict(rho=rho,reason=reason,total=len(curve),valid=len(valid))
def describe(x):
    x=[float(v) for v in x if v is not None]
    return dict(n=len(x),median=med(x),positive=sum(v>0 for v in x),negative=sum(v<0 for v in x),zero=sum(v==0 for v in x))
def aggregate(rows,key):return {arm:describe([r[key][arm]['rho'] for r in rows]) for arm in ['holding','straight']}

def main():
    out=R/'results';out.mkdir(exist_ok=False)
    protected={str(p):sha(p) for folder in [SOURCE,OLD] for p in folder.rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    write(R/'before-hashes.json',protected)
    old=read(OLD/'summary.json')['qc500']['holding']
    oldmanifest=read(OLD/'analysis-manifest.json')
    assert sha(OLD/'experiment-results.json')==oldmanifest['input_sha256']['experiment-results.json']
    cutoff={s['scene_id']:s['cutoff'] for s in old['scenes']}
    # Check archived selection rows without running the old peak selector.
    with (OLD/'qc500-holding-point-selection.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            c=cutoff[r['scene_id']]
            assert (int(r['cutoff']) if r['cutoff'] else None)==c
            assert (r['within_retained_range']=='True')==(c is not None and int(r['dose'])<=c)
    data=read(SOURCE/'results/experiment-results.json');full_summary=read(SOURCE/'results/summary.json')
    assert set(cutoff)=={t['scene'] for t in data}
    policy=dict(cutoff_source=str(OLD/'summary.json'),cutoff_source_variant='qc500.holding.scenes[].cutoff',
        cutoff_source_sha256=sha(OLD/'summary.json'),cutoffs=cutoff,cutoff_units='integer number of injected aircraft; not a fractional remapping',
        inclusion='0 <= dose <= archived cutoff, including cutoff; same cutoff in both arms and all five orders',
        missing_cutoff='No retained analysis and no fallback cutoff; complete results remain preserved',
        cutoff_origin='Previously selected peaks of midpoint Holding curves; imported unchanged, not reselected from terminal Holding or Straight',
        correlation='Existing status=ok finite D, at least five valid doses, nonconstant D; Spearman rho',
        comparison='Report own-valid subsets separately; primary paired correlations use identical jointly valid doses',
        D_difference='Holding minus Straight at same scene/order/dose, both valid; exclude dose zero when summarizing differences',
        baseline_changes='Require valid common zero-dose baseline, as well as both arm D values at the compared dose',
        summary='Within-order median difference, then median across orders, then equal-scene median; descriptive, no independent-repeat assumption',
        limits='Shared archived outcome-selected cutoffs remove separate-arm peak selection but do not establish a physical operating limit; old midpoint versus new endpoint placement differs',
        restrictions=dict(new_Encoder_calls=0,new_D_estimates=0,new_trajectories=0,new_experiments=0,new_peak_searches=0,threshold_changes=0))
    write(R/'policy.json',policy)
    rows=[];points=[];scenes=[]
    old_scene={s['scene_id']:s for s in old['scenes']}
    for t in data:
        sid=t['scene'];c=cutoff[sid];hc=t['curves']['holding'];sc=t['curves']['straight']
        assert len(hc)==len(sc)==t['n_eligible']+1 and t['n_aircraft']==old_scene[sid]['n_aircraft']
        assert t['n_eligible']==t['n_aircraft']
        assert all(p['injected_aircraft']==i for i,p in enumerate(hc)) and all(p['injected_aircraft']==i for i,p in enumerate(sc))
        if c is not None:assert 0<=c<len(hc)
        assert hc[0]['dimension']==sc[0]['dimension']==old_scene[sid]['baseline_D']
        baseline=hc[0]['dimension'] if ok(hc[0]) else None
        kept_h=hc[:c+1] if c is not None else [];kept_s=sc[:c+1] if c is not None else []
        joint=[(h,s) for h,s in zip(kept_h,kept_s) if ok(h) and ok(s)]
        full_joint=[(h,s) for h,s in zip(hc,sc) if ok(h) and ok(s)]
        own={arm:corr(v) for arm,v in [('holding',kept_h),('straight',kept_s)]}
        shared={arm:corr([p[j] for p in joint]) for j,arm in enumerate(['holding','straight'])}
        full={arm:corr([p[j] for p in full_joint]) for j,arm in enumerate(['holding','straight'])}
        for j,arm in enumerate(['holding','straight']):
            assert corr([hc,sc][j])==t['correlations'][arm]
        if c is None:
            for v in [own,shared]:
                for arm in v:v[arm]['reason']='no_archived_cutoff'
        differences=[];changes={'holding':[],'straight':[]}
        for h,s in zip(hc,sc):
            dose=h['injected_aircraft'];retained=c is not None and dose<=c;valid=ok(h) and ok(s)
            delta=h['dimension']-s['dimension'] if valid else None
            dh=h['dimension']-baseline if valid and baseline is not None else None
            ds=s['dimension']-baseline if valid and baseline is not None else None
            point=dict(scene=sid,replicate=t['replicate'],dose=dose,cutoff=c,within_retained_range=retained,
                holding_valid=ok(h),straight_valid=ok(s),jointly_valid=valid,holding_D=h['dimension'],straight_D=s['dimension'],
                holding_reason=h['reason'],straight_reason=s['reason'],holding_minus_straight=delta,
                holding_minus_baseline=dh,straight_minus_baseline=ds,
                used_in_paired_difference_summary=bool(retained and valid and dose>0),
                used_in_paired_rho=bool(retained and valid and shared['holding']['rho'] is not None and shared['straight']['rho'] is not None),
                range_exclusion='no_archived_cutoff' if c is None else ('after_archived_cutoff' if not retained else None))
            points.append(point)
            if retained and valid and dose>0:
                differences.append(delta)
                if baseline is not None:changes['holding'].append(dh);changes['straight'].append(ds)
        rows.append(dict(scene=sid,replicate=t['replicate'],cutoff=c,baseline_D=baseline,
            own_valid=own,common_valid=shared,full_common_valid=full,joint_nonzero_doses=len(differences),
            paired_difference_median=med(differences),baseline_changes={arm:med(v) for arm,v in changes.items()}))
    for sid in cutoff:
        rr=[r for r in rows if r['scene']==sid]
        scenes.append(dict(scene=sid,local_UTC8=local(sid),N=old_scene[sid]['n_aircraft'],cutoff=cutoff[sid],
            baseline_D=rr[0]['baseline_D'],own_valid=aggregate(rr,'own_valid'),common_valid=aggregate(rr,'common_valid'),
            joint_nonzero_doses=sum(r['joint_nonzero_doses'] for r in rr),
            paired_difference_median=med([r['paired_difference_median'] for r in rr]),
            baseline_changes={arm:med([r['baseline_changes'][arm] for r in rr]) for arm in ['holding','straight']}))
    matched=[r for r in rows if all(r['common_valid'][a]['rho'] is not None for a in ['holding','straight'])]
    matched_baseline=[r for r in matched if r['baseline_D'] is not None]
    base=[r for r in rows if r['baseline_D'] is not None]
    eligible_scenes=[s for s in scenes if s['paired_difference_median'] is not None]
    baseline_scenes=[s for s in eligible_scenes if s['baseline_D'] is not None]
    summary=dict(scenes=12,scenes_with_archived_cutoff=sum(c is not None for c in cutoff.values()),
        common_valid=aggregate(rows,'common_valid'),own_valid=aggregate(rows,'own_valid'),
        baseline_valid_common=aggregate(base,'common_valid'),
        same_curve_full_vs_retained=dict(curves=len(matched),full=aggregate(matched,'full_common_valid'),retained=aggregate(matched,'common_valid')),
        same_baseline_curve_full_vs_retained=dict(curves=len(matched_baseline),full=aggregate(matched_baseline,'full_common_valid'),retained=aggregate(matched_baseline,'common_valid')),
        equal_scene_rho={arm:describe([s['common_valid'][arm]['median'] for s in scenes]) for arm in ['holding','straight']},
        paired_difference=dict(scenes=len(eligible_scenes),positive_scene_medians=sum(s['paired_difference_median']>0 for s in eligible_scenes),
            equal_scene_median=med([s['paired_difference_median'] for s in eligible_scenes]),
            joint_nonzero_records=sum(s['joint_nonzero_doses'] for s in scenes)),
        baseline_valid_paired_difference=dict(scenes=len(baseline_scenes),positive_scene_medians=sum(s['paired_difference_median']>0 for s in baseline_scenes),
            equal_scene_median=med([s['paired_difference_median'] for s in baseline_scenes])),
        scene_details=scenes)
    # Previously reported full-range shared-dose medians/counts must match exactly.
    fullcheck=aggregate(rows,'full_common_valid')
    for arm in fullcheck:
        assert fullcheck[arm]['n']==full_summary['common_correlations'][arm]['valid']
        assert fullcheck[arm]['median']==full_summary['common_correlations'][arm]['median']
    write(out/'summary.json',summary);write(out/'repeat-summary.json',rows);write(out/'point-selection.json',points)
    figures=R/'figures';figures.mkdir(exist_ok=False)
    chosen=[s for s in scenes if s['cutoff'] is not None]
    plt.rcParams.update({'font.size':10,'axes.titlesize':11,'axes.labelsize':10})
    colors={'holding':'#2166ac','straight':'#d66016'}
    for kind in ['curves','difference']:
        fig,axes=plt.subplots(4,2,figsize=(13,14),layout='constrained')
        for ax,s in zip(axes.flat,chosen):
            pp=[p for p in points if p['scene']==s['scene']];n=s['N']
            x=np.arange(n+1);cut=s['cutoff']
            arms=['holding','straight'] if kind=='curves' else ['difference']
            for arm in arms:
                key=arm+'_D' if arm!='difference' else 'holding_minus_straight'
                color=colors.get(arm,'#59469c')
                matrix=np.array([[p[key] if p['jointly_valid'] else np.nan for p in pp if p['replicate']==rep] for rep in range(5)])
                counts=np.isfinite(matrix).sum(axis=0)
                mean=np.divide(np.nansum(matrix,axis=0),counts,out=np.full(n+1,np.nan),where=counts>0)
                ax.plot(x,mean,color=color,alpha=.35,lw=1.2,ls='--')
                for row in matrix:ax.plot(x[:cut+1],row[:cut+1],color=color,alpha=.2,lw=.7)
                ax.plot(x[:cut+1],mean[:cut+1],color=color,lw=2,label=arm.title() if arm!='difference' else 'Holding − Straight')
            ax.axvline(cut,color='#444444',ls=':',lw=1.2)
            ax.axvspan(cut,n,color='gray',alpha=.09)
            if kind=='difference':ax.axhline(0,color='black',lw=.7,ls='--')
            ax.set_title(f"{s['local_UTC8']} UTC+08 | N={n} | archived cutoff={cut}\nShared-dose rho: H {fmt(s['common_valid']['holding']['median'])}, S {fmt(s['common_valid']['straight']['median'])}")
            ax.set(xlabel='Aircraft with +240 s appended',ylabel='Accepted D' if kind=='curves' else 'D(Holding) − D(Straight)',xlim=(0,n))
            ax.grid(alpha=.2)
        axes.flat[-1].axis('off')
        handles,labels=axes.flat[0].get_legend_handles_labels();axes.flat[-1].legend(handles,labels,loc='upper left')
        axes.flat[-1].text(0,.72,'Bold: retained available-order mean\nThin: retained matched orders\nDashed: saved full-range mean\nDotted vertical line: archived cutoff\n\nBoth D values must pass at each point.\nFive scenes have no archived cutoff;\nno fallback range was assigned.\nThe full data are unchanged.',transform=axes.flat[-1].transAxes,va='top',fontsize=11,linespacing=1.5)
        fig.suptitle('Equal-duration control at the SAME archived Holding cutoffs\nNo new peak search; missing D remains missing',fontsize=16)
        for ext in ['png','svg']:fig.savefig(figures/f'shared-cutoff-{kind}.{ext}',dpi=180)
        plt.close(fig)
    lines=['# Equal-duration Holding control at archived common cutoffs','',
        'This analysis uses only the saved terminal-append control results. Both arms receive exactly the archived QC500, strict-10-second, midpoint-Holding cutoff for each scene, including its endpoint. No trajectory generation, model inference, D estimation, threshold change, or new peak selection was performed. Complete prior results remain unchanged.','',
        '## Cutoff provenance','',
        'The cutoffs were read from `evaluation-10s/workspace/evaluation/results/summary.json`, under `qc500.holding.scenes`, and cross-checked against the archived point-selection CSV. Counts are used directly, not rescaled fractions. The source populations match the current control populations. Five scenes have no archived cutoff; they receive no retained-range estimate or replacement cutoff.','',
        '| Scene UTC+08 | Background N | Archived cutoff (aircraft) |','|---|---:|---:|']
    lines += [f"| {s['local_UTC8']} | {s['N']} | {s['cutoff'] if s['cutoff'] is not None else 'Unavailable'} |" for s in scenes]
    lines += ['', '## Correlation results','',
        'Primary comparisons use identical doses where BOTH D values are accepted. Each arm\'s own valid-dose subset is also recorded in the machine-readable output; it is not substituted for the matched comparison. The unchanged minimum is five accepted doses per correlation.','',
        '| Comparison | Holding median rho | Straight median rho | Matched orders |', '|---|---:|---:|---:|']
    for label,values in [('Archived cutoff: all computable',summary['common_valid']),('Archived cutoff: baseline-valid scenes',summary['baseline_valid_common']),('Full range: same orders as retained analysis',summary['same_curve_full_vs_retained']['full'])]:
        lines.append(f"| {label} | {fmt(values['holding']['median'])} | {fmt(values['straight']['median'])} | {values['holding']['n']} |")
    lines += ['', 'A matched order is a within-scene repeat, not an independent scene. Full-versus-retained comparisons above keep the same order identifiers; within an order, the full range naturally contains more doses. No confirmatory p-values are claimed.','',
        '| Scene UTC+08 | Cutoff | Common rho H | Common rho S | Joint nonzero records | Median D(H) − D(S) |','|---|---:|---:|---:|---:|---:|']
    for s in chosen:
        lines.append(f"| {s['local_UTC8']} | {s['cutoff']} | {fmt(s['common_valid']['holding']['median'])} | {fmt(s['common_valid']['straight']['median'])} | {s['joint_nonzero_doses']} | {fmt(s['paired_difference_median'],5)} |")
    pd=summary['paired_difference'];bp=summary['baseline_valid_paired_difference']
    lines += ['',f"Among {pd['scenes']} scenes with retained paired differences, {pd['positive_scene_medians']} have positive scene medians. The equal-scene median difference is {fmt(pd['equal_scene_median'],5)}. Among {bp['scenes']} baseline-valid scenes, {bp['positive_scene_medians']} have positive scene medians and the corresponding median difference is {fmt(bp['equal_scene_median'],5)}.",'',
        'Difference aggregation: median over accepted nonzero doses within each order, then median across orders within a scene, then median across scenes. Dose zero is excluded from difference summaries. Baseline-relative changes are provided only for baseline-valid scenes; D failures are never filled with zero.','',
        '## What this comparison establishes','',
        'A common archived cutoff prevents choosing a favorable peak independently for each arm. Stronger prefix correlations in both arms show that early-dose growth is not unique to Holding. A positive paired D difference at equal duration and point count supports sensitivity to route geometry/location beyond those two matched properties. A higher D than Straight and a strong dose correlation are different claims.','',
        'The experiment does not isolate pure sequence-length contribution: straight continuation also changes trajectory position and spatial extent. It cannot assign a percentage of the old Holding response to length. The imported cutoffs were originally chosen using midpoint Holding outcomes; they were not independently established physical limits. Applying them without reselection to the terminal experiment does not remove that provenance or make this an independent validation dataset.','',
        'Only three original scenes have valid zero-dose D. Correlations remain conditional on the unchanged D quality gates and available jointly valid doses. These limitations, the shared cutoffs, and both-arm results should accompany any paper claim.','',
        '![Both arms and archived cutoffs](figures/shared-cutoff-curves.png)','',
        '![Paired differences at archived cutoffs](figures/shared-cutoff-difference.png)','',
        '## Saved evidence','',
        '- `policy.json`: immutable cutoff source, exact values, inclusion and missing-cutoff policy.',
        '- `results/summary.json`: scene and aggregate statistics, including matched-order full-range comparison.',
        '- `results/repeat-summary.json`: own-valid and common-valid correlations for each order.',
        '- `results/point-selection.json`: all original dose pairs, retained flags, D values, reasons and differences.',
        '- `verification.json`: source preservation, archived cutoff checks and independent rank-correlation verification.','']
    (R/'report.md').write_text('\n'.join(lines),encoding='utf8')
    assert all(sha(p)==value for p,value in protected.items())
    write(R/'verification.json',dict(old_files_unchanged=True,protected_files=len(protected),
        archived_cutoffs_match_saved_summary_and_CSV=True,original_pair_records_preserved=len(points),
        full_range_shared_correlations_match_previous=True,correlations_checked_by_independent_rank_calculation=True,
        no_new_D_estimates=True,no_new_encoder_calls=True,no_new_trajectories=True,no_peak_search=True,
        threshold_changes=0,source_sha256={str(p):sha(p) for p in [SOURCE/'results/experiment-results.json',SOURCE/'results/summary.json',OLD/'summary.json',OLD/'qc500-holding-point-selection.csv']},
        analysis_sha256=sha(Path(__file__))))
    print(json.dumps({k:v for k,v in summary.items() if k!='scene_details'},indent=2))
    print(json.dumps(scenes,indent=2))

def cli(argv=None):
    import argparse
    global R,SOURCE,OLD
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--control',type=Path,default=SOURCE)
    ap.add_argument('--reference',type=Path,default=OLD.parent)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(argv);SOURCE=args.control.resolve();OLD=args.reference.resolve()/'results'
    if not (SOURCE/'results/experiment-results.json').is_file() or not (OLD/'summary.json').is_file():
        ap.error('Control results and historical reference summary are required')
    R=new_output(args.output)
    main()

if __name__=='__main__':cli()
