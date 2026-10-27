"""Render all saved maneuver scenes. No inference, D fitting, or resampling.

python evaluation/code/make_review_figures.py --output /new/local/figure-package
Only reviewed figures/report may be published; keep the hash manifest local.
"""
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
BLUE, ORANGE, PURPLE = '#2166ac', '#c66312', '#73569c'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(sid):
    return (datetime.strptime(sid, '%Y-%m-%dT%HZ') + timedelta(hours=8)).strftime('%m-%d %H:00')


def number(x):
    return 'NA' if x is None else f'{x:.3f}'


def accepted(p):
    return p['dimension'] if p['status'] == 'ok' else np.nan


def median_columns(values):
    a = np.asarray(values, float)
    return np.array([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else np.nan for c in a.T])


def save(fig, out, name, footer):
    fig.text(.5, .015, footer, ha='center', va='bottom', fontsize=9, linespacing=1.5)
    fig.tight_layout(rect=(0, .065, 1, .92), h_pad=2.8, w_pad=2.4)
    for ext in ['png', 'pdf', 'svg']:
        fig.savefig(out / (name + '.' + ext), dpi=220)
    plt.close(fig)


def holding(out, runs, summary, cutoff, pairs):
    scenes = sorted({r['scene'] for r in runs})
    details = {r['scene']: r for r in summary['scene_details']}
    cut = {r['scene']: r for r in cutoff['scene_details']}
    fig, axes = plt.subplots(4, 3, figsize=(16.5, 16), sharey=True)
    fig.suptitle('Holding versus equal-duration straight flight | all 12 scenes\nFull dose range; each selected aircraft receives 240 seconds at the trajectory endpoint', fontsize=17, y=.99)
    fig.legend(handles=[Line2D([], [], color=c, lw=2.7, label=t) for c,t in [(BLUE,'Holding'), (ORANGE,'Straight flight')]] + [Line2D([],[],color='gray',lw=.8,label='Thin: individual orders'), Line2D([],[],color='gray',lw=2.7,label='Thick: available-order median')], loc='upper center', bbox_to_anchor=(.5,.95), ncol=4, frameon=False)
    for ax, sid in zip(axes.flat, scenes):
        rr = sorted([r for r in runs if r['scene']==sid], key=lambda r:r['replicate'])
        d = details[sid]; c = cut[sid]['cutoff']
        x = [p['injected_aircraft'] for p in rr[0]['curves']['holding']]
        valid_counts=[]
        for arm, color, rail in [('holding',BLUE,.025), ('straight',ORANGE,.055)]:
            ys = [[accepted(p) for p in r['curves'][arm]] for r in rr]
            for y in ys: ax.plot(x,y,color=color,lw=.65,alpha=.3,marker='.',ms=2)
            ax.plot(x,median_columns(ys),color=color,lw=2,marker='.',ms=3)
            valid_counts.append(int(np.isfinite(ys).sum()))
            bad = np.array([np.sum(~np.isfinite(np.asarray(ys)[:,i])) for i in range(len(x))])
            ax.scatter(np.array(x)[bad>0], np.full(sum(bad>0),rail), s=7+bad[bad>0]*4, marker='x', color=color, alpha=.55, transform=ax.get_xaxis_transform())
        if c is not None: ax.axvline(c,color='#555555',ls='--',lw=.9)
        co=d['common_correlations']
        ax.set_title(f'{local(sid)} UTC+08 | N={d["n_aircraft"]}\nValid H/S: {valid_counts[0]}/{valid_counts[1]} of {len(x)*len(rr)} each\nFull-range median rho H/S: {number(co["holding"]["median"])}/{number(co["straight"]["median"])}',fontsize=10,loc='left')
        if not any(valid_counts):
            reasons=Counter(p['reason'] for r in rr for p in r['curves']['holding'])
            ax.text(.5,.5,'No accepted D\n'+', '.join(reasons),transform=ax.transAxes,ha='center',va='center',fontsize=10,bbox=dict(fc='white',ec='none'))
        ax.set(xlabel='Injected aircraft',ylabel='Accepted D',xlim=(-.5,max(x)+.5)); ax.grid(alpha=.17)
    save(fig,out,'holding-all-scenes-dose','Dashed line: archived common cutoff, where available; later doses remain visible. Crosses at bottom mark failed order-dose fits.\nR² ≥ 0.98 throughout. Five orders are dependent repeats. Lines break at NA; medians may use different available orders at each dose.')

    fig,axes=plt.subplots(4,3,figsize=(16.5,16),sharey=True)
    fig.suptitle('Holding minus equal-duration straight flight | matched order and aircraft dose\nPositive values mean higher D for Holding; all 12 scenes retained',fontsize=17,y=.99)
    fig.legend(handles=[Line2D([],[],color=PURPLE,lw=.7,alpha=.55,label='Individual paired orders'),Line2D([],[],color=PURPLE,lw=2.6,label='Available-pair median'),Line2D([],[],color='gray',ls='--',label='Archived common cutoff')],loc='upper center',bbox_to_anchor=(.5,.95),ncol=3,frameon=False)
    for ax,sid in zip(axes.flat,scenes):
        rr=[r for r in pairs if r['scene']==sid]; orders=sorted({r['replicate'] for r in rr});x=sorted({r['dose'] for r in rr})
        ys=[]
        for order in orders:
            lookup={r['dose']:r for r in rr if r['replicate']==order}
            y=[lookup[k]['holding_minus_straight'] if lookup[k]['jointly_valid'] else np.nan for k in x]
            for k, val in zip(x,y):
                if np.isfinite(val): assert abs(val-(lookup[k]['holding_D']-lookup[k]['straight_D']))<1e-12
            ys.append(y);ax.plot(x,y,color=PURPLE,alpha=.32,lw=.8,marker='.',ms=2)
        ax.plot(x,median_columns(ys),color=PURPLE,lw=2,marker='.',ms=3)
        ax.axhline(0,color='#555555',lw=.8)
        c=cut[sid]['cutoff']
        if c is not None: ax.axvline(c,color='gray',ls='--',lw=.9)
        n=sum(r['jointly_valid'] and r['dose']>0 for r in rr)
        absent=np.any(~np.isfinite(np.asarray(ys)),axis=0)
        ax.scatter(np.array(x)[absent],np.full(sum(absent),.025),transform=ax.get_xaxis_transform(),marker='x',s=12,color='gray',alpha=.5)
        ax.set_title(f'{local(sid)} UTC+08 | N={details[sid]["n_aircraft"]}\nAccepted nonzero pairs: {n}/{sum(r["dose"]>0 for r in rr)}\nShared-cutoff scene difference: {number(cut[sid]["paired_difference_median"])}',fontsize=10,loc='left')
        if not n: ax.text(.5,.65,'No accepted pairs\nInsufficient aircraft',transform=ax.transAxes,ha='center',fontsize=10)
        ax.set(xlabel='Injected aircraft',ylabel='D(Holding) − D(Straight)',xlim=(-.5,max(x)+.5));ax.grid(alpha=.17)
    save(fig,out,'holding-all-scenes-paired-difference','Both arms must pass at the same dose and order; missing pairs are NA (bottom crosses), never zero. No valid baseline is required for this difference.\nThe title statistic uses the saved median-of-order-medians within the common cutoff; it is not the median of the plotted curve. No confidence band or causal attribution.')


