"""Render the user-selected R2 >= 0.94 midpoint Holding presentation.

Re-screen saved final fits; never run inference, refit D or select new peaks.
The R2=0.98 source experiment remains immutable.
"""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import argparse
import contextlib
import io
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

from audit_holding_r2_sensitivity import run as screen, rho, stats
from plot_holding_midpoint_response import ROOT, COLORS, NAVY, sha


def render(out):
    audit = out / 'screening'
    audit.mkdir()
    with contextlib.redirect_stdout(io.StringIO()):
        screen(audit)
    data = json.loads((audit/'summary.json').read_text(encoding='utf8'))
    records = json.loads((audit/'screened-fit-records.json').read_text(encoding='utf8'))
    scenes = data['scenes']
    selected = [s for s in scenes if s['cutoff'] is not None]
    baseline = [s for s in selected if s['sensitivity_baseline']]
    arrays = {}
    coefficients = {}
    for s in scenes:
        rows = sorted([r for r in records if r['scene'] == s['scene']], key=lambda r:(r['replicate'],r['dose']))
        orders = sorted(set(r['replicate'] for r in rows))
        assert len(orders) == 5
        groups = [[r for r in rows if r['replicate']==order] for order in orders]
        x = np.array([r['dose'] for r in groups[0]])
        assert all([r['dose'] for r in group]==list(x) for group in groups)
        y = np.array([[r['sensitivity_dimension'] if r['sensitivity_accepted'] else np.nan for r in group] for group in groups])
        assert y.shape == (5,s['N']+1)
        mean = np.array([v[np.isfinite(v)].mean() if np.isfinite(v).any() else np.nan for v in y.T])
        arrays[s['scene']] = x,y,mean
        for scope in ['full','retained']:
            if scope == 'retained' and s['cutoff'] is None:
                continue
            mask = np.ones(x.shape,bool) if scope=='full' else x<=s['cutoff']
            values = [rho(x[mask],v[mask]) for v in y]
            coefficients[s['scene'],scope] = values
            assert stats(values) == s['correlations']['sensitivity_'+scope]
    assert len(selected)==7 and len(baseline)==5
    totals = data['totals']
    aggregate = totals['correlations']['sensitivity_retained']
    full_stats = totals['correlations']['sensitivity_full']
    baseline_stats = stats([v for s in baseline for v in coefficients[s['scene'],'retained']])
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,
        'axes.spines.top':False,'axes.spines.right':False,
        'axes.edgecolor':'#a7b2ba','axes.labelcolor':NAVY,
        'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':True})
    handles = [Line2D([],[],color=c,marker='o',ls='',ms=4.5,label=f'Order {k+1}') for k,c in enumerate(COLORS)]
    handles += [Line2D([],[],color=NAVY,lw=2.3,label='Mean of available orders'),
                Line2D([],[],color='#7b8790',marker='x',ls='',ms=4,label='Unavailable D (bottom)')]
    def save(fig,name):
        for ext in ['png','pdf','svg']:
            fig.savefig(out/f'{name}.{ext}',dpi=300,facecolor='white')
        plt.close(fig)
    def header(fig,title,subtitle,missing=True):
        fig.suptitle(title,x=.055,y=.976,ha='left',fontsize=24,fontweight='bold',color=NAVY)
        fig.text(.055,.928,subtitle,fontsize=12,color=NAVY)
        fig.legend(handles=handles if missing else handles[:-1],loc='upper left',bbox_to_anchor=(.05,.905),ncol=7,frameon=False,fontsize=10.5,
                   columnspacing=1.4,handletextpad=.5)
    def panel(ax,s,letter,full=False,delta=False):
        x,y,mean = arrays[s['scene']]
        mask = np.ones(x.shape,bool) if full else x<=s['cutoff']
        x,y,mean = x[mask],y[:,mask],mean[mask]
        if delta:
            assert np.isfinite(y[:,0]).all() and np.ptp(y[:,0]) == 0
            offset=y[0,0]
            y,mean=y-offset,mean-offset
            ax.axhline(0,lw=.8,color='#83949f',ls='--')
        for k,(v,c) in enumerate(zip(y,COLORS)):
            ax.scatter(x,v,s=19,color=c,alpha=.8,linewidths=0,zorder=3)
            bad=~np.isfinite(v)
            ax.plot(x[bad],np.full(bad.sum(),.018+.016*k),ls='',marker='x',ms=2.8,mew=.65,
                    color='#7b8790',alpha=.7,transform=ax.get_xaxis_transform())
        ax.plot(x,mean,color=NAVY,lw=2.4,zorder=4)
        if full and s['cutoff'] is not None:
            ax.axvline(s['cutoff'],ls='--',lw=.8,color='#83949f')
        summary=s['correlations']['sensitivity_'+('full' if full else 'retained')]
        value=summary['median']
        rs='NA' if value is None else f'{value:.3f}'
        ax.set_title(f'{letter}  {s["local"]}\nN = {s["N"]}   |   median order ρ = {rs}',loc='left',pad=13,fontsize=12,color=NAVY)
        ax.set(xlim=(-.35,float(x.max())+.35),xlabel='Aircraft with added Holding',ylabel='D − baseline D' if delta else 'Estimated D')
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5,integer=True))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.grid(axis='y',alpha=.22,lw=.65)
        good=y[np.isfinite(y)]
        if not len(good):
            ax.text(.5,.5,'Insufficient aircraft\nN < 30',transform=ax.transAxes,ha='center',va='center',color='#66747e')
        elif not full and not delta:
            low,high=good.min(),good.max(); span=max(high-low,.05)
            ax.set_ylim(low-.16*span,high+.12*span)
        return good
    def correlation_panel(ax,ss,tag):
        all_values=[]
        for i,s in enumerate(ss):
            values=coefficients[s['scene'],'retained']
            all_values.extend(values)
            for k,v in enumerate(values):
                if v is not None:ax.scatter(i+(k-2)*.09,v,color=COLORS[k],s=26,zorder=3)
            ax.hlines(stats(values)['median'],i-.28,i+.28,color=NAVY,lw=2)
        summary=stats(all_values)
        ax.axhline(0,color='#83949f',ls='--',lw=.8)
        ax.set(ylim=(-1.1,1.1),xlim=(-.5,len(ss)-.5),xticks=range(len(ss)),
               xticklabels=list('ABCDEFG')[:len(ss)],ylabel='Spearman ρ',xlabel='Scene panel')
        ax.set_title(f'{tag}  Per-order correlations\nMedian ρ = {summary["median"]:.3f}   |   {summary["positive"]}/{summary["n"]} positive',loc='left',pad=13,fontsize=12,color=NAVY)
        ax.grid(axis='y',alpha=.22,lw=.65)
    fig,axes=plt.subplots(2,4,figsize=(18.5,10.6))
    fig.subplots_adjust(left=.055,right=.985,top=.79,bottom=.08,hspace=.47,wspace=.34)
    header(fig,'Midpoint Holding: dose–dimension response',
           '240 s injection · 10 s sampling · R² ≥ 0.94 · archived pre-peak ranges · local time (UTC+08)')
    for i,(ax,s) in enumerate(zip(axes.flat,selected)):panel(ax,s,chr(65+i))
    correlation_panel(axes.flat[-1],selected,'H')
    save(fig,'holding-midpoint-prepeak-all-scenes')
    fig,axes=plt.subplots(2,3,figsize=(16,10.4),sharey=False)
    fig.subplots_adjust(left=.065,right=.98,top=.79,bottom=.08,hspace=.47,wspace=.3)
    header(fig,'Midpoint Holding: change from baseline',
           '240 s injection · 10 s sampling · R² ≥ 0.94 · archived pre-peak ranges · local time (UTC+08)',missing=False)
    good=[]
    for i,(ax,s) in enumerate(zip(axes.flat,baseline)):good.append(panel(ax,s,chr(65+i),delta=True))
    values=np.concatenate(good);lo=min(0,values.min());hi=values.max();span=hi-lo
    for ax in list(axes.flat)[:5]:ax.set_ylim(lo-.14*span,hi+.12*span)
    correlation_panel(axes.flat[-1],baseline,'F')
    save(fig,'holding-midpoint-prepeak-delta')
    fig,axes=plt.subplots(4,3,figsize=(16,18),sharey=True)
    fig.subplots_adjust(left=.065,right=.98,top=.85,bottom=.055,hspace=.52,wspace=.28)
    fig.suptitle('Midpoint Holding: complete dose ranges',x=.065,y=.978,ha='left',fontsize=24,fontweight='bold',color=NAVY)
    fig.text(.065,.947,'240 s injection · 10 s sampling · R² ≥ 0.94 · local time (UTC+08)',fontsize=12,color=NAVY)
    fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.06,.93),ncol=4,frameon=False,fontsize=11)
    all_good=[]
    for i,(ax,s) in enumerate(zip(axes.flat,scenes)):all_good.append(panel(ax,s,str(i+1),full=True))
    values=np.concatenate(all_good);lo=values.min();hi=values.max();span=hi-lo
    for ax in axes.flat:ax.set_ylim(lo-.12*span,hi+.1*span)
    fig.text(.065,.018,'Dashed vertical lines mark the archived pre-peak endpoints. Crosses mark unavailable estimates, not D = 0.',fontsize=11,color=NAVY)
    save(fig,'holding-midpoint-full-range-appendix')
    fmt=lambda v:'NA' if v is None else f'{v:.3f}'
    table='\n'.join(f'| {s["local"]} | {s["N"]} | {s["cutoff"] if s["cutoff"] is not None else "NA"} | {"Yes" if s["sensitivity_baseline"] else "No"} | {s["sensitivity_accepted"]}/{s["attempts"]} | {fmt(s["correlations"]["sensitivity_retained"]["median"])} | {fmt(s["correlations"]["sensitivity_full"]["median"])} |' for s in scenes)
    report=f'''# Midpoint Holding: dose–dimension response

Updated 2026-10-27. **The primary midpoint Holding fit threshold is now R² ≥ 0.94**, as explicitly selected by the user. R² ≥ 0.98 is preserved as the historical comparison, not the current primary gate. The endpoint control and Vectoring are separate experiments and are unchanged.

## Main paper figure

![Midpoint Holding dose–dimension response](figures/holding-midpoint-prepeak-all-scenes.png)

[Vector PDF](figures/holding-midpoint-prepeak-all-scenes.pdf) · [Editable SVG](figures/holding-midpoint-prepeak-all-scenes.svg)

**Figure caption.** Dose–dimension responses to a corrected 240-second midpoint Holding insertion, using trajectories sampled every 10 seconds and the frozen epoch-90 Encoder. Panels A–G include every scene with an archived pre-peak endpoint; endpoints are inherited unchanged from the earlier R² ≥ 0.98 analysis and were selected from its outcomes. Points denote five injection orders, and dark lines are unsmoothed means of available orders. Missing estimates are marked at the bottom and are never imputed; lines break where the mean is unavailable. Panel H displays every per-order Spearman coefficient within the corresponding displayed range; horizontal bars denote scene medians. Panel-specific D axes are labelled and should not be used to compare effect magnitudes by apparent slope. Dates are September 2026, local UTC+08. The five orders reuse aircraft and are dependent repeats.

Within these seven archived ranges, **{aggregate['positive']}/{aggregate['n']} order correlations are positive**, with **median Spearman ρ = {aggregate['median']:.3f}**. All 35 order coefficients are computable, including one negative coefficient. This median is over per-order correlations, not a correlation of the mean line and not 35 independent scene replications. The strong association is conditional on these exploratory, outcome-selected ranges.

## Exact experiment and processing

Aircraft were selected from natural-hour source files. A corrected 240-second racetrack was inserted at the trajectory midpoint; the complete original tail was retained. Injected trajectories were not clipped back to the source hour. The frozen Encoder uses 9 input features and a 16-dimensional embedding.

The final log C(r)–log r fit gate changes from R² ≥ 0.98 to R² ≥ 0.94. Aircraft QC, the minimum 30 aircraft, at least 8 fitting scales, at least 10 pairs, C(r) in [0.02, 0.3], radius ratio ≥ 2, the original adaptive fitting windows, five injection orders and archived endpoints remain unchanged. No new peak or favorable scene subset is selected. This is a declared post-analysis gate revision; 0.94 follows the existing engineering convention elsewhere in this evaluation, not a universally validated cutoff or a threshold optimized here by a search.

Saved positive slopes rejected solely for poor_linear_fit are re-screened. Earlier-stage failures remain unavailable. Acceptance changes from {totals['old_accepted']}/{totals['attempts']} to **{totals['sensitivity_accepted']}/{totals['attempts']}** order-dose records; accepted baselines change from {totals['old_baselines']}/12 to **{totals['sensitivity_baselines']}/12**. This changes availability of D, not the aircraft population. No Encoder inference, new D fit or new trajectory generation is needed for this gate-only update.

## Baseline-relative companion

![Change from baseline](figures/holding-midpoint-prepeak-delta.png)

[Vector PDF](figures/holding-midpoint-prepeak-delta.pdf)

All five accepted-baseline scenes are shown on a common ΔD scale. Within their archived ranges, {baseline_stats['positive']}/{baseline_stats['n']} coefficients are positive; median ρ = {baseline_stats['median']:.3f}. Subtracting a constant baseline does not change an order's correlation. The remaining two pre-peak scenes have no accepted baseline and are retained in absolute D in the main figure.

## Complete ranges and unavailable scenes

![All twelve scenes](figures/holding-midpoint-full-range-appendix.png)

[Vector PDF](figures/holding-midpoint-full-range-appendix.pdf)

All twelve planned scenes are retained. Across complete ranges, {full_stats['positive']}/{full_stats['n']} computable order correlations are positive; median ρ = **{full_stats['median']:.3f}**. Four scenes remain below the minimum sample count; another has no archived pre-peak endpoint and is not assigned a new one. The complete-range response is not uniformly positive or monotonic.

| Local UTC+08 | Aircraft N | Archived endpoint | Baseline accepted | Accepted D / attempted | Median pre-peak ρ | Median full-range ρ |
|---|---:|---:|---|---:|---:|---:|
{table}

## Paper interpretation and controls

Suggested manuscript wording: “With an R² ≥ 0.94 fit-quality criterion, the corrected midpoint Holding intervention showed predominantly positive dose–dimension associations within the seven archived pre-peak ranges (34/35 per-order coefficients positive; median Spearman ρ = 0.884). These exploratory ranges were inherited from an earlier analysis. Complete-range responses were weaker and included negative associations.”

The response is evidence of sensitivity to this synthetic intervention, not proof of global monotonicity or operational workload validity. Holding adds both geometry and duration. The [endpoint equal-duration control](holding-paper-appendix.md) remains necessary context: straight continuation also changes D. That control uses a different insertion position and cannot identify the exact duration contribution to midpoint Holding. It remains at its previously reported gate; no control result is relabelled as a newly computed 0.94 result.

## Reproducibility and history

- [Current renderer](code/plot_holding_primary.py) replays screening from saved fits and creates all three figures and this report; `--output` requires a new directory.
- [Saved-fit screening logic](code/audit_holding_r2_sensitivity.py) preserves original statuses and checks source hashes. Its internal sensitivity naming records the provenance; this report defines the user-selected primary presentation.
- [Archived R² ≥ 0.98 report](archive/holding-midpoint-r098/holding-midpoint-response.md) preserves the previous figures. The immutable strict-10s-reference run remains the original 0.98 source experiment.
- Local screening records, per-order statistics and render manifests are retained outside publication artifacts. No Git push was performed.
'''
    # Local renders place plots beside the report; publication copies put them
    # under figures/. Resolve source links for the caller's new output directory.
    from evaluation_layout import report_link
    report=report.replace('](figures/', '](')
    for old,target in {
        'holding-paper-appendix.md': ROOT/'holding/controls/holding-paper-appendix.md',
        'code/plot_holding_primary.py': Path(__file__),
        'code/audit_holding_r2_sensitivity.py': ROOT/'holding/code/audit_holding_r2_sensitivity.py',
        'archive/holding-midpoint-r098/holding-midpoint-response.md': ROOT/'holding/history/midpoint-r098/holding-midpoint-response.md',
    }.items():
        report=report.replace(']('+old+')', ']('+report_link(target,out)+')')
    (out/'holding-midpoint-response.md').write_text(report,encoding='utf8')
    result=dict(primary_min_r_squared=.94,old_min_r_squared=.98,totals=totals,
                baseline_retained=baseline_stats,scenes=scenes,new_encoder_calls=0,new_D_fits=0,new_cutoffs=0,
                rendering='Unsmoothed available-order means; all archived pre-peak scenes; all full-range scenes',
                source_manifest=json.loads((audit/'manifest.json').read_text(encoding='utf8')),
                figure_sha256={p.name:sha(p) for p in out.iterdir() if p.suffix in ['.png','.pdf','.svg']})
    (out/'render-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(primary_min_r_squared=.94,retained=aggregate,full=full_stats,baseline=baseline_stats,accepted=totals['sensitivity_accepted']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Choose a new directory; previous renders are protected.')
    a.output.mkdir(parents=True)
    render(a.output)
