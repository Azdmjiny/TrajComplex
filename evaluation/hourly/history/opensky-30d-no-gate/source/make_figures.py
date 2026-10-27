import json, numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, Normalize
from matplotlib.cm import ScalarMappable

SRC=Path(r'deliverables/opensky-30d-no-gate-2026-10-26')
d=json.load(open(SRC/'results/d-vs-n-no-gate.json'))
rows=d['rows']; cols={}
for r in rows:
    for n,v in zip(range(5,r['N']+1),r['curve']):
        if v is not None: cols.setdefault(n,[]).append(v)
ns=sorted(cols); med={n:float(np.median(cols[n])) for n in ns}
p10={n:float(np.percentile(cols[n],10)) for n in ns}; p90={n:float(np.percentile(cols[n],90)) for n in ns}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.5,'axes.titlesize':9.5,'axes.labelsize':8.8,
                     'xtick.labelsize':7.8,'ytick.labelsize':7.8,'axes.spines.top':False,'axes.spines.right':False})

# A: boxplots by N bin
bins=[(5,9),(10,14),(15,19),(20,24),(25,29),(30,34),(35,39),(40,44),(45,49),(50,54)]
data=[];labels=[];counts=[]
for lo,hi in bins:
    vals=[]; hours=0
    for r in rows:
        xs=[r['curve'][n-5] for n in range(lo,hi+1) if n>=5 and n<=r['N'] and r['curve'][n-5] is not None]
        if xs: vals.append(float(np.median(xs))); hours+=1
    data.append(vals);labels.append(f'{lo}–{hi}');counts.append(hours)
fig,axes=plt.subplots(2,1,figsize=(9.2,6.2),sharex=True,gridspec_kw={'height_ratios':[3,1],'hspace':.08})
ax=axes[0]
bp=ax.boxplot(data,positions=np.arange(len(data)),widths=.62,patch_artist=True,showfliers=False,medianprops=dict(color='black',lw=1.4),whiskerprops=dict(color='#4B5563'),capprops=dict(color='#4B5563'),boxprops=dict(edgecolor='#4B5563'))
for patch,v in zip(bp['boxes'],[np.median(x) for x in data]): patch.set_facecolor(plt.cm.viridis((v-.5)/1.8)); patch.set_alpha(.8)
ax.plot(np.arange(len(data)),[np.median(x) for x in data],'o-',color='#1F4E79',lw=1.2,ms=4,label='median of hourly medians')
ax.set_ylabel('raw log–log slope')
ax.set_title('A · all 720 raw hourly scenes · from 5 aircraft to all',loc='left')
ax.grid(True,axis='y',color='#E5E7EB',lw=.55)
ax.legend(loc='lower right',frameon=False,fontsize=7.2)
ax.set_xticks(np.arange(len(data))); ax.set_xticklabels([])
ax2=axes[1]; ax2.bar(np.arange(len(data)),counts,color='#9DB4CC',width=.62)
ax2.set_ylabel('hours'); ax2.set_xticks(np.arange(len(data))); ax2.set_xticklabels(labels,rotation=0)
ax2.set_xlabel('aircraft count bin')
ax2.grid(True,axis='y',color='#E5E7EB',lw=.55)
fig.tight_layout(); fig.savefig(SRC/'figures'/'A-boxplot-no-gate.png',dpi=300,bbox_inches='tight'); plt.close(fig)

# B: hexbin
x=np.array([n for r in rows for n,v in zip(range(5,r['N']+1),r['curve']) if v is not None],float)
y=np.array([v for r in rows for v in r['curve'] if v is not None],float)
fig,ax=plt.subplots(figsize=(8.4,5.6))
hb=ax.hexbin(x,y,gridsize=(28,30),mincnt=1,norm=LogNorm(),cmap='viridis',linewidths=.1)
ax.plot(ns,[med[n] for n in ns],color='white',lw=2.0,label='median')
ax.plot(ns,[p10[n] for n in ns],color='white',lw=.9,ls='--',label='10–90%')
ax.plot(ns,[p90[n] for n in ns],color='white',lw=.9,ls='--')
ax.set_xlabel('Number of aircraft in the scene'); ax.set_ylabel('raw log–log slope')
ax.set_title('B · density of all hourly medians, no quality gate',loc='left')
ax.grid(True,color='#E5E7EB',lw=.4,alpha=.5)
ax.legend(loc='upper left',frameon=True,facecolor='white',framealpha=.8,fontsize=7.2)
cb=fig.colorbar(hb,ax=ax); cb.set_label('hour-scene estimates')
fig.tight_layout(); fig.savefig(SRC/'figures'/'B-hexbin-no-gate.png',dpi=300,bbox_inches='tight'); plt.close(fig)

# C: band + one sample day (09-11)
fig,ax=plt.subplots(figsize=(8.6,5.4))
ax.fill_between(ns,[p10[n] for n in ns],[p90[n] for n in ns],color='#9DB4CC',alpha=.35,lw=0,label='10–90% across all hours')
ax.plot(ns,[med[n] for n in ns],color='#1F4E79',lw=2.2,label='median, all 720 hours')
cmap=plt.cm.viridis
sample=[r for r in rows if r['local_date']=='2026-09-11']
for r in sample:
    xs=list(range(5,r['N']+1)); ys=r['curve']
    ax.plot(xs,ys,color=cmap(r['local_hour']/23),lw=.8,alpha=.55,zorder=1)
ax.set_xlabel('Number of aircraft in the scene'); ax.set_ylabel('raw log–log slope')
ax.set_title('C · median and 10–90% band, all hours; colour = 09-11 local hour',loc='left')
ax.grid(True,color='#E5E7EB',lw=.55)
ax.legend(loc='upper left',frameon=False,fontsize=7.2)
sm=ScalarMappable(norm=Normalize(0,23),cmap=cmap); sm.set_array([])
cb=fig.colorbar(sm,ax=ax); cb.set_label('local hour (09-11)')
fig.tight_layout(); fig.savefig(SRC/'figures'/'C-band-curves-no-gate.png',dpi=300,bbox_inches='tight'); plt.close(fig)

# 24h two days
fig,axes=plt.subplots(2,1,figsize=(10.5,6.4),sharex=True,gridspec_kw={'hspace':.25})
for ax,day in zip(axes,['2026-09-08','2026-09-11']):
    rr=sorted([r for r in rows if r['local_date']==day],key=lambda r:r['local_hour'])
    h=[r['local_hour'] for r in rr]; dv=[r['curve'][-1] if r['curve'] else np.nan for r in rr]; n=[r['N'] for r in rr]
    ax.plot(h,dv,'-o',color='#1F4E79',lw=1.5,ms=4,label='raw slope, full scene')
    ax.set_ylabel('raw slope'); ax.set_title(f'{day} (UTC+08) · no gate',loc='left')
    ax.grid(True,color='#E5E7EB',lw=.55); ax.set_xlim(-.5,23.5); ax.set_xticks(range(0,24,2))
    ax2=ax.twinx(); ax2.bar(h,n,width=.55,color='#C9D6E4',alpha=.45,zorder=0); ax2.set_ylabel('N',color='#6B7280'); ax2.set_ylim(0,max(n)*1.2)
axes[-1].set_xlabel('Local hour (UTC+08)')
fig.tight_layout(); fig.savefig(SRC/'figures'/'24h-no-gate-09-08-09-11.png',dpi=300,bbox_inches='tight'); plt.close(fig)
print('saved figures',SRC/'figures')
