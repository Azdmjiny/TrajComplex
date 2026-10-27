"""Paper layout from immutable Holding results; no inference or estimation.

Keep generated manifests local. Publish only reviewed figures and text.
"""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
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

ROOT = EVALUATION_ROOT
COLORS = ['#2378a5', '#5a9a70', '#af81af', '#cf8a45', '#68aeb2']
NAVY, GREY = '#173f60', '#828b95'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p):
    return json.loads(p.read_text(encoding='utf8'))


def assemble():
    full = study_path('holding-equal-duration/results')
    cut = study_path('holding-equal-duration-old-cutoff/results')
    files = [full/'experiment-results.json', full/'paired-dose-records.json',
             full/'summary.json', cut/'summary.json', cut/'repeat-summary.json']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
    runs, pairs, full_summary, summary, repeats = [load(p) for p in files]
    selected = [s for s in summary['scene_details'] if s['cutoff'] is not None]
    assert len(selected) == 7 and len(summary['scene_details']) == 12
    assert len(runs) == 60
    assert all(p['config']['min_r_squared'] == .98 for r in runs for p in r['curves']['holding'])
    lookup = {(r['scene'], r['replicate']): r for r in repeats}
    # Confirm the displayed coefficients refer to the same jointly valid pairs
    # within the stored cutoff. Never derive a new cutoff or refit D.
    for s in selected:
        for order in range(5):
            accepted = [p for p in pairs if p['scene']==s['scene'] and p['replicate']==order
                        and p['dose']<=s['cutoff'] and p['jointly_valid']]
            c = lookup[s['scene'], order]['common_valid']['holding']
            assert len(accepted) == c['valid']
            assert (c['rho'] is None) == (len(accepted)<5)
    coeffs = [lookup[s['scene'], k]['common_valid']['holding']['rho'] for s in selected for k in range(5)]
    valid = [v for v in coeffs if v is not None]
    assert len(valid)==33 and sum(v>0 for v in valid)==30 and sum(v<0 for v in valid)==3
    assert np.isclose(np.median(valid), summary['common_valid']['holding']['median'])
    return runs, selected, lookup, summary, full_summary, hashes


