"""Explicitly outcome-selected six-scene preview and complementary six scenes.

Reads saved D only; never overwrites existing renders or changes primary reports.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from plot_holding_midpoint_response import ROOT, COLORS, NAVY, label, sha


def render(out):
    source = ROOT/'runs/strict-10s-reference/results'
    files = [source/'experiment-results.json', source/'summary.json']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
    raw, summary = [json.loads(p.read_text(encoding='utf8')) for p in files]
    runs = raw['qc500']['holding']['scenes']
    summary = summary['qc500']['holding']
    scenes = summary['scenes']
    ranked = sorted([s for s in scenes if s['cutoff'] is not None],
                    key=lambda s: (-s['retained']['median'], s['scene_id']))
    selected = sorted(ranked[:6], key=lambda s: s['scene_id'])
    ids = {s['scene_id'] for s in selected}
    remaining = [s for s in scenes if s['scene_id'] not in ids]
    assert len(selected) == len(remaining) == 6
    assert len(ids | {s['scene_id'] for s in remaining}) == 12
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11,
                         'axes.spines.top':False, 'axes.spines.right':False,
                         'axes.edgecolor':'#afbdc6', 'axes.labelcolor':NAVY,
                         'xtick.color':'#4c6170', 'ytick.color':'#4c6170',
                         'pdf.fonttype':42, 'svg.fonttype':'none'})
    handles = [Line2D([], [], marker='o', color=c, lw=.6, ms=4, label=f'Order {i+1}') for i,c in enumerate(COLORS)]
    handles += [Line2D([], [], color=NAVY, lw=2.4, label='Available-order mean'),
                Line2D([], [], color='#7a8791', marker='x', ls='', ms=4, label='Rejected fit (bottom marks)')]
    for name, group, prepeak in [('holding-six-selected-prepeak', selected, True),
                                  ('holding-six-remaining-full-range', remaining, False)]:
        fig, axes = plt.subplots(3, 2, figsize=(15, 16))
        fig.subplots_adjust(left=.075, right=.98, top=.81, bottom=.14, hspace=.47, wspace=.19)
        title = 'Holding: six higher-correlation scenes' if prepeak else 'Holding: the other six planned scenes'
        subtitle = ('Selected by archived pre-peak median order ρ; only archived pre-peak doses shown' if prepeak else
                    'Full dose ranges shown; failed scenes retained; dashed lines mark archived cutoffs')
        fig.suptitle(title, x=.075, y=.975, ha='left', fontsize=24, fontweight='bold', color=NAVY)
        fig.text(.075, .942, subtitle, fontsize=12, color='#526472')
        fig.text(.075, .918, 'Corrected 10-second midpoint Holding • +240 s • absolute D • scene times UTC+08', fontsize=11, color='#526472')
        fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.07,.898), ncol=4, frameon=False, fontsize=10)
        for i,(ax,s) in enumerate(zip(axes.flat,group)):
            rr = sorted([r for r in runs if r['scene_id']==s['scene_id']], key=lambda r:r['replicate'])
            x = np.array([p['holding_aircraft'] for p in rr[0]['dose_curve']])
            ys = np.array([[p['dimension'] if p['status']=='ok' else np.nan for p in r['dose_curve']] for r in rr], float)
            mask = x<=s['cutoff'] if prepeak else np.ones(len(x),bool)
            x,ys = x[mask],ys[:,mask]
            means = np.array([np.mean(v[np.isfinite(v)]) if np.isfinite(v).any() else np.nan for v in ys.T])
            saved = np.array([np.nan if v is None else v for v in s['peak']['mean_D']])[mask]
            assert np.allclose(means,saved,equal_nan=True)
            for k,(y,c) in enumerate(zip(ys,COLORS)):
                ax.plot(x,y,color=c,lw=.55,alpha=.35)
                ax.scatter(x,y,color=c,s=19,alpha=.82,linewidths=0,zorder=3)
                bad=~np.isfinite(y)
                ax.plot(x[bad],np.full(bad.sum(),.018+k*.013),ls='',marker='x',color=c,
                        ms=2.5,mew=.6,alpha=.6,transform=ax.get_xaxis_transform())
            ax.plot(x,means,color=NAVY,lw=2.6,zorder=4)
            key='retained' if prepeak else 'full'
            rho=s[key]['median'];rho_text='NA' if rho is None else f'{rho:.3f}'
            ax.set_title(f'{chr(65+i)}  {label(s)} | N={s["n_aircraft"]}\nMedian order ρ={rho_text} | {s[key]["n"]}/5 orders estimable',
                         loc='left',fontsize=12,pad=12,color=NAVY)
            accepted=int(np.isfinite(ys).sum())
            ax.text(.02,.97,f'Accepted fits: {accepted}/{ys.size}  |  '+('archived cutoff: '+str(s['cutoff']) if prepeak else 'full range'),
                    transform=ax.transAxes,va='top',fontsize=9,color='#526472')
            if not prepeak and s['cutoff'] is not None:
                ax.axvline(s['cutoff'],ls='--',color='#8295a1',lw=1)
                ax.text(s['cutoff']+.4,.12,f'cutoff {s["cutoff"]}',transform=ax.get_xaxis_transform(),fontsize=9,color='#526472')
            finite=ys[np.isfinite(ys)]
            if len(finite):
                low,high=finite.min(),finite.max();span=max(high-low,.05)
                ax.set_ylim(low-.17*span,high+.25*span)
            else:
                ax.set_ylim(0,3)
                ax.text(.5,.53,'D unavailable at every dose',transform=ax.transAxes,ha='center',fontsize=13,color='#526472')
                reasons=sorted({p.get('reason','unspecified') for r in rr for p in r['dose_curve'] if p['status']!='ok'})
                ax.text(.5,.41,'N < 30: insufficient aircraft' if s['n_aircraft']<30 else '\n'.join(reasons),transform=ax.transAxes,ha='center',fontsize=11,color='#526472')
            ax.set(xlabel='Injected Holding aircraft',ylabel='Estimated D',xlim=(-.4,max(x)+.4))
            ax.grid(axis='y',alpha=.22,lw=.6)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=6,integer=True));ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        notes = [
            'Outcome-selected display: highest 6 of 7 archived pre-peak scene median coefficients; not a representative or confirmatory subset.' if prepeak else
            'Complement of the selected six: four scenes have no accepted D; September 18 has no eligible peak; September 26 has cutoff 7.',
            'Independent panel y-scales aid inspection; slopes across panels are not comparable. Missing estimates break lines; no smoothing.',
            'Hour-based source selection; complete injected tails retained, not clipped to hour boundaries. R² ≥ 0.98 unchanged.',
            'Cutoffs were outcome-selected. Full 12-scene evidence and the separate endpoint equal-duration control remain in the existing report.']
        for y,text in zip([.081,.06,.039,.018],notes):fig.text(.075,y,text,fontsize=9.5,color='#526472')
        for ext in ['png','pdf','svg']:fig.savefig(out/f'{name}.{ext}',dpi=220,facecolor='white')
        plt.close(fig)
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    manifest=dict(source_sha256=hashes,new_D_calls=0,new_encoder_calls=0,changed_cutoffs=0,
                  selection_rule='Largest six archived pre-peak scene median order Spearman coefficients; ties by scene ID',
                  selected=[s['scene_id'] for s in selected],remaining=[s['scene_id'] for s in remaining],
                  rank=[dict(scene=s['scene_id'],rho=s['retained']['median']) for s in ranked],
                  selected_range='Archived pre-peak, peak included',remaining_range='Full dose range')
    (out/'render-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    table='\n'.join(f'| {i+1} | {s["scene_id"]} | {label(s)} | {s["retained"]["median"]:.3f} | {"Selected" if s["scene_id"] in ids else "Complement"} |' for i,s in enumerate(ranked))
    (out/'README.md').write_text('''# Six-scene Holding display preview

Saved corrected 10-second midpoint results only. No experiment rerun, model inference, new D fit, threshold change or peak search. The previous complete presentation remains unchanged.

The first figure selects the six highest archived pre-peak **scene median order correlations**, not the most visually attractive curves. This is deliberately outcome-selected and cannot be presented as representative independent validation. The seventh eligible scene (September 26 local) is retained with the five scenes without an archived cutoff in the second figure. All 12 scene IDs occur exactly once across the pair.

![Six selected, archived pre-peak ranges](holding-six-selected-prepeak.png)

![Other six, full ranges](holding-six-remaining-full-range.png)

The first figure shows only each stored pre-peak range; the second shows complete ranges because five scenes have no accepted peak. Correlation labels therefore refer to different ranges. September 26's pre-peak median is 0.762, whereas its full-range median is -0.045. No new cutoff is substituted for the five unavailable peaks. Full curves for the selected six remain in the existing all-12 midpoint appendix. Panel-specific y-scales are disclosed; apparent slopes cannot compare effect sizes. Source-hour selection preserves complete extended tracks, not post-injection hour clipping.

| Rank | UTC scene | Local UTC+08 | Archived pre-peak median rho | Display group |
|---|---|---|---:|---|
'''+table+'\n',encoding='utf8')
    print(json.dumps(manifest['rank'],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():p.error('Choose a new output directory; prior renders are protected.')
    args.output.mkdir(parents=True)
    render(args.output)
