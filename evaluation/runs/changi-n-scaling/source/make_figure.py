import json, numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(r'deliverables/changi-n-scaling-2026-10-26')
d=json.load(open(OUT/'d_vs_n.json')); rows=d['rows']
n=np.array([r['n'] for r in rows]); med=np.array([r['median'] if r['median'] is not None else np.nan for r in rows])
p10=np.array([r['p10'] if r['p10'] is not None else np.nan for r in rows])
p90=np.array([r['p90'] if r['p90'] is not None else np.nan for r in rows])
std=np.array([r['median_std'] if r['median_std'] is not None else np.nan for r in rows])
valid=np.array([r['valid'] for r in rows]); N=d['N']
C='#1F4E79'; C2='#B35C1E'; G='#6B7280'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.5,'axes.titlesize':9.5,'axes.labelsize':8.8,
                     'xtick.labelsize':7.8,'ytick.labelsize':7.8,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,1,figsize=(8.4,6.4),sharex=True,gridspec_kw={'height_ratios':[3,1.15],'hspace':.08})
ax=axes[0]
ax.axvspan(4.5,19.5,color='#F3F4F6',alpha=.7,lw=0,zorder=0)
ax.fill_between(n,p10,p90,color=C,alpha=.14,lw=0,label='10–90% of orders')
med_line=med.copy(); med_line[n<15]=np.nan
ax.plot(n,med_line,'-o',color=C,lw=1.5,ms=3.2,label='median, low-N exploratory gate')
ax.scatter(n,med,s=9,color=C,zorder=4)
std_plot=std.copy(); std_plot[n<20]=np.nan
ax.plot(n,std_plot,'--',color=C2,lw=1.2,label='median, standard gate (N≥20)')
ax.axvline(20,color=G,ls=':',lw=.9); ax.axvline(30,color=G,ls=':',lw=.9)
ax.text(20,ax.get_ylim()[1]*.97,'N=20',ha='center',va='top',fontsize=7,color=G)
ax.text(30,ax.get_ylim()[1]*.97,'N=30',ha='center',va='top',fontsize=7,color=G)
ax.set_ylabel('Correlation dimension $D$')
ax.set_title(f'{d["scene"]} · N={N} · {d["orders"]} nested random orders',loc='left')
ax.grid(True,color='#E5E7EB',lw=.55)
ax.legend(loc='lower right',frameon=False,fontsize=7.2)
ax.text(5,1.98,'N<20: no fit or low valid rate',fontsize=7.2,color=G,va='top')
ax.scatter(n[n<15],med[n<15],s=22,facecolors='white',edgecolors=C,linewidths=.9,zorder=5)
ax2=axes[1]
ax2.bar(n,valid/d['orders'],color=C,alpha=.75,width=.82)
ax2.axvline(20,color=G,ls=':',lw=.9); ax2.axvline(30,color=G,ls=':',lw=.9)
ax2.set_ylim(0,1.05); ax2.set_ylabel('valid fraction')
ax2.set_xlabel('Number of aircraft in the scene')
ax2.set_xlim(4.5,N+.5); ax2.set_xticks(range(5,N+1,5))
ax2.grid(True,axis='y',color='#E5E7EB',lw=.55)
fig.tight_layout()
for ext in ['png','pdf']:
    fig.savefig(OUT/f'd-vs-n-{d["scene"]}.{ext}',dpi=300,bbox_inches='tight')
print('saved',OUT)
