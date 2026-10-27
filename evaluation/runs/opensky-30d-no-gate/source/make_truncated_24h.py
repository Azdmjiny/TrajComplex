import json,numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SRC=Path(r'deliverables/opensky-30d-no-gate-2026-10-26')
rows=json.load(open(SRC/'results/d-vs-n-no-gate.json'))['rows']
DATES=['2026-09-08','2026-09-11']
floor=min(r['curve'][-1] for r in rows if r['curve'] and r['N']>=15)
summary={}
fig,axes=plt.subplots(2,1,figsize=(10.8,6.6),sharex=True,gridspec_kw={'hspace':.28})
for ax,day in zip(axes,DATES):
    rr=sorted([r for r in rows if r['local_date']==day],key=lambda r:r['local_hour'])
    h=[r['local_hour'] for r in rr]; raw=[r['curve'][-1] if r['curve'] else np.nan for r in rr]
    trunc=[x if r['N']>=15 else floor for x,r in zip(raw,rr)]
    n=[r['N'] for r in rr]
    ax.plot(h,raw,'o--',color='#9CA3AF',lw=.9,ms=3,label='raw full-scene slope')
    ax.plot(h,trunc,'-o',color='#1F4E79',lw=1.8,ms=4,label='truncated at N=15')
    assigned=[i for i,r in enumerate(rr) if r['N']<15]
    ax.scatter([h[i] for i in assigned],[floor]*len(assigned),marker='v',s=55,color='#B35C1E',zorder=5,label='assigned floor (N<15)')
    ax.axhline(floor,color='#B35C1E',ls=':',lw=.8)
    ax.set_ylabel('raw log–log slope'); ax.set_ylim(min(floor,min(raw))-.08,max(raw)+.08)
    ax.set_title(f'{day} (UTC+08) · threshold N=15 · floor={floor:.3f}',loc='left')
    ax.grid(True,color='#E5E7EB',lw=.55); ax.set_xlim(-.5,23.5); ax.set_xticks(range(0,24,2))
    ax2=ax.twinx(); ax2.bar(h,n,width=.55,color='#C9D6E4',alpha=.4,zorder=0); ax2.set_ylabel('N',color='#6B7280'); ax2.set_ylim(0,max(n)*1.18)
    if ax is axes[0]: ax.legend(loc='upper left',frameon=False,fontsize=7.4)
    summary[day]={'affected':[dict(hour=r['local_hour'],N=r['N'],raw=float(r['curve'][-1])) for r in rr if r['N']<15],
                  'n_min':min(n),'n_median':float(np.median(n)),'floor':float(floor)}
axes[-1].set_xlabel('Local hour (UTC+08)')
fig.tight_layout(); fig.savefig(SRC/'figures'/'24h-threshold15-truncated.png',dpi=300,bbox_inches='tight')
fig.savefig(SRC/'figures'/'24h-threshold15-truncated.pdf')
json.dump(summary,open(SRC/'results/truncation-threshold15.json','w'),indent=2)
print('floor',floor); print(json.dumps(summary,indent=2))
