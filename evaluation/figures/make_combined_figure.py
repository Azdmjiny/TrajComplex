import json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

repo=Path(__file__).resolve().parents[2]
hr=repo/'evaluation/runs/holding-equal-duration/results'
vr=repo/'evaluation/runs/segmented-15km/results'
hrec=json.load(open(hr/'paired-dose-records.json'))
vexp=json.load(open(vr/'segmented/experiment-results.json'))['qc500_safe']['vectoring']['scenes']

C_H='#1F4E79'; C_S='#777777'; C_V='#B35C1E'; C_T='#8C8C8C'
plt.rcParams.update({
    'font.family':'DejaVu Serif','mathtext.fontset':'dejavuserif','font.size':8.5,
    'axes.titlesize':9.2,'axes.labelsize':8.6,'xtick.labelsize':7.8,'ytick.labelsize':7.8,
    'axes.linewidth':0.6,'xtick.major.width':0.6,'ytick.major.width':0.6,
    'xtick.direction':'out','ytick.direction':'out','legend.fontsize':7.4,
})
fig,axes=plt.subplots(1,2,figsize=(7.2,2.95),gridspec_kw={'wspace':0.32})
ax=axes[0]
# holding 09-04, median + IQR across replicates
sid='2026-09-04T08Z'
for arm,color,ls,label in [('holding',C_H,'-','Holding'),('straight',C_S,'--','Straight')]:
    by={}
    for r in hrec:
        if r['scene']==sid and r[arm+'_D'] is not None:
            by.setdefault(r['dose'],[]).append(r[arm+'_D'])
    ds=sorted(by); med=[np.median(by[d]) for d in ds]
    lo=[np.percentile(by[d],25) for d in ds]; hi=[np.percentile(by[d],75) for d in ds]
    ax.fill_between(ds,lo,hi,color=color,alpha=.10,lw=0,zorder=1)
    ax.plot(ds,med,color=color,ls=ls,lw=1.8,label=label,zorder=3)
ax.set_xlabel('Aircraft with +240 s appended')
ax.set_ylabel('Correlation dimension $D$')
ax.set_title('(a) Holding · 09-04 16:00',loc='left',pad=6)
ax.text(.03,.96,'Holding $\\rho$ = 0.82\nStraight $\\rho$ = 0.67',transform=ax.transAxes,va='top',ha='left',fontsize=7.4,color='#333333')
ax.legend(loc='lower right',frameon=False,handlelength=1.8)
ax.set_xlim(5,35)
ax.grid(False)

ax=axes[1]
sid='2026-09-15T07Z'
rows=[s for s in vexp if s['scene_id']==sid]
by={}
for s in rows:
    for p in s['dose_curve']:
        if p['status']=='ok' and p['dimension'] is not None:
            by.setdefault(p['vectoring_aircraft'],[]).append(p['dimension'])
    pts=[(p['vectoring_aircraft'],p['dimension']) for p in s['dose_curve'] if p['status']=='ok' and p['dimension'] is not None]
    ax.plot([p[0] for p in pts],[p[1] for p in pts],color=C_T,lw=.65,alpha=.75,zorder=1)
ds=sorted(by); med=[np.median(by[d]) for d in ds]
ax.plot(ds,med,color=C_V,lw=2.0,marker='o',ms=3.4,mfc='white',mew=.8,zorder=3)
ax.set_xlabel('Aircraft with 15 km vectoring')
ax.set_title('(b) Vectoring · 09-15 15:00',loc='left',pad=6)
ax.text(.03,.96,'median $\\rho$ = 0.96\n5/5 orders positive',transform=ax.transAxes,va='top',ha='left',fontsize=7.4,color='#333333')
ax.set_xticks(ds)
ax.grid(False)

for ax in axes:
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.tick_params(pad=2)

fig.tight_layout()
out=repo/'evaluation/figures'
for ext in ['png','pdf']:
    fig.savefig(out/f'holding-vs-vectoring-comparison.{ext}',dpi=300,bbox_inches='tight')
print('saved',out)