def draw(out, show_full_tail=False):
    runs, scenes, lookup, summary, full_summary, hashes = assemble()
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10,
                         'axes.spines.top':False, 'axes.spines.right':False,
                         'axes.edgecolor':'#a5aeb8', 'axes.labelcolor':'#273744',
                         'xtick.color':'#475664', 'ytick.color':'#475664',
                         'pdf.fonttype':42, 'svg.fonttype':'none'})
    fig, axes = plt.subplots(2,4,figsize=(18.6,10.4))
    fig.subplots_adjust(left=.055,right=.985,bottom=.17,top=.79,wspace=.29,hspace=.52)
    fig.suptitle('Holding dose–dimension response',x=.055,y=.975,ha='left',fontsize=23,fontweight='bold',color=NAVY)
    subtitle = 'Historical dose ranges highlighted; complete later-dose results retained' if show_full_tail else 'Only archived historical dose ranges shown; full ranges and control in Appendix H'
    fig.text(.055,.934,subtitle,fontsize=13,color='#536575')
    handles=[Line2D([],[],color=c,marker='o',ls='',ms=5,label=f'Order {i+1}') for i,c in enumerate(COLORS)]
    handles += [Line2D([],[],color=NAVY,lw=2.6,label='Available-order median')]
    if show_full_tail:
        handles += [Line2D([],[],color=GREY,lw=2,label='Later-dose median'),
                    Line2D([],[],color='#64717d',lw=1,ls='--',label='Archived cutoff')]
    fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.05,.903),ncol=4,
               frameon=False,fontsize=10,handlelength=2.2,columnspacing=2.3,labelspacing=.9)

    for i,(ax,s) in enumerate(zip(axes.flat,scenes)):
        sid, cutoff = s['scene'],s['cutoff']
        rr=sorted([r for r in runs if r['scene']==sid],key=lambda r:r['replicate'])
        x=np.array([p['injected_aircraft'] for p in rr[0]['curves']['holding']])
        ys=np.array([[p['dimension'] if p['status']=='ok' else np.nan
                      for p in r['curves']['holding']] for r in rr],float)
        for r,y,c in zip(rr,ys,COLORS):
            # NA remains in the arrays; no line bridges a failed dose.
            ax.plot(x,np.where(x<=cutoff,y,np.nan),color=c,lw=.65,alpha=.42,zorder=2)
            ax.scatter(x[x<=cutoff],y[x<=cutoff],color=c,s=13,alpha=.7,linewidths=0,zorder=3)
            if show_full_tail:
                ax.plot(x,np.where(x>=cutoff,y,np.nan),color='#b3bac2',lw=.7,alpha=.65,zorder=1)
                ax.scatter(x[x>cutoff],y[x>cutoff],color='#b3bac2',s=9,alpha=.65,linewidths=0,zorder=2)
        med=np.array([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else np.nan for c in ys.T])
        ax.plot(x,np.where(x<=cutoff,med,np.nan),color=NAVY,lw=2.4,zorder=4)
        if show_full_tail:
            ax.plot(x,np.where(x>=cutoff,med,np.nan),color=GREY,lw=2,zorder=4)
            ax.axvspan(cutoff,max(x)+.5,color='#e9edf1',alpha=.55,zorder=0)
            ax.axvline(cutoff,color='#64717d',ls='--',lw=1,zorder=3)
        rho=s['common_valid']['holding']['median'];n=s['common_valid']['holding']['n']
        retained=int(np.isfinite(ys[:,x<=cutoff]).sum());total=5*int(sum(x<=cutoff))
        ax.set_title(f'{chr(65+i)}  {s["local_UTC8"]} | N={s["N"]}\nMedian order ρ = {rho:.3f}  ·  {n}/5 estimable',loc='left',fontsize=11,color=NAVY,pad=12)
        ax.text(.02,.97,f'Cutoff: {cutoff} aircraft\nAccepted Holding fits: {retained}/{total}',transform=ax.transAxes,
                va='top',fontsize=8.5,color='#536575',bbox=dict(fc='white',ec='none',alpha=.9,pad=3))
        ax.set(xlabel='Injected Holding aircraft',ylabel='Accepted D',xlim=(-.3,(max(x) if show_full_tail else cutoff)+.3))
        # Tail omission is explicit in the figure and report; cutoff is unchanged.
        displayed = ys if show_full_tail else ys[:,x<=cutoff]
        low,high=np.nanmin(displayed),np.nanmax(displayed);span=max(high-low,.05)
        ax.set_ylim(low-.08*span,high+.30*span)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5,integer=True));ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.grid(axis='y',alpha=.22,lw=.6)

    ax=axes.flat[7]
    for i,s in enumerate(scenes):
        for k,c in enumerate(COLORS):
            rho=lookup[s['scene'],k]['common_valid']['holding']['rho']
            if rho is not None:ax.scatter(i+(k-2)*.10,rho,s=24,color=c,edgecolors='white',linewidth=.35,zorder=4)
        ax.hlines(s['common_valid']['holding']['median'],i-.29,i+.29,color=NAVY,lw=2,zorder=5)
    ax.axhline(0,color='#64717d',lw=1,ls='--')
    ax.set(ylim=(-1.08,1.10),xlim=(-.6,6.6),ylabel='Spearman ρ',xlabel='Scene (panels A–G)',xticks=range(7),xticklabels=list('ABCDEFG'))
    ax.set_title('H  All historical-range correlations\n30/33 positive  ·  pooled median ρ = 0.661',loc='left',fontsize=11,color=NAVY,pad=12)
    ax.text(.03,.045,'3 negative coefficients retained\n2/35 orders NA: A3 and G3',transform=ax.transAxes,fontsize=9,
            color='#536575',bbox=dict(fc='white',ec='none',alpha=.9))
    ax.grid(axis='y',alpha=.22,lw=.6)
    fig.text(.055,.115,'Scope: all 7 scenes with an archived cutoff (of 12 planned). Five scenes have no cutoff; all 12 appear in Appendix H.',fontsize=10,color=NAVY)
    fig.text(.055,.087,'ρ uses jointly valid Holding/straight doses within the cutoff; curves use available Holding fits. Missing doses break lines; panel y-scales differ.',fontsize=9.5,color='#536575')
    fig.text(.055,.059,'Historical cutoffs were outcome-derived, not independently validated operating limits. Equal-duration straight control: median ρ = 0.598 (Appendix H).',fontsize=9.5,color='#536575')
    fig.text(.055,.031,'R² ≥ 0.98 unchanged. Orders are dependent repeats; no confidence intervals or p-values. All scene times are UTC+08.',fontsize=9.5,color='#536575')
    for ext in ['png','pdf','svg']:fig.savefig(out/f'holding-historical-range-main.{ext}',dpi=300,facecolor='white')
    plt.close(fig)
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    manifest={'new_encoder_calls':0,'new_D_calls':0,'new_draws':0,'changed_cutoffs':0,'changed_thresholds':0,
              'source_sha256':hashes,'selected_scenes':[s['scene'] for s in scenes],
              'selection_rule':'All scenes with an already archived cutoff; no selection by new figure or coefficient',
              'show_full_tail':show_full_tail,
              'positive_order_correlations':30,'negative_order_correlations':3,'unavailable_order_correlations':2,
              'figure_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()}}
    (out/'render-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--show-full-tail',action='store_true',help='Reproduce the earlier view with grey later doses; default shows only stored cutoff ranges')
    args=p.parse_args()
    if args.output.exists():p.error('Use a new output directory; existing outputs are protected.')
    args.output.mkdir(parents=True);draw(args.output,args.show_full_tail)
    print('Rendered saved Holding results; 7 scenes, 33 coefficients, 2 unavailable; sources unchanged.')


if __name__=='__main__':main()
