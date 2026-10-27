"""Audit saved midpoint D curves; no Encoder or dimension-estimator imports.

Outputs stay local. Complete-case curves are diagnostics, not replacement results.
"""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from plot_holding_midpoint_response import ROOT, label, sha, NAVY


def correlation(y):
    ok=np.isfinite(y)
    if ok.sum()<5 or np.ptp(y[ok])==0:return None
    return float(spearmanr(np.arange(len(y))[ok],y[ok]).statistic)


def run(out):
    src=study_path('strict-10s-reference/results')
    paths=[src/'experiment-results.json',src/'summary.json',src/'analysis-manifest.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    raw,summary,policy=[json.loads(p.read_text(encoding='utf8')) for p in paths]
    rr=raw['qc500']['holding']['scenes'];summary=summary['qc500']['holding']
    rows=[];steps=[];curves={}
    for s in summary['scenes']:
        if s['cutoff'] is None:continue
        runs=sorted([r for r in rr if r['scene_id']==s['scene_id']],key=lambda r:r['replicate'])
        k=s['cutoff']
        ys=np.array([[d['dimension'] if d['status']=='ok' else np.nan for d in r['dose_curve'][:k+1]] for r in runs],float)
        ok=np.isfinite(ys);counts=ok.sum(0)
        means=np.array([np.mean(col[np.isfinite(col)]) if np.isfinite(col).any() else np.nan for col in ys.T])
        stored=np.array([np.nan if v is None else v for v in s['peak']['mean_D'][:k+1]])
        assert np.allclose(means,stored,equal_nan=True)
        complete=ok.all(axis=1);fixed=ys[complete].mean(axis=0) if complete.any() else np.full(k+1,np.nan)
        scene_steps=[]
        for dose in range(1,k+1):
            before,after=ok[:,dose-1],ok[:,dose];common=before&after
            if not (before.any() and after.any()):continue
            delta=float(means[dose]-means[dose-1])
            paired=float(np.mean(ys[common,dose]-ys[common,dose-1])) if common.any() else None
            residual=delta-paired if paired is not None else None
            if paired is not None:assert np.isclose(delta,paired+residual)
            same_ranges=0;compared_ranges=0
            for j in np.flatnonzero(common):
                a,b=runs[j]['dose_curve'][dose-1:dose+1]
                compared_ranges+=1
                same_ranges+=a['fit_radius_range']==b['fit_radius_range']
            record=dict(scene=s['scene_id'],to_dose=dose,available_mean_delta=delta,
                        common_order_mean_delta=paired,composition_residual=residual,
                        membership_changed=bool(np.any(before!=after)),
                        before_orders=','.join(str(i+1) for i in np.flatnonzero(before)),
                        after_orders=','.join(str(i+1) for i in np.flatnonzero(after)),
                        common_count=int(common.sum()),same_fit_range_count=same_ranges,
                        comparable_fit_range_count=compared_ranges)
            scene_steps.append(record);steps.append(record)
        downs=[d for d in scene_steps if d['available_mean_delta']<0]
        ranges={tuple(d['fit_radius_range']) for r in runs for d in r['dose_curve'][:k+1] if d['status']=='ok'}
        ranges_total=sum(d['comparable_fit_range_count'] for d in scene_steps)
        changes=sum(d['comparable_fit_range_count']-d['same_fit_range_count'] for d in scene_steps)
        row=dict(scene=s['scene_id'],local=label(s),N=s['n_aircraft'],cutoff=k,
                 accepted=int(ok.sum()),attempts=int(ys.size),complete_orders=[int(i+1) for i in np.flatnonzero(complete)],
                 mean_down_steps=len(downs),comparable_steps=len(scene_steps),
                 downs_with_unchanged_membership=sum(not d['membership_changed'] for d in downs),
                 downs_despite_nonnegative_common=sum(d['common_order_mean_delta'] is not None and d['common_order_mean_delta']>=0 for d in downs),
                 mean_curve_rho=correlation(means),complete_case_mean_rho=correlation(fixed),
                 archived_median_order_rho=s['retained']['median'],distinct_fit_ranges=len(ranges),
                 order_steps_with_changed_fit_range=changes,comparable_order_steps=ranges_total,
                 complete_case_down_steps=int(np.sum(np.diff(fixed)<0)) if complete.any() else None)
        rows.append(row);curves[s['scene_id']]=(means,fixed,counts)
    with (out/'adjacent-dose-audit.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(steps[0]));w.writeheader();w.writerows(steps)
    (out/'scene-summary.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n',encoding='utf8')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    fig,axes=plt.subplots(4,2,figsize=(15,18))
    fig.subplots_adjust(left=.07,right=.975,top=.87,bottom=.10,hspace=.63,wspace=.2)
    fig.suptitle('Holding: is the mean changing because its members change?',x=.07,y=.975,ha='left',fontsize=20,color=NAVY,fontweight='bold')
    fig.text(.07,.945,'Saved 10-second midpoint results • archived pre-peak ranges unchanged • descriptive diagnostics only',fontsize=11)
    fig.legend(handles=[Line2D([],[],color=NAVY,lw=2,label='Original available-order mean'),
                        Line2D([],[],color='#ca7a26',lw=2,ls='--',label='Fixed complete-case order mean')],
               loc='upper left',bbox_to_anchor=(.065,.928),ncol=2,frameon=False)
    for ax,r in zip(axes.flat,rows):
        mean,fixed,counts=curves[r['scene']];x=np.arange(len(mean))
        ax.plot(x,mean,color=NAVY,lw=2,marker='o',ms=3)
        if r['complete_orders']:ax.plot(x,fixed,color='#ca7a26',lw=2,ls='--',marker='.',ms=4)
        ax.set_title(f'{r["local"]} | N={r["N"]} | cutoff={r["cutoff"]}\nComplete-case orders: '+(', '.join(map(str,r['complete_orders'])) or 'none'),loc='left',fontsize=11,pad=12)
        ax.set(xlabel='Injected aircraft',ylabel='Absolute D',xlim=(-.4,x[-1]+.4))
        finite=np.r_[mean[np.isfinite(mean)],fixed[np.isfinite(fixed)]];lo,hi=finite.min(),finite.max();span=max(hi-lo,.05)
        ax.set_ylim(lo-.34*span,hi+.13*span)
        for xx,n in zip(x,counts):ax.text(xx,.045,str(n),transform=ax.get_xaxis_transform(),ha='center',fontsize=7,color='#728592')
        ax.text(.02,.13,'Bottom numbers: available orders (0–5)',transform=ax.transAxes,fontsize=8,color='#728592')
        ax.grid(axis='y',alpha=.2);ax.xaxis.set_major_locator(MaxNLocator(nbins=6,integer=True))
    ax=axes.flat[-1];ax.axis('off')
    total_down=sum(r['mean_down_steps'] for r in rows)
    reversed_down=sum(r['downs_despite_nonnegative_common'] for r in rows)
    unchanged_down=sum(r['downs_with_unchanged_membership'] for r in rows)
    ax.text(0,1,'What the audit can and cannot establish',va='top',fontsize=14,fontweight='bold',color=NAVY)
    ax.text(0,.82,f'{total_down} downward mean steps across 7 archived ranges\n{reversed_down}: common orders did not decline\n{unchanged_down}: exactly the same orders still declined\n\n4/7 scenes have no complete-case order.\nFixed subsets are selected by fit availability;\nthey are diagnostics, not replacement evidence.\n\nScale effects remain unresolved; D was not refitted.',va='top',fontsize=11,linespacing=1.4)
    fig.text(.07,.063,'All curves use saved accepted D. No imputation, smoothing, new peaks or new dimension fits. Times UTC+08; independent panel y-scales.',fontsize=10)
    fig.text(.07,.038,'Adjacent common-order subsets can differ between steps; their increments are not accumulated into a fabricated corrected response curve.',fontsize=10)
    fig.text(.07,.013,'Hour-selected source aircraft; complete injected tails retained. Complete-case selection can bias the diagnostic and is disclosed explicitly.',fontsize=10)
    for ext in ['png','pdf']:fig.savefig(out/f'holding-mean-composition-diagnostic.{ext}',dpi=180,facecolor='white')
    plt.close(fig)
    fmt=lambda v:'NA' if v is None else f'{v:.3f}'
    table='\n'.join(f'| {r["local"]} | {r["accepted"]}/{r["attempts"]} | '+(', '.join(map(str,r['complete_orders'])) or 'None')+f' | {r["mean_down_steps"]} | {r["downs_despite_nonnegative_common"]} | {r["downs_with_unchanged_membership"]} | {fmt(r["mean_curve_rho"])} | {fmt(r["complete_case_mean_rho"])} |' for r in rows)
    scale_table='\n'.join(f'| {r["local"]} | {r["distinct_fit_ranges"]} | {r["order_steps_with_changed_fit_range"]}/{r["comparable_order_steps"]} |' for r in rows)
    report='''# Holding mean-composition audit — step 1

Uses saved corrected 10-second midpoint QC500 results. No Encoder inference, D fit, threshold change, new random order or cutoff search. All seven cutoff-available scenes are audited, not just the outcome-selected top six. The other five planned scenes have no archived cutoff and are not assigned an invented one. Primary results and figures remain unchanged.

## Method

For adjacent doses, A and B are the sets of accepted injection orders; C is their intersection. Compare the original mean difference with mean(D_after - D_before) for C only. The residual is the exact arithmetic difference between those two summaries; it is a composition effect relative to this common-order reference, not a causal decomposition. When A=B, the residual must be zero. No-overlap steps cannot be decomposed. Tiny negative differences are retained without choosing an extra tolerance.

The fixed complete-case subset is the intersection of valid orders across every dose from zero through the existing cutoff. The cutoff is not shortened to obtain more complete cases. These subsets are selected by fit success and may be biased; they are diagnostic only. Adjacent common-order increments are never chained into a new D curve because their membership may change between steps.

## Findings

'''+f'There are {total_down} downward available-mean steps. In {reversed_down}, the common orders did not decline; in {unchanged_down}, membership was exactly unchanged and the mean still declined. These are counts, not percentages of fluctuation magnitude or independent observations.\n\n'+'''| Local UTC+08 | Accepted fits | Complete-case orders (1–5) | Downward steps | Down despite nonnegative common change | Down with identical membership | Original mean rho | Fixed complete-case mean rho |
|---|---:|---|---:|---:|---:|---:|---:|
'''+table+'''

![Mean-composition diagnostic](holding-mean-composition-diagnostic.png)

These rho values describe aggregate mean curves. They are not the previously reported median of order-level rho values and should not be substituted to inflate the primary association. A smoother or more correlated complete-case mean would not justify discarding the other orders.

## Scale selection remains another unresolved contributor

| Local UTC+08 | Distinct accepted fit-radius intervals | Adjacent accepted order steps whose interval changes |
|---|---:|---:|
'''+scale_table+'''

The fixed candidate grid does not freeze which radii enter each fit. Changing fit ranges is observed, but its contribution cannot be isolated without re-estimating D. Identical endpoint ranges do not prove every internal fit index stayed identical; the archived compact records omit the complete indices and C(r) arrays. Thus the interval comparison is a limited diagnostic.

## Recommended next step, not executed

Diagnose fixed scales in all three scenes with accepted baselines (September 10 14:00, September 20 12:00, September 26 07:00 local). Use the exact baseline grid/index set, never a new best-looking range. Evaluate complete original dose ranges with the same five orders, and retain the original cutoff merely as a reporting marker. Keep the historical R², aircraft count, pair count, C(r) bounds, radius-span and scale-count gates. If a locked scale fails its required gate, mark that dose NA rather than silently dropping the scale or widening the range. Baseline-NA scenes are unavailable for this baseline-anchored diagnostic.

Implementation warning: in the inspected local calculator, explicit fit_range selects radius bounds instead of applying the automatic C(r) bounds. Calling it directly would therefore fail the promise to retain all current conditions. A diagnostic implementation must explicitly preserve both the locked indices and original gates, with fail-closed behavior; no such estimator change has been made here. Restore the historical configuration from the saved run manifest, not the potentially changed defaults in the current source tree.

The midpoint compact JSON does not contain full correlation-integral curves or embeddings. A filename scan of the existing Holding/10s artifact folders found endpoint-control embeddings but no midpoint embedding cache. If no verifiable midpoint cache is available, reconstruct the original midpoint embeddings with the frozen source/Encoder/order configuration, first reproduce the saved adaptive results, and only then compare fixed scales. Endpoint injected embeddings must not be substituted. This is additional computation requiring the next-stage decision, not a plotting operation.

Do not relax thresholds, switch to the old geometry-bug pilot, fit a monotone smoother and call its association validation, or increase repetitions until a desirable coefficient appears. Increasing repeats is a separate later decision after this diagnostic.

## Files

- `scene-summary.json`: scene-level diagnostics, full precision.
- `adjacent-dose-audit.csv`: all decomposable/comparable adjacent steps and membership.
- `render-manifest.json`: source hashes and no-estimation record.
- `holding-mean-composition-diagnostic.pdf`: vector figure.
'''
    (out/'report.md').write_text(report,encoding='utf8')
    assert all(sha(ROOT/p)==v for p,v in hashes.items())
    (out/'render-manifest.json').write_text(json.dumps(dict(source_sha256=hashes,new_encoder_calls=0,new_D_calls=0,new_draws=0,changed_cutoffs=0,changed_thresholds=0),indent=2)+'\n',encoding='utf8')
    print(json.dumps(rows,indent=2));print('Down steps',total_down,'nonnegative common',reversed_down,'identical membership',unchanged_down)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Use a new output directory; previous artifacts are preserved.')
    a.output.mkdir(parents=True);run(a.output)
