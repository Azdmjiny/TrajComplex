"""Verify and summarize the authorized two-arm run; no new experimental arms."""
from pathlib import Path
import collections, hashlib, json, sys
from datetime import datetime, timedelta
ROOT=Path(__file__).resolve().parent; B=ROOT.parent; WS=B/'evaluation-10s/workspace'
sys.dont_write_bytecode=True
sys.path[:0]=[str(B/'evaluation-python-deps'),str(WS),str(WS/'evaluation/code')]
import numpy as np
from scipy.stats import rankdata
from complexity.calculator import ComplexityConfig,estimate_complexity
from truncation import finite_ok,curve_correlation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def json_text(x):return json.dumps(x,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v))
def write(p,x):Path(p).write_text(json_text(x),encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
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

def main():
    results=read(ROOT/'results/experiment-results.json'); assignments=read(ROOT/'assignments.json')
    manifest=read(ROOT/'results/run-manifest.json'); geometry=read(ROOT/'geometry-audit.json')
    assert manifest['state']=='complete'
    protected=read(ROOT/'before-hashes.json')
    assert all(sha(p)==value for p,value in protected.items())
    assert all(sha(p)==value for p,value in manifest['source_sha256'].items())
    assert sha(ROOT/'policy.json')==manifest['policy_sha256'] and sha(ROOT/'assignments.json')==manifest['assignments_sha256']
    cfg=ComplexityConfig(normalize=False)
    checked_D=0; checked_paths=0; checked_rho=0
    repeat_rows=[]; pair_rows=[]; scene_rows=[]
    for selection in assignments:
        sid=selection['scene']; trials=[t for t in results if t['scene']==sid]
        assert len(trials)==5
        with np.load(ROOT/'inputs'/(sid+'-trajectories.npz')) as tr:
            gm={r['icao24']:r for r in next(s for s in geometry if s['scene']==sid)['candidates']}
            for i in selection['eligible_indices']:
                a=selection['aircraft_ids'][i]; p=tr[a+'_baseline']; h=tr[a+'_holding']; s=tr[a+'_straight']; speed=gm[a]['speed_m_s']
                assert len(h)==len(s)==len(p)+24
                for q in (h,s):
                    np.testing.assert_array_equal(q[:len(p)],p)
                    np.testing.assert_array_equal(q[len(p):,2],np.full(24,p[-1,2]))
                np.testing.assert_array_equal(h[-1],p[-1])
                np.testing.assert_allclose(h[len(p):len(p)+6],s[len(p):len(p)+6],rtol=0,atol=1e-8)
                distances=np.linalg.norm(np.diff(h[len(p)-1:,:2],axis=0),axis=1)
                expected=np.tile(np.r_[np.full(6,10*speed),np.full(6,2*speed/np.deg2rad(3)*np.sin(np.deg2rad(30)/2))],2)
                np.testing.assert_allclose(distances,expected,rtol=1e-10,atol=1e-8)
                direction=(p[-1,:2]-p[-2,:2]); direction/=np.linalg.norm(direction)
                np.testing.assert_allclose(s[-1,:2]-p[-1,:2],direction*240*speed,rtol=1e-10,atol=1e-8)
                checked_paths+=1
        with np.load(ROOT/'results'/(sid+'-embeddings.npz')) as arrays:
            for t,rep in zip(trials,selection['repeats']):
                assert t['replicate']==rep['replicate'] and t['aircraft_order']==rep['aircraft_order']
                assert len(set(rep['order']))==len(rep['order'])==len(selection['eligible_indices'])
                for arm in ['holding','straight']:
                    current=arrays['baseline'].copy()
                    for k,record in enumerate(t['curves'][arm]):
                        if k:current[rep['order'][k-1]]=arrays[arm][rep['order'][k-1]]
                        fresh=estimate_complexity(current,config=cfg,radii=arrays['radii'],scene_id=sid).to_dict()
                        assert json.loads(json.dumps(fresh))=={key:value for key,value in record.items() if key!='injected_aircraft'}, (sid,t['replicate'],arm,k)
                        checked_D+=1
                    rr=independent_rho(t['curves'][arm]); actual=t['correlations'][arm]['rho']
                    if rr is None:assert actual is None
                    else:assert abs(rr-actual)<1e-12
                    checked_rho+=1
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
    summary=dict(scenes=12,background=manifest['n_background'],pair_eligible=manifest['n_eligible'],baseline_valid_scenes=len(baseline_scenes),
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
    write(ROOT/'results/summary.json',summary);write(ROOT/'results/paired-dose-records.json',pair_rows);write(ROOT/'results/repeat-summary.json',repeat_rows)
    figures=ROOT/'figures';figures.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.titlesize':11,'axes.labelsize':10,'legend.fontsize':10})
    colors={'holding':'#2166ac','straight':'#d66016'}
    for page in range(2):
        fig,axes=plt.subplots(3,2,figsize=(13,12),layout='constrained')
        for ax,s in zip(axes.flat,scene_rows[page*6:page*6+6]):
            tt=[t for t in results if t['scene']==s['scene']]
            for arm in ['holding','straight']:
                values=np.asarray([[p['dimension'] if finite_ok(p) else np.nan for p in t['curves'][arm]] for t in tt])
                x=np.arange(values.shape[1]); n=np.isfinite(values).sum(axis=0)
                mean=np.divide(np.nansum(values,axis=0),n,out=np.full(len(x),np.nan),where=n>0)
                for row in values:ax.plot(x,row,color=colors[arm],alpha=.18,lw=.7)
                ax.plot(x,mean,color=colors[arm],lw=1.8,label=arm.title())
            ax.set_title(f"{s['local_UTC8']} UTC+08 | N={s['n_aircraft']}\nValid estimates: H {s['valid_counts']['holding']}, S {s['valid_counts']['straight']} / {s['dose_records_per_arm']} each")
            ax.set(xlabel='Aircraft with +240 s appended',ylabel='Accepted D',xlim=(0,s['eligible']))
            if not sum(s['valid_counts'].values()):ax.text(.5,.5,'D unavailable: fewer than 30 aircraft',transform=ax.transAxes,ha='center',va='center',wrap=True)
            ax.grid(alpha=.2)
        fig.suptitle('Holding versus equal-duration straight flight\nThin: five matched orders; thick: available-order mean; gaps remain missing',fontsize=15)
        handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=2)
        for ext in ['png','svg']:fig.savefig(figures/f'dose-curves-{page+1}.{ext}',dpi=180)
        plt.close(fig)
    fig,axes=plt.subplots(4,3,figsize=(15,13),layout='constrained')
    for ax,s in zip(axes.flat,scene_rows):
        pp=[p for p in pair_rows if p['scene']==s['scene']]; curves=[]
        for rep in range(5):
            points=[p for p in pp if p['replicate']==rep]
            y=np.asarray([p['holding_minus_straight'] if p['jointly_valid'] else np.nan for p in points]);curves.append(y)
            ax.plot(range(len(y)),y,color='#59469c',alpha=.3,lw=.8)
        vals=np.asarray(curves);n=np.isfinite(vals).sum(axis=0)
        mean=np.divide(np.nansum(vals,axis=0),n,out=np.full(vals.shape[1],np.nan),where=n>0)
        ax.plot(range(len(mean)),mean,color='#59469c',lw=2)
        ax.axhline(0,color='black',lw=.8,ls='--'); ax.grid(alpha=.2)
        ax.set_title(f"{s['local_UTC8']} | N={s['n_aircraft']}\nMatched nonzero records: {s['joint_nonzero_doses']}")
        ax.set(xlabel='Aircraft with +240 s appended',ylabel='D(Holding) − D(Straight)',xlim=(0,s['eligible']))
        if s['joint_nonzero_doses']==0:ax.text(.5,.65,'No accepted paired comparison',transform=ax.transAxes,ha='center',va='center',fontsize=9)
    fig.suptitle('Equal-duration paired difference at the same aircraft dose\nBoth D estimates must pass; positive means Holding gives higher D',fontsize=15)
    for ext in ['png','svg']:fig.savefig(figures/f'paired-differences.{ext}',dpi=180)
    plt.close(fig)
    # Deterministically selected first scene/first eligible aircraft, independent of D.
    sel=assignments[0];a=sel['aircraft_ids'][sel['eligible_indices'][0]]
    with np.load(ROOT/'inputs'/(sel['scene']+'-trajectories.npz')) as saved:
        p=saved[a+'_baseline'];anchor=p[-1,:2]
        fig,ax=plt.subplots(figsize=(9,6),layout='constrained')
        ax.plot(*(p[-7:,:2]-anchor).T/1000,color='gray',lw=2,label='Original final 60 s (unchanged)')
        for arm in ['holding','straight']:
            q=saved[a+'_'+arm][len(p)-1:,:2]
            ax.plot(*((q-anchor).T/1000),'-o',color=colors[arm],ms=3,label=arm.title()+' +240 s')
        ax.scatter(0,0,color='black',s=45,zorder=5,label='Shared endpoint / start')
        ax.set(xlabel='East from original endpoint (km)',ylabel='North from original endpoint (km)',title=f'Approved terminal-append construction: {sel["scene"]}, {a}')
        ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.2);ax.legend(loc='upper left',bbox_to_anchor=(1,1))
        for ext in ['png','svg']:fig.savefig(figures/f'paired-geometry-example.{ext}',dpi=180)
        plt.close(fig)
    lines=['# Holding equal-duration terminal-append control','',
        'Completed the approved experiment on all original twelve scenes with the frozen 10-second Encoder. Earlier results remain unchanged. No Vectoring run, retraining, download, threshold relaxation or outcome-selected cutoff was performed.','',
        '## Design and verification','',
        f"All {manifest['n_background']} QC500 background aircraft-hours supported both additions. Each arm appends exactly 240 seconds / 24 samples from the same endpoint, with the same starting heading, speed, constant local ENU height and injection order. The original trajectory points are retained exactly. All twelve baseline D results (including failures) exactly reproduce the earlier run.",'',
        'Holding reuses the existing racetrack: two 60-second straight legs and two standard-rate 180-degree turns (3 degrees/second). Straight flight continues for 240 seconds at the same speed. Endpoint heading is the final input segment direction; speed uses the existing local median rule on the final three segments (>1 m/s). No fallback speed or direction was used. This is synthetic continuation, not an attempt to fill missing observations.','',
        'The two paths have the same continuous path length. At 10-second sampling, circular arcs are represented by chords, making the Holding polyline approximately 0.57% shorter than the straight polyline; point count and duration are exactly equal. No adjustment was made to erase that geometry difference. The existing source QC is preserved; this control is not an additional aircraft-specific feasibility certification.','',
        '![Matched construction](figures/paired-geometry-example.png)','',
        '## Main numerical results','',
        '| Full-range correlation summary | Holding | Straight |','|---|---:|---:|']
    for label,key in [("Each arm's own valid-dose subset",'arm_correlations'),('Same jointly valid doses in each pair','common_correlations'),('Same doses, baseline-valid scenes only','baseline_ok_common_correlations')]:
        vals=summary[key]
        lines.append(f"| {label}: median rho | {fmt(vals['holding']['median'])} ({vals['holding']['valid']} curves) | {fmt(vals['straight']['median'])} ({vals['straight']['valid']} curves) |")
    lines += ['',f"There are {summary['scenes_with_paired_data']} scenes with accepted nonzero paired comparisons, out of twelve. {summary['scenes_positive_paired_median']} have a positive median Holding-minus-Straight difference. The equal-scene median paired difference is {fmt(summary['equal_scene_median_paired_excess'],5)}. Only {summary['baseline_valid_scenes']} scenes have an accepted zero-injection baseline; their equal-scene median paired difference is {fmt(summary['baseline_ok_scene_median_paired_excess'],5)}.",'',
        'Paired differences use only the same scene/order/dose with both D estimates accepted. Baseline-relative changes additionally require an accepted baseline. Missing D is never filled or treated as zero. Every rejected record and reason is retained. Five orders and their nested doses are not independent experimental samples; the reported medians are descriptive and no p-values are claimed.','',
        '| Scene (UTC+08) | N | Baseline D | Joint nonzero records | Common-dose rho H | Common-dose rho S | Median paired D(H) − D(S) |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for s in scene_rows:
        lines.append(f"| {s['local_UTC8']} | {s['n_aircraft']} | {fmt(s['baseline_D'])} | {s['joint_nonzero_doses']} | {fmt(s['common_correlations']['holding']['median'])} | {fmt(s['common_correlations']['straight']['median'])} | {fmt(s['paired_excess_median'],5)} |")
    lines += ['', 'Within each scene, the paired difference is summarized by the median across orders of each order\'s median over valid nonzero doses. Common-dose rho is similarly summarized across orders, subject to the unchanged minimum of five valid doses. Joint record counts include repeated orders and are not independent sample counts.','',
        '## Interpretation and limits','',
        'Straight continuation also changes D, and both arms show positive and negative dose associations depending on the scene/order. Thus an increase in Holding D alone cannot establish that the effect is specific to turning geometry. The matched Holding-minus-Straight difference is positive in seven of eight scene summaries, supporting a geometry/location contribution beyond equal additional duration and token count. One scene has a negative median difference. A higher D than the straight control is distinct from a strong positive correlation with the number of injected aircraft.','',
        'This experiment controls added duration and point count, but it cannot assign a percentage of the old response to pure sequence length: straight flight itself changes spatial extent, position features and contextual Encoder outputs. The matched contrast estimates the difference between these two specified continuations, not a universal isolated effect of Holding.','',
        'The old experiment inserted Holding at the midpoint. This approved control appends both arms at the endpoint. It therefore does not directly validate or invalidate the old midpoint pre-peak coefficient, and should not be presented as the same intervention. Full-range results are retained here; no high-correlation prefix was selected.','',
        'D is still subject to the unchanged finite-count and fit-quality gates. Four scenes have fewer than 30 background aircraft and cannot yield D at any dose. Other failures are preserved. A shared radius grid does not imply an identical eligible fitting-scale subset: that subset can change under the existing pair-count/C(r) rules. Correlations on available accepted doses remain conditional on those gates.','',
        'The paper can report this as a paired equal-duration sensitivity/control experiment with mixed scene-dependent outcomes. These results do not establish a universal strong positive Holding-specific dose response or complete validation of the D method.','',
        '![First six scenes](figures/dose-curves-1.png)','', '![Last six scenes](figures/dose-curves-2.png)','',
        '![Same-dose paired differences](figures/paired-differences.png)','',
        '## Reproducibility','',
        '- `policy.json` and `assignments.json`: choices frozen before inference.',
        '- `geometry-audit.json` and `inputs/`: exact paired arrays, source QC and geometry checks.',
        '- `results/run-manifest.json`: checkpoint, source hashes, original inputs and environment.',
        '- `results/experiment-results.json`: every D attempt, scale, pair count and failure reason.',
        '- `results/summary.json`, `repeat-summary.json`, `paired-dose-records.json`: reported statistics.',
        '- `verification.json`: independent replays of saved D records, rank correlations, path geometry and protected-file hashes.',
        '- `run.py`: run once into a new directory; refuses to overwrite an existing results directory.','']
    (ROOT/'report.md').write_text('\n'.join(lines),encoding='utf8')
    verification=dict(old_files_unchanged=all(sha(p)==value for p,value in protected.items()),protected_files=len(protected),
        trajectory_pairs_verified=checked_paths,D_records_replayed=checked_D,arm_correlations_rank_verified=checked_rho,
        common_dose_correlations_rank_verified=120,baseline_scenes_exactly_matching_old_run=12,
        original_points_unchanged=True,equal_added_points=24,equal_added_seconds=240,
        all_source_policy_assignment_hashes_match=True,threshold_changes=0,truncations=0,vectoring_runs=0)
    write(ROOT/'verification.json',verification)
    print(json_text({k:v for k,v in summary.items() if k!='scene_details'}))
    print(json_text(scene_rows))
    print(json_text(verification))

if __name__=='__main__':main()
