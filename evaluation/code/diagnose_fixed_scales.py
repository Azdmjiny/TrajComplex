"""Fourth scene only: fixed baseline-selected scales, reject if any fails.

Reads saved embeddings and assignments. No route generation, Encoder calls,
side swaps, peak searches, or changes to production evaluation code.
"""
from pathlib import Path
import hashlib,json,sys
from collections import Counter
from evaluation_runtime import REPO, RUNS, new_output
R=None; B=RUNS; OLD=RUNS/'four-scene-vectoring-evaluation'; WS=REPO
import numpy as np
from scipy.spatial.distance import pdist
from scipy.stats import linregress,rankdata
from complexity.calculator import ComplexityConfig,estimate_complexity
from truncation import curve_correlation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SCENE='2026-09-27T05Z'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf8')
def fmt(x,n=3):return 'NA' if x is None else f'{x:+.{n}f}'
def fixed_estimate(embeddings,radii,indices,cfg):
    """Same count and OLS equations/gates; freeze indices instead of refiltering.

Do not use the existing explicit fit_range API: it intentionally replaces the
C(r) bounds, and it can filter out deficient scales. Neither is allowed here.
"""
    p=np.array(embeddings,dtype=np.float64,copy=True)
    assert cfg.normalize is False and p.ndim==2 and np.isfinite(p).all()
    n=len(p);unique=len(np.unique(p,axis=0));pair_n=n*(n-1)//2
    result=dict(status='unestimable',reason=None,dimension=None,fit_slope=None,intercept=None,r_squared=None,
        n_samples=n,n_unique=unique,n_pairs=pair_n,zero_distance_pairs=None,
        fit_indices=indices.tolist(),radii=radii.tolist(),pair_counts=[],correlation=[],failed_scales=[],
        fit_radius_range=[float(radii[indices[0]]),float(radii[indices[-1]])])
    if n<cfg.min_samples:result['reason']='insufficient_samples';return result
    if pair_n>cfg.max_pairs:raise ValueError('Existing pair-count resource limit exceeded')
    dist=pdist(p);assert np.isfinite(dist).all();dist.sort()
    result['zero_distance_pairs']=int(np.searchsorted(dist,0,side='right'))
    if not np.any(dist>0):result['reason']='collapsed_point_cloud';return result
    counts=np.searchsorted(dist,radii,side='left');C=counts/pair_n
    result['pair_counts']=counts.tolist();result['correlation']=C.tolist()
    low,high=cfg.correlation_bounds
    for j in indices:
        reasons=[]
        if counts[j]<cfg.min_pairs:reasons.append('below_min_pairs')
        if not 0<C[j]<1:reasons.append('correlation_not_in_open_unit_interval')
        if C[j]<low:reasons.append('below_correlation_lower_bound')
        if C[j]>high:reasons.append('above_correlation_upper_bound')
        if reasons:result['failed_scales'].append(dict(index=int(j),radius=float(radii[j]),pair_count=int(counts[j]),correlation=float(C[j]),reasons=reasons))
    if result['failed_scales']:
        result['reason']='fixed_scale_gate_failure';return result
    if len(indices)<cfg.min_fit_points:result['reason']='insufficient_fit_scales';return result
    selected=radii[indices]
    if np.log(selected[-1])-np.log(selected[0])<np.log(cfg.min_radius_ratio):
        result['reason']='insufficient_scale_span';return result
    x=np.log(selected);y=np.log(C[indices]);cx=x-x.mean();cy=y-y.mean()
    total=float(cy@cy)
    if total<=np.finfo(float).eps:result['reason']='flat_correlation_curve';return result
    slope=float((cx@cy)/(cx@cx));intercept=float(y.mean()-slope*x.mean())
    residual=y-(slope*x+intercept);r2=float(1-(residual@residual)/total)
    if not np.isfinite([slope,intercept,r2]).all():result['reason']='nonfinite_fit';return result
    result.update(fit_slope=slope,intercept=intercept,r_squared=r2)
    if slope<=0:result['reason']='nonpositive_slope'
    elif r2<cfg.min_r_squared:result['reason']='poor_linear_fit'
    else:result.update(status='ok',dimension=slope)
    return result

