import json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path

repo=Path(__file__).resolve().parents[2]
hr=repo/'evaluation/runs/holding-equal-duration/results'
vr=repo/'evaluation/runs/segmented-15km/results'
hs=json.load(open(hr/'summary.json'))
hrec=json.load(open(hr/'paired-dose-records.json'))
vs=json.load(open(vr/'segmented/summary.json'))
vexp=json.load(open(vr/'segmented/experiment-results.json'))['qc500_safe']['vectoring']['scenes']

PASTEL=['#A6CEE3','#B2DF8A','#CAB2D6','#FDBF6F','#A6D8D4']
BLACK='#1A1A1A'; GREY='#6B7280'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.4,'axes.titlesize':9.2,'axes.labelsize':8.4,'xtick.labelsize':7.6,'ytick.labelsize':7.6,'axes.linewidth':.6})
fig,axes=plt.subplots(3,2,figsize=(12.0,9.0),gridspec_kw={'hspace':.43,'wspace':.22})
hsce=[('2026-09-01T01Z','09-01 09:00'),('2026-09-04T08Z','09-04 16:00'),('2026-09-10T06Z','09-10 14:00')]
vsce=[('2026-09-15T07Z','09-15 15:00'),('2026-09-19T07Z','09-19 15:00'),('2026-09-27T05Z','09-27 13:00')]
for row,(sid,label) in enumerate(hsce):
    ax=axes[row,0]
    for rep in range(5):
        pts=[(r['dose'],r['holding_D']) for r in hrec if r['scene']==sid and r['replicate']==rep and r['holding_D'] is not None]
        if pts:
            ax.scatter([p[0] for p in pts],[p[1] for p in pts],s=9,color=PASTEL[rep],alpha=.65,edgecolors='none',zorder=2)
    bh={}; bs={}
    for r in hrec:
        if r['scene']==sid:
            if r['holding_D'] is not None: bh.setdefault(r['dose'],[]).append(r['holding_D'])
            if r['straight_D'] is not None: bs.setdefault(r['dose'],[]).append(r['straight_D'])
    dh=sorted(bh); ds=sorted(bs)
    ax.plot(dh,[np.mean(bh[d]) for d in dh],color=BLACK,lw=1.8,zorder=4)
    ax.plot(ds,[np.mean(bs[d]) for d in ds],color=GREY,lw=1.2,ls='--',zorder=3)
    sc=next(s for s in hs['scene_details'] if s['scene']==sid)
    c=sc['common_correlations']
    ax.set_title(f'{label} · $N$={sc["n_aircraft"]}\n$\\rho$ H={c["holding"]["median"]:.2f}, S={c["straight"]["median"]:.2f}',loc='left')
    ax.set_xlabel('Injected holding aircraft (count)')
    ax.grid(True,color='#E5E5E5',lw=.6,zorder=0)
for row,(sid,label) in enumerate(vsce):
    ax=axes[row,1]
    by={}
    offsets=np.linspace(-.16,.16,5)
    for s in [x for x in vexp if x['scene_id']==sid]:
        pts=[(p['vectoring_aircraft'],p['dimension']) for p in s['dose_curve'] if p['status']=='ok' and p['dimension'] is not None]
        ax.plot([p[0] for p in pts],[p[1] for p in pts],color=PASTEL[s['replicate']],lw=.7,alpha=.55,zorder=1)
        ax.scatter([p[0]+offsets[s['replicate']] for p in pts],[p[1] for p in pts],s=12,color=PASTEL[s['replicate']],alpha=.8,edgecolors='white',linewidths=.35,zorder=2)
        for p in s['dose_curve']:
            if p['status']=='ok' and p['dimension'] is not None: by.setdefault(p['vectoring_aircraft'],[]).append(p['dimension'])
    ds=sorted(by)
    ax.plot(ds,[np.mean(by[d]) for d in ds],color=BLACK,lw=1.8,zorder=4)
    sc=next(s for s in vs['scenes'] if s['scene_id']==sid)['retained']
    ax.set_title(f'{label} · $N$={next(s for s in vs["scenes"] if s["scene_id"]==sid)["n_aircraft"]}\nmedian $\\rho$={sc["median"]:.2f}, {sc["positive"]}/{sc["n"]} positive',loc='left')
    ax.set_xlabel('Injected vectoring aircraft (count)')
    ax.grid(True,color='#E5E5E5',lw=.6,zorder=0)
for ax in axes[:,0]:
    ax.set_ylabel('Correlation dimension $D$')
for ax in axes.ravel():
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.tick_params(pad=2)

handles=[Line2D([0],[0],marker='o',color='none',markerfacecolor=PASTEL[i],markersize=4,label=f'order {i+1}') for i in range(5)]
handles += [Line2D([0],[0],color=BLACK,lw=1.8,label='mean'),
            Line2D([0],[0],color=GREY,lw=1.2,ls='--',label='straight mean')]
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(0.5,0.985),ncol=7,frameon=False,fontsize=7.6,handletextpad=.4,columnspacing=1.2)
fig.text(0.27,0.952,'Holding',ha='center',va='top',fontsize=11)
fig.text(0.755,0.952,'Vectoring',ha='center',va='top',fontsize=11)
fig.tight_layout(rect=(0,0,1,0.94))
out=repo/'evaluation/figures'
for ext in ['png','pdf']:
    fig.savefig(out/f'holding-vs-vectoring-comparison.{ext}',dpi=300,bbox_inches='tight')
print('saved',out)
