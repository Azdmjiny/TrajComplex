import json, numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from datetime import datetime,timedelta

ROOT=Path(r'C:\Users\HP\Documents\ChatGPT\UVA World Model')
R=ROOT/'tmp/WM4ATM/evaluation/runs/holding-equal-duration/results'
runs=json.load(open(R/'experiment-results.json')); summary=json.load(open(R/'summary.json'))
det={s['scene']:s for s in summary['scene_details']}
# estimable scenes only
scenes=[s for s in sorted(det) if det[s]['common_correlations']['holding']['valid']>0]
print('scenes',scenes)
BLUE='#2166ac'; ORANGE='#c66312'
def local(sid): return (datetime.strptime(sid,'%Y-%m-%dT%HZ')+timedelta(hours=8)).strftime('%m-%d %H:00')
def acc(p): return p['dimension'] if p['status']=='ok' else np.nan
fig,axes=plt.subplots(2,4,figsize=(15.5,7.8),sharex=False)
fig.suptitle('Holding versus equal-duration straight flight | 8 estimable scenes\nMean of available orders; each selected aircraft receives 240 seconds at the endpoint',fontsize=14,y=.99)
fig.legend(handles=[Line2D([],[],color=BLUE,lw=2.3,label='Holding'),Line2D([],[],color=ORANGE,lw=2.3,label='Straight'),
                    Line2D([],[],color='gray',lw=.7,alpha=.5,label='individual orders')],loc='upper center',bbox_to_anchor=(.5,.94),ncol=3,frameon=False,fontsize=9)
for ax,sid in zip(axes.flat,scenes):
    rr=sorted([r for r in runs if r['scene']==sid],key=lambda r:r['replicate'])
    x=[p['injected_aircraft'] for p in rr[0]['curves']['holding']]
    for arm,color in [('holding',BLUE),('straight',ORANGE)]:
        ys=np.array([[acc(p) for p in r['curves'][arm]] for r in rr],float)
        for y in ys: ax.plot(x,y,color=color,lw=.55,alpha=.22)
        mean=np.array([np.nanmean(c) if np.isfinite(c).any() else np.nan for c in ys.T])
        ax.plot(x,mean,color=color,lw=1.9)
    co=det[sid]['common_correlations']
    ax.set_title(f'{local(sid)} · N={det[sid]["n_aircraft"]}\nρ H={co["holding"]["median"]:.2f}, S={co["straight"]["median"]:.2f}',fontsize=8.5,loc='left')
    ax.set_xlabel('Injected aircraft'); ax.grid(True,color='#E5E7EB',lw=.5)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.tick_params(labelsize=7.5)
for i,ax in enumerate(axes.flat):
    if i%4==0: ax.set_ylabel('Accepted D',fontsize=8)
fig.tight_layout(rect=(0,0,1,.92),h_pad=1.8,w_pad=1.5)
out=ROOT/'deliverables/holding-redraw-2026-10-26'
for ext in ['png','pdf']: fig.savefig(out/f'holding-8-scenes-mean.{ext}',dpi=300,bbox_inches='tight')
print('saved',out)