def vectoring(out, data, summaries):
    scenes=sorted({r['scene_id'] for r in data['segmented']})
    palette=plt.get_cmap('tab10').colors[:5]
    fig,axes=plt.subplots(2,4,figsize=(19,10.5),sharey=True)
    fig.suptitle('Vectoring dose response | all four scenes and both saved 15 km shapes\nAccepted D on a common y-axis; no truncation or scene selection',fontsize=17,y=.99)
    handles=[Line2D([],[],color=c,marker='o',lw=1,label=f'Order {i+1}') for i,c in enumerate(palette)]+[Line2D([],[],color='black',lw=2.6,label='Available-order median')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.94),ncol=6,frameon=False)
    for row,arm in enumerate(['segmented','smooth-control']):
        for col,sid in enumerate(scenes):
            ax=axes[row,col];rr=sorted([r for r in data[arm] if r['scene_id']==sid],key=lambda r:r['replicate'])
            ss=next(r for r in summaries[arm]['scenes'] if r['scene_id']==sid)
            x=[p['vectoring_aircraft'] for p in rr[0]['dose_curve']];ys=[]
            for r,color in zip(rr,palette):
                y=[accepted(p) for p in r['dose_curve']];ys.append(y);ax.plot(x,y,color=color,alpha=.72,marker='o',ms=3,lw=1)
                bad=~np.isfinite(y)
                if any(bad): ax.scatter(np.array(x)[bad],np.full(sum(bad),.025),transform=ax.get_xaxis_transform(),marker='x',color=color)
            ax.plot(x,median_columns(ys),color='black',lw=2.2,marker='.',ms=5)
            valid=int(np.isfinite(ys).sum())
            rho=ss['full']['median'];rho_text='rho NA: only 4 doses (<5 required)' if rho is None else f'Median order rho={rho:.3f}; positive {ss["full"]["positive"]}/{ss["full"]["n"]}'
            ax.set_title(f'{local(sid)} UTC+08 | N={rr[0]["n_aircraft"]}\n{rr[0]["n_vectoring_eligible"]} candidates | D fits: {valid}/{len(x)*len(rr)}\n{rho_text}',fontsize=9.5,loc='left')
            ax.set(xlabel='Injected aircraft',xticks=x,ylabel=('Segmented 15 km' if row==0 else 'Smooth 15 km')+'\nAccepted D');ax.grid(alpha=.2)
    save(fig,out,'vectoring-all-scenes-dose','All 115 D fits per shape pass R² ≥ 0.94; the first scene lacks enough dose levels for correlation, not for D. Negative-order responses remain visible.\nSegmented: schematic stimulus without the smooth motion certificate. Smooth: screened control. Five orders are dependent, not independent scenes.')

    fig,axes=plt.subplots(2,2,figsize=(12.5,9.5),sharey=True)
    fig.suptitle('Vectoring dose–D correlation | every order, including negative and unavailable\nSegmented: 13/15 positive, median 0.829 | Smooth: 9/15 positive, median 0.600',fontsize=15,y=.99)
    for ax,sid in zip(axes.flat,scenes):
        for offset,arm,color,label in [(-.12,'smooth-control',BLUE,'Smooth'),(.12,'segmented',ORANGE,'Segmented')]:
            rows=sorted([r for r in summaries[arm]['curves'] if r['scene']==sid],key=lambda r:r['replicate'])
            x=np.array([r['replicate']+1 for r in rows])+offset
            y=[r['full']['rho'] if r['full']['rho'] is not None else np.nan for r in rows]
            ax.scatter(x,y,color=color,s=48,label=label,zorder=3)
            for xx,yy in zip(x,y):
                if np.isfinite(yy): ax.vlines(xx,0,yy,color=color,alpha=.3,lw=1)
            if not np.isfinite(y).any(): ax.text(.5,.65 if arm=='segmented' else .47,f'{label}: all 5 orders NA',transform=ax.transAxes,ha='center',color=color,bbox=dict(fc='white',ec='none'),zorder=5)
        ax.axhline(0,color='#555555',ls='--',lw=1)
        ax.set(title=local(sid)+' UTC+08',xlabel='Injection order',ylabel='Spearman rho',xticks=range(1,6),ylim=(-1.13,1.13),xlim=(.5,5.5));ax.grid(axis='y',alpha=.2)
        if sid==scenes[0]:ax.text(.5,.28,'4 valid doses; at least 5 required\nNo coefficient is assigned',transform=ax.transAxes,ha='center',fontsize=10)
    fig.legend(*axes.flat[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,.93),ncol=2,frameon=False)
    save(fig,out,'vectoring-all-scenes-correlations','Coefficients are read from saved full-range summaries, not computed from median curves. All 20 planned order curves per shape are accounted for.\nNo p-values or confidence intervals: orders share the same scene. These results concern the two 15 km stimuli, not vectoring in general.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists(): parser.error('Output already exists; choose a new directory.')
    paths=[study_path('holding-equal-duration/results')/n for n in ['experiment-results.json','summary.json','paired-dose-records.json']]
    paths += [study_path('holding-equal-duration-old-cutoff/results/summary.json')]
    paths += [study_path('segmented-15km/results')/a/n for a in ['segmented','smooth-control'] for n in ['summary.json','experiment-results.json']]
    before={str(p.relative_to(ROOT)):sha(p) for p in paths}
    h,hs,pairs,cut=map(read,paths[:4]);summaries={};data={}
    for arm in ['segmented','smooth-control']:
        base=study_path('segmented-15km/results')/arm
        summaries[arm]=read(base/'summary.json');data[arm]=read(base/'experiment-results.json')['qc500_safe']['vectoring']['scenes']
        assert len(data[arm])==20
        for r in data[arm]:
            c=next(c for c in summaries[arm]['curves'] if c['scene']==r['scene_id'] and c['replicate']==r['replicate'])
            assert sum(p['status']=='ok' for p in r['dose_curve'])==c['full']['valid']
            assert all(p['config']['min_r_squared']==.94 for p in r['dose_curve'])
    assert len(h)==60 and len({r['scene'] for r in h})==12
    assert all(p['config']['min_r_squared']==.98 for r in h for ps in r['curves'].values() for p in ps)
    args.output.mkdir(parents=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    holding(args.output,h,hs,cut,pairs);vectoring(args.output,data,summaries)
    assert all(sha(ROOT/p)==s for p,s in before.items())
    manifest={'new_D_calls':0,'new_encoder_calls':0,'new_draws':0,'threshold_changes':0,'holding_scenes':12,'vectoring_scenes':4,'source_sha256':before,'figure_sha256':{p.name:sha(p) for p in args.output.iterdir()}}
    (args.output/'render-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    print('Rendered 4 figure sets (PNG/PDF/SVG); all saved source hashes unchanged.')


if __name__=='__main__': main()
