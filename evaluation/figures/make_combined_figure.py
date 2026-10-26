import json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

repo=Path(__file__).resolve().parents[2]
hr=repo/'evaluation/runs/holding-equal-duration/results'
vr=repo/'evaluation/runs/segmented-15km/results'
hs=json.load(open(hr/'summary.json'))
hrec=json.load(open(hr/'paired-dose-records.json'))
vs=json.load(open(vr/'segmented/summary.json'))
vexp=json.load(open(vr/'segmented/experiment-results.json'))['qc500_safe']['vectoring']['scenes']

C_H='#2563EB'; C_V='#D97706'; GREY='#9CA3AF'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.8,'axes.titlesize':9.5,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':8,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,2,figsize=(12.2,8.6),gridspec_kw={'height_ratios':[1.0,1.15]})
axL,axR=axes[0]; axBL,axBR=axes[1]
# column headers
fig.text(0.265,0.975,'HOLDING',ha='center',va='top',fontsize=13,fontweight='bold',color=C_H)
fig.text(0.755,0.975,'VECTORING',ha='center',va='top',fontsize=13,fontweight='bold',color=C_V)

# A: holding paired excess for all estimable scenes
rows=[s for s in hs['scene_details'] if s.get('paired_excess_median') is not None]
rows=sorted(rows,key=lambda s:s['local_UTC8'])
labels=[s['local_UTC8'].replace(' ','\n') for s in rows]
vals=[s['paired_excess_median'] for s in rows]
x=np.arange(len(rows))
cols=[C_H if v>=0 else '#B91C1C' for v in vals]
axL.bar(x,vals,color=cols,width=.68,alpha=.9)
axL.axhline(0,color='#374151',lw=1)
axL.axhline(np.median(vals),color=C_H,lw=1.4,ls='--')
axL.set_xticks(x); axL.set_xticklabels(labels,fontsize=7.6)
axL.set_ylabel('Median $D$(Holding) − $D$(Straight)')
axL.set_title(f'All estimable scenes ({len(rows)}/12): 7/8 positive, median +{np.median(vals):.3f}',loc='left',fontsize=8.8)
axL.text(.98,.95,'4 scenes have no accepted paired comparison',transform=axL.transAxes,fontsize=7.2,color='#4B5563',va='top',ha='right')
axL.grid(True,axis='y',color='#E5E7EB',lw=.7,zorder=0)
axL.text(-.11,1.06,'A',transform=axL.transAxes,fontweight='bold',fontsize=14,va='top')

# B: vectoring rho by scene, all 15 curves
scene_order=['2026-09-15T07Z','2026-09-19T07Z','2026-09-27T05Z']
scene_lab=['09-15','09-19','09-27']
rng=np.random.default_rng(11)
allrho=[]
for i,sid in enumerate(scene_order):
    rr=[c['retained']['rho'] for c in vs['curves'] if c['scene']==sid and c['retained']['rho'] is not None]
    allrho+=rr
    axR.scatter(i+rng.uniform(-.12,.12,len(rr)),rr,s=30,color=C_V,alpha=.85,edgecolor='white',linewidth=.5,zorder=3)
    axR.hlines(np.median(rr),i-.25,i+.25,color=C_V,lw=2.5,zorder=4)
    axR.text(i,1.02,f'{sum(v>0 for v in rr)}/{len(rr)}',ha='center',va='bottom',fontsize=8,color=C_V,fontweight='bold')
axR.axhline(0,color='#374151',lw=1,ls='--')
axR.set_xticks(range(3)); axR.set_xticklabels(scene_lab)
axR.set_xlim(-.5,2.5); axR.set_ylim(-1.05,1.12)
axR.set_ylabel('Spearman $\\rho$ (dose vs $D$)')
axR.set_title(f'All 15 curves: 13/15 positive, median {np.median(allrho):.3f}',loc='left',fontsize=8.8)
axR.grid(True,axis='y',color='#E5E7EB',lw=.7,zorder=0)
axR.text(-.11,1.06,'B',transform=axR.transAxes,fontweight='bold',fontsize=14,va='top')

# C: holding best scene 09-04, H vs S median curves with IQR
sid='2026-09-04T08Z'
for arm,color,lab in [('holding',C_H,'Holding'),('straight','#6B7280','Straight')]:
    by={}
    for r in hrec:
        if r['scene']==sid and r[arm+'_D'] is not None:
            by.setdefault(r['dose'],[]).append(r[arm+'_D'])
    ds=sorted(by); med=[np.median(by[d]) for d in ds]
    lo=[np.percentile(by[d],25) for d in ds]; hi=[np.percentile(by[d],75) for d in ds]
    axBL.plot(ds,med,color=color,lw=2.4,label=lab,zorder=3)
    axBL.fill_between(ds,lo,hi,color=color,alpha=.13,lw=0,zorder=1)
axBL.set_xlabel('Aircraft with +240 s appended')
axBL.set_ylabel('Correlation dimension $D$')
axBL.set_title('09-04 16:00 · representative holding scene\n$N$=40 · median $\\rho$ H=0.82, S=0.67',loc='left',fontsize=8.6)
axBL.grid(True,color='#E5E7EB',lw=.7,zorder=0)
axBL.legend(frameon=False,fontsize=8,loc='lower right')
axBL.text(-.11,1.06,'C',transform=axBL.transAxes,fontweight='bold',fontsize=14,va='top')

# D: vectoring best scene 09-15, 5 orders + median
sid='2026-09-15T07Z'
rows=[s for s in vexp if s['scene_id']==sid]
by={}
for s in rows:
    for p in s['dose_curve']:
        if p['status']=='ok' and p['dimension'] is not None:
            by.setdefault(p['vectoring_aircraft'],[]).append(p['dimension'])
    pts=[(p['vectoring_aircraft'],p['dimension']) for p in s['dose_curve'] if p['status']=='ok' and p['dimension'] is not None]
    axBR.plot([p[0] for p in pts],[p[1] for p in pts],color=GREY,lw=1,alpha=.5,zorder=1)
ds=sorted(by); med=[np.median(by[d]) for d in ds]
axBR.plot(ds,med,color=C_V,lw=2.6,marker='o',ms=5,zorder=3,label='Median of 5 orders')
axBR.set_xlabel('Aircraft with 15 km vectoring')
axBR.set_ylabel('Correlation dimension $D$')
axBR.set_title('09-15 15:00 · best vectoring contrast\n$N$=47 · median $\\rho$=0.96, 5/5 positive',loc='left',fontsize=8.6)
axBR.set_xticks(ds)
axBR.grid(True,color='#E5E7EB',lw=.7,zorder=0)
axBR.legend(frameon=False,fontsize=8,loc='lower right')
axBR.text(-.11,1.06,'D',transform=axBR.transAxes,fontweight='bold',fontsize=14,va='top')

fig.tight_layout(rect=(0,0.02,1,0.955),h_pad=1.6,w_pad=1.6)
fig.text(0.5,0.008,'Holding: 8 of 12 scenes have a jointly valid paired comparison; 4 have none. Vectoring: 3 of 4 scenes are estimable; 09-14 has only 4 doses. Thin/grey lines are individual orders; bands are IQR across orders.',ha='center',fontsize=7.4,color='#4B5563')
out=repo/'evaluation/figures'
for ext in ['png','pdf']:
    fig.savefig(out/f'holding-vs-vectoring-comparison.{ext}',dpi=300,bbox_inches='tight')
print('saved',out)


