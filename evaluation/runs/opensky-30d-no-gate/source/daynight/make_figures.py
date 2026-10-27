import json, numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SRC=Path(r'deliverables/opensky-30d-daynight-2026-10-26')
d=json.load(open(SRC/'results/daynight-model.json'))
a=d['exact_full']; main=d['main']; beta=main['beta']; floor=d['floor']; N0=d['N_threshold']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.5,'axes.titlesize':9.5,'axes.labelsize':8.8,
                     'xtick.labelsize':7.8,'ytick.labelsize':7.8,'axes.spines.top':False,'axes.spines.right':False})
C_D='#2563EB'; C_N='#B35C1E'
# A: bands
fig,axes=plt.subplots(2,1,figsize=(8.8,6.2),sharex=True,gridspec_kw={'height_ratios':[3,1],'hspace':.08})
ax=axes[0]
for label,color in [('day',C_D),('night',C_N)]:
    ns=[int(k) for k in a if label in a[k]]
    ns.sort()
    med=[a[str(n)][label]['median'] for n in ns]
    p10=[a[str(n)][label]['p10'] for n in ns]; p90=[a[str(n)][label]['p90'] for n in ns]
    ax.plot(ns,med,'-o',color=color,lw=1.8,ms=3.4,label=label)
    ax.fill_between(ns,p10,p90,color=color,alpha=.13,lw=0)
ax.axvspan(4.5,N0-.5,color='#F3F4F6',alpha=.8,zorder=0)
ax.axvline(N0,color='#6B7280',ls=':',lw=.9)
ax.text(5,1.73,f'N<{N0}: low-reliability',fontsize=7.2,color='#4B5563',va='top')
ax.set_ylabel('raw log–log slope'); ax.set_title('A · day/night, no truncation; median and 10–90%',loc='left')
ax.grid(True,color='#E5E7EB',lw=.55); ax.legend(loc='lower right',frameon=False)
ax2=axes[1]
for label,color in [('day',C_D),('night',C_N)]:
    ns=[int(k) for k in a if label in a[k]]; ns.sort()
    ax2.bar(np.array(ns)+(0.2 if label=='night' else -0.2),[a[str(n)][label]['n'] for n in ns],width=.4,color=color,alpha=.7,label=label)
ax2.set_ylabel('hours'); ax2.set_xlabel('Number of aircraft in the scene'); ax2.grid(True,axis='y',color='#E5E7EB',lw=.55)
ax2.set_xlim(4.5,54.5); ax2.set_xticks(range(5,55,5)); ax2.legend(loc='upper right',frameon=False,fontsize=7.2)
fig.tight_layout(); fig.savefig(SRC/'figures/A-daynight-bands.png',dpi=300,bbox_inches='tight'); plt.close(fig)

# C: model predictions vs observed medians
fig,ax=plt.subplots(figsize=(8.8,5.6))
ng=np.arange(5,55)
for label,color in [('day',C_D),('night',C_N)]:
    flag=0 if label=='day' else 1
    pred=beta[0]+beta[1]*ng+beta[2]*flag+beta[3]*ng*flag
    ax.plot(ng,pred,color=color,lw=2.3,label=f'{label} model')
    # observed medians thin
    ns=[int(k) for k in a if label in a[k]]; ns.sort()
    ax.plot(ns,[a[str(n)][label]['median'] for n in ns],color=color,lw=.8,alpha=.5,ls=':')
ax.axvspan(4.5,N0-.5,color='#F3F4F6',alpha=.8,zorder=0)
ax.axvline(N0,color='#6B7280',ls=':',lw=.9)
ax.set_xlabel('Number of aircraft in the scene'); ax.set_ylabel('raw log–log slope')
ax.set_title(f'C · Tobit-like model; floor={floor}, N<{N0} censored',loc='left')
ax.grid(True,color='#E5E7EB',lw=.55)
ax.legend(loc='lower right',frameon=False)
ax.text(5,1.72,f'night effect at N=30 = {beta[2]+30*beta[3]:+.2f}\n(bootstrap 95% CI in report)',fontsize=7.2,color='#4B5563',va='top')
fig.tight_layout(); fig.savefig(SRC/'figures/C-tobit-predictions.png',dpi=300,bbox_inches='tight'); plt.close(fig)
print('saved',SRC/'figures')