def main():
    out=R/'results';out.mkdir(exist_ok=False)
    protected={str(p):sha(p) for folder in [OLD,B/'vectoring-existing-result-diagnosis',
        B/'four-scene-vectoring-screen',B/'holding-equal-duration',B/'holding-equal-duration-old-cutoff',WS/'complexity']
        for p in folder.rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    write(R/'before-hashes.json',protected)
    saved=read(OLD/'results/experiment-results.json')['qc500_safe']['vectoring']['scenes']
    trials=[t for t in saved if t['scene_id']==SCENE];assert len(trials)==5
    assignments=next(s for s in read(OLD/'assignments.json') if s['scene']==SCENE)
    baseline=trials[0]['dose_curve'][0];assert baseline['status']=='ok'
    cfg=ComplexityConfig(normalize=False)
    assert json.loads(json.dumps(cfg.__dict__))==baseline['config']
    with np.load(OLD/'results'/(SCENE+'-embeddings.npz')) as z:
        arrays={k:z[k].copy() for k in ['baseline','left','right','radii','aircraft_ids']}
    radii=arrays['radii'];indices=np.array(baseline['fit_indices'],dtype=int)
    assert np.array_equal(radii,np.array(baseline['radii']))
    assert arrays['aircraft_ids'].tolist()==assignments['aircraft_ids']
    for t in trials:assert t['dose_curve'][0]==baseline
    policy=dict(scene=SCENE,baseline_D=baseline['dimension'],fixed_indices=indices.tolist(),
        fixed_radii=radii[indices].tolist(),fixed_scale_count=len(indices),config=cfg.__dict__,
        input_sha256={str(p):sha(p) for p in [OLD/'results'/(SCENE+'-embeddings.npz'),OLD/'results/experiment-results.json',OLD/'assignments.json']},
        decision='Always fit exactly the archived baseline fit_indices. Reject the entire D estimate if ANY fixed scale fails min_pairs, 0<C<1, or original C bounds. Retain min_samples, min_fit_points, radius span, positive slope and R2 gates.',
        original_rule='Same 64 radii, but eligible fit indices may change with dose; replay only the fourth scene to verify stored inputs',
        correlation='Same existing function: status-ok finite D, at least five valid doses; report all-valid and matched-dose comparisons; no dose cutoff',
        interpretation='Diagnostic only; a negative curve becoming unavailable is not evidence it became positive. Dropped doses change the correlation domain.',
        restrictions=dict(threshold_changes=0,encoder_calls=0,new_routes=0,side_swaps=0,first_three_scene_recalculations=0,holding_runs=0,production_code_edits=0))
    write(R/'policy.json',policy)
    records=[];summaries=[];fixed_curves=[];verified_ols=0
    for t,repeat in zip(trials,assignments['repeats']):
        assert t['replicate']==repeat['replicate'] and t['assignments']==repeat['assignments']
        current=arrays['baseline'].copy();curve=[]
        for dose,old in enumerate(t['dose_curve']):
            injected=None
            if dose:
                a=repeat['assignments'][dose-1];j=a['baseline_index']
                assert arrays['aircraft_ids'][j]==a['icao24']
                current[j]=arrays['left' if a['side']<0 else 'right'][j]
                injected=dict(icao24=a['icao24'],side='Left' if a['side']<0 else 'Right')
            replay=estimate_complexity(current,config=cfg,radii=radii,scene_id=SCENE).to_dict()
            assert json.loads(json.dumps(replay))=={k:v for k,v in old.items() if k!='vectoring_aircraft'}
            fixed=fixed_estimate(current,radii,indices,cfg)
            assert fixed['pair_counts']==old['pair_counts'] and fixed['correlation']==old['correlation']
            assert fixed['fit_indices']==baseline['fit_indices']
            if fixed['fit_slope'] is not None:
                independent=linregress(np.log(radii[indices]),np.log(np.array(fixed['correlation'])[indices]))
                assert abs(independent.slope-fixed['fit_slope'])<1e-12
                assert abs(independent.intercept-fixed['intercept'])<1e-12
                assert abs(independent.rvalue**2-fixed['r_squared'])<1e-12
                verified_ols+=1
            if old['fit_indices']==fixed['fit_indices']:
                for key in ['status','reason','dimension','fit_slope','intercept','r_squared']:assert old[key]==fixed[key]
            curve.append(dict(vectoring_aircraft=dose,**fixed))
            records.append(dict(replicate=t['replicate'],dose=dose,injected=injected,
                original=old,fixed=fixed,removed_from_original_fit=sorted(set(baseline['fit_indices'])-set(old['fit_indices'])),
                added_to_original_fit=sorted(set(old['fit_indices'])-set(baseline['fit_indices'])),
                D_fixed_minus_original=fixed['dimension']-old['dimension'] if fixed['status']=='ok' else None,
                original_step_D_change=old['dimension']-t['dose_curve'][dose-1]['dimension'] if dose else None,
                fixed_step_D_change=fixed['dimension']-curve[dose-1]['dimension'] if dose and fixed['status']=='ok' and curve[dose-1]['status']=='ok' else None))
        fixed_curves.append(dict(scene=SCENE,replicate=t['replicate'],dose_curve=curve))
        old_corr=curve_correlation(t['dose_curve'],'vectoring_aircraft');new_corr=curve_correlation(curve,'vectoring_aircraft')
        valid=[k for k,p in enumerate(curve) if p['status']=='ok']
        matched_old=curve_correlation([t['dose_curve'][k] for k in valid],'vectoring_aircraft')
        if new_corr['rho'] is not None:
            y=[curve[k]['dimension'] for k in valid]
            assert abs(float(np.corrcoef(rankdata(valid),rankdata(y))[0,1])-new_corr['rho'])<1e-12
        summaries.append(dict(replicate=t['replicate'],order=t['replicate']+1,original_correlation=old_corr,fixed_correlation=new_corr,
            original_correlation_on_fixed_valid_doses=matched_old,fixed_valid_doses=valid,
            fixed_invalid_doses=[k for k,p in enumerate(curve) if p['status']!='ok'],
            fixed_invalid_reasons=dict(Counter(p['reason'] for p in curve if p['status']!='ok'))))
    summary=dict(scene=SCENE,baseline_D=baseline['dimension'],fixed_scale_count=len(indices),
        fixed_radius_range=[float(radii[indices[0]]),float(radii[indices[-1]])],
        original_valid_records=30,fixed_valid_records=sum(r['fixed']['status']=='ok' for r in records),
        fixed_rejection_reasons=dict(Counter(r['fixed']['reason'] for r in records if r['fixed']['status']!='ok')),
        fixed_estimable_correlations=sum(s['fixed_correlation']['rho'] is not None for s in summaries),
        curves=summaries)
    write(out/'summary.json',summary);write(out/'step-comparison.json',records);write(out/'fixed-dose-curves.json',fixed_curves)
    # Independent count gate audit: every passing D retains every baseline scale.
    for r in records:
        f=r['fixed'];counts=np.array(f['pair_counts']);C=np.array(f['correlation'])
        failures=indices[(counts[indices]<cfg.min_pairs)|(C[indices]<cfg.correlation_bounds[0])|(C[indices]>cfg.correlation_bounds[1])|(C[indices]<=0)|(C[indices]>=1)]
        assert failures.tolist()==[x['index'] for x in f['failed_scales']]
        if len(failures):assert f['status']=='unestimable' and f['dimension'] is None and f['fit_slope'] is None
    figs=R/'figures';figs.mkdir(exist_ok=False)
    plt.rcParams.update({'font.size':10,'axes.labelsize':10,'axes.titlesize':11})
    fig,axes=plt.subplots(5,2,figsize=(14,15),layout='constrained',gridspec_kw={'width_ratios':[2,1]})
    for left,right,s in zip(axes[:,0],axes[:,1],summaries):
        rr=[r for r in records if r['replicate']==s['replicate']];x=np.arange(6)
        orig=np.array([r['original']['dimension'] for r in rr]);fixed=np.array([r['fixed']['dimension'] if r['fixed']['status']=='ok' else np.nan for r in rr])
        left.plot(x,orig,'o--',color='#888888',lw=1.5,label='Original changing fit scales')
        left.plot(x,fixed,'o-',color='#2166ac',lw=1.8,label='Fixed baseline fit scales')
        left.set_title(f"Order {s['order']}: original rho {fmt(s['original_correlation']['rho'])}; fixed rho {fmt(s['fixed_correlation']['rho'])}\nFixed valid doses: {s['fixed_correlation']['valid']}/6")
        labels=['Baseline']+[r['injected']['icao24']+'\n'+r['injected']['side'] for r in rr[1:]]
        left.set_xticks(x,labels);left.set_ylabel('Accepted D');left.set_ylim(1.35,1.405);left.grid(alpha=.2)
        for k in s['fixed_invalid_doses']:
            left.plot(k,.04,'x',color='#c43c39',ms=8,transform=left.get_xaxis_transform())
            left.text(k,.10,'Rejected',color='#c43c39',ha='center',fontsize=8,transform=left.get_xaxis_transform())
        right.plot(x,[r['fixed']['pair_counts'][int(indices[0])] for r in rr],'o-',color='#624b99')
        right.axhline(cfg.min_pairs,color='#c43c39',ls='--',lw=1,label='Minimum 10 pairs')
        right.set(xlabel='Injected aircraft count',ylabel='Pairs at first fixed radius',xticks=x,yticks=[8,9,10,11,12],ylim=(8.5,12.5))
        right.set_title(f"Smallest fixed radius = {radii[indices[0]]:.5f}\nC(r) also must remain at least 0.02")
        right.grid(alpha=.2)
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=2)
    fig.suptitle('September 27, 13:00 UTC+08: fixed-baseline-scale diagnostic\nSame five saved injection sequences; rejected D is not plotted as zero',fontsize=16)
    for ext in ['png','svg']:fig.savefig(figs/f'fixed-scale-comparison.{ext}',dpi=180)
    plt.close(fig)
    lines=['# Fourth-scene Vectoring: fixed baseline fitting scales','',
        'Only the saved embeddings and original left/right assignments for 2026-09-27 05:00 UTC (13:00 UTC+08) were used. The other three scenes, all previous outputs and production code were left unchanged. No Encoder inference, trajectory generation, left/right experiment, or threshold adjustment was performed.','',
        '## Exact diagnostic rule','',
        f"The baseline selected {len(indices)} radii, indexes {indices.tolist()}, spanning {radii[indices[0]]:.8f} to {radii[indices[-1]]:.8f} in embedding-distance units. These exact indexes are used at every dose and in all five orders. The baseline D remains {baseline['dimension']:.10f}.",'',
        'Every fixed scale must meet the existing count and C(r) gates: at least 10 pairs, 0 < C(r) < 1 and 0.02 <= C(r) <= 0.3. Failure of any fixed scale rejects the entire D estimate; that scale is not removed and no replacement scale is added. The existing minimum of 30 aircraft, eight scales, radius ratio 2, positive slope and R² >= 0.98 are retained.','',
        'The production explicit-radius-range option was not used because it replaces the C(r) interval gate and may remove deficient scales. A separate local diagnostic implements the original distance counts and regression equations while freezing the exact index set and enforcing every original quality bound.','',
        '## Correlations and missing estimates','',
        '| Order | Original rho, all six doses | Fixed-scale rho | Original rho on the same fixed-valid doses | Fixed-valid doses |',
        '|---|---:|---:|---:|---|']
    for s in summaries:
        lines.append(f"| {s['order']} | {fmt(s['original_correlation']['rho'])} | {fmt(s['fixed_correlation']['rho'])} | {fmt(s['original_correlation_on_fixed_valid_doses']['rho'])} | {s['fixed_valid_doses']} |")
    lines += ['',f"The original method accepted all 30 displayed dose records. The fixed-scale diagnostic accepts {summary['fixed_valid_records']} and rejects {30-summary['fixed_valid_records']}. Correlation still requires at least five accepted doses; {summary['fixed_estimable_correlations']} of five orders meet this requirement. Baseline records are shared across orders and are not independent observations.",'',
        '## Step-by-step comparison','',
        '| Order | Dose | Newly injected aircraft / side | Original D | Fixed D | Fixed − original | Rejection details |',
        '|---|---:|---|---:|---:|---:|---|']
    for r in records:
        injected='Baseline' if r['injected'] is None else r['injected']['icao24']+' / '+r['injected']['side']
        detail='; '.join(f"scale {v['index']}: {v['pair_count']} pairs, C={v['correlation']:.7f}" for v in r['fixed']['failed_scales'])
        if not detail and r['fixed']['reason']:detail=r['fixed']['reason']
        lines.append(f"| {r['replicate']+1} | {r['dose']} | {injected} | {fmt(r['original']['dimension'],6)} | {fmt(r['fixed']['dimension'],6)} | {fmt(r['D_fixed_minus_original'],6)} | {detail or '—'} |")
    lines += ['', '## Interpretation boundaries','',
        'When a right-side injection makes a baseline scale fail, the fixed-scale policy withholds D instead of discarding that scale and reporting a slope over the remainder. A previously negative correlation may therefore become unavailable, or may become positive only because later doses are no longer estimable. That is not evidence that the full-dose trajectory response has changed sign. The matched-dose original-rho column separates this missing-dose effect from changes to accepted D values.','',
        'Conversely, when the original method admits an extra small scale, this diagnostic ignores that added scale. Any accepted D difference then compares the identical embedding cloud with different fit-index sets. This diagnoses scale-selection sensitivity; it does not isolate the causal effect of aircraft choice or left/right direction.','',
        'These are conditional descriptive results from one scene and five dependent orders. They do not establish a stable strong positive Vectoring relationship, do not validate the first three scenes, and are not a replacement for the archived primary evaluation.','',
        '![Step comparison and fixed-scale count gate](figures/fixed-scale-comparison.png)','',
        '## Evidence','',
        '- `policy.json`: frozen baseline indices, original configuration, input hashes and restrictions.',
        '- `results/step-comparison.json`: original and fixed results at all 30 displayed doses, full pair counts, failed scales and step changes.',
        '- `results/summary.json`: original, fixed and matched-dose correlations with valid-dose identifiers.',
        '- `results/fixed-dose-curves.json`: complete diagnostic output, including rejections.',
        '- `verification.json`: exact original-output replay, independent OLS/rank verification and protected-file hashes.','']
    (R/'report.md').write_text('\n'.join(lines),encoding='utf8')
    assert all(sha(p)==value for p,value in protected.items())
    write(R/'verification.json',dict(old_files_unchanged=True,protected_files=len(protected),original_fourth_scene_records_replayed=30,
        fixed_records_computed=30,independent_OLS_checks=verified_ols,baseline_identical=True,
        count_gate_audit_passed=True,all_fixed_index_sets_identical=True,all_pair_counts_identical_to_original=True,
        independent_rank_checks_passed=True,first_three_scene_recalculations=0,threshold_changes=0,
        new_Encoder_calls=0,new_routes=0,new_side_combinations=0,analysis_sha256=sha(Path(__file__))))
    print(json.dumps(summary,indent=2))

def cli(argv=None):
    import argparse
    global R,OLD
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,default=OLD)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(argv);OLD=args.input.resolve()
    if not (OLD/'results'/(SCENE+'-embeddings.npz')).is_file():
        ap.error('Saved fourth-scene embeddings are required')
    R=new_output(args.output)
    main()

if __name__=='__main__':cli()
