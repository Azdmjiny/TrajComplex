import json, numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(r'C:\Users\HP\Documents\ChatGPT\UVA World Model')
OUT=ROOT/'deliverables/changi-threshold-review-2026-10-26'
rows=json.load(open(OUT/'results/threshold-review.json'))
DATES=['2026-09-08','2026-09-11']
H=np.arange(24)
floor=min(r['one_hour']['n20_r90']['dimension'] for r in rows if r['one_hour']['n20_r90']['status']=='ok')
summary={}
for day in DATES:
    rr=sorted([r for r in rows if r['date']==day],key=lambda x:x['hour'])
    summary[day]={
        'three_hour_ok':sum(r['full']['status']=='ok' for r in rr),
        'one_hour_ok':sum(r['one_hour']['n20_r90']['status']=='ok' for r in rr),
        'three_hour_missing':[r['hour'] for r in rr if r['full']['status']!='ok'],
        'one_hour_missing':[r['hour'] for r in rr if r['one_hour']['n20_r90']['status']!='ok'],
        'assigned_floor_hours':[r['hour'] for r in rr if r['one_hour']['n20_r90']['status']!='ok' and r['one_hour']['N']<15],
    }
summary['floor']=float(floor)
json.dump(summary,open(OUT/'results/summary.json','w'),indent=2)

C3='#1F4E79'; C1='#B35C1E'; GREY='#666666'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.5,'axes.titlesize':9.5,'axes.labelsize':8.8,
                     'xtick.labelsize':7.8,'ytick.labelsize':7.8,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,2,figsize=(12.8,7.8),sharex='col',gridspec_kw={'width_ratios':[1.65,1],'hspace':.28,'wspace':.18})
for i,day in enumerate(DATES):
    rr=sorted([r for r in rows if r['date']==day],key=lambda x:x['hour'])
    ax=axes[i,0]
    d3=np.array([r['full']['dimension'] if r['full']['status']=='ok' else np.nan for r in rr],float)
    d1=np.array([r['one_hour']['n20_r90']['dimension'] if r['one_hour']['n20_r90']['status']=='ok' else np.nan for r in rr],float)
    ax.plot(H,d3,'-o',color=C3,lw=1.5,ms=4,label='3h rolling, N≥30, R²≥0.90',zorder=3)
    ax.plot(H,d1,'--s',color=C1,lw=1.2,ms=3.2,mfc='white',mew=.8,label='1h, N≥20, R²≥0.90',zorder=4)
    # Low-confidence 1h estimates (15-19 aircraft) and assigned floor.
    for r in rr:
        h=r['hour']; one=r['one_hour']
        if one['n20_r90']['status']!='ok' and 15<=one['N']<20 and one['n15_r90']['status']=='ok':
            ax.plot(h,one['n15_r90']['dimension'],'o',color=C1,mfc='white',mew=1.0,ms=5,zorder=5)
        if one['n20_r90']['status']!='ok' and one['N']<15:
            ax.plot(h,floor,'v',color=GREY,mfc='white',mew=.9,ms=5,zorder=5)
    for r in rr:
        if r['full']['status']!='ok':
            ax.axvspan(r['hour']-.48,r['hour']+.48,color='#D1D5DB',alpha=.35,lw=0)
    ax.set_ylabel('Correlation dimension $D$')
    ax.set_title(f'{day} (UTC+08)  ·  3h {summary[day]["three_hour_ok"]}/24, 1h {summary[day]["one_hour_ok"]}/24',loc='left')
    ax.set_xlim(-.5,23.5); ax.set_xticks(range(0,24,2))
    ax.grid(True,color='#E5E7EB',lw=.55,zorder=0)
    if i==0: ax.legend(loc='upper center',bbox_to_anchor=(.5,1.18),frameon=False,fontsize=7.2,ncol=2)

    axn=axes[i,1]
    n3=[r['N'] for r in rr]; n1=[r['one_hour']['N'] for r in rr]
    axn.bar(H-.19,n3,width=.38,color='#A9C4DD',label='3h union')
    axn.bar(H+.19,n1,width=.38,color='#E8C2A6',label='1h')
    axn.axhline(30,color=C3,ls=':',lw=.9)
    axn.axhline(20,color=C1,ls=':',lw=.9)
    axn.set_ylim(0,max(n3)*1.12); axn.set_ylabel('Aircraft')
    axn.set_xlim(-.5,23.5); axn.set_xticks(range(0,24,2)); axn.set_xticklabels([f'{h:02d}' for h in range(0,24,2)])
    axn.grid(True,axis='y',color='#E5E7EB',lw=.55)
    axn.set_title('Window population',loc='left')
    if i==0: axn.legend(loc='upper left',frameon=False,fontsize=7.0)
    axn.set_xlabel('Local hour (UTC+08)')

fig.tight_layout()
for ext in ['png','pdf','svg']:
    fig.savefig(OUT/f'changi-24h-threshold-comparison.{ext}',dpi=300,bbox_inches='tight')
print('floor',floor)
print(json.dumps(summary,indent=2))
