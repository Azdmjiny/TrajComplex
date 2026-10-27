import json,numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
SRC=Path(r'deliverables/opensky-30d-daynight-2026-10-26')
d=json.load(open(SRC/'results/daynight-model.json')); a=d['exact_full']
bins=[(5,9),(10,14),(15,19),(20,24),(25,29),(30,34),(35,39),(40,44),(45,49)]
data_day=[];data_night=[];labels=[]
for lo,hi in bins:
 dd=[];nn=[]
 for n in range(lo,hi+1):
  z=a.get(str(n),{})
  if 'day' in z: dd.append(z['day']['median'])
  if 'night' in z: nn.append(z['night']['median'])
 data_day.append(dd);data_night.append(nn);labels.append(f'{lo}–{hi}')
# Need hourly distributions, not medians: use raw rows to make box data
raw=json.load(open(r'deliverables/opensky-30d-no-gate-2026-10-26/results/d-vs-n-no-gate.json'))['rows']
by={r['key']:r for r in raw}
data_day=[];data_night=[];counts_day=[];counts_night=[]
for lo,hi in bins:
 dd=[];nn=[]
 for r in raw:
  if not r['curve']: continue
  flag=0 if 7<=r['local_hour']<19 else 1
  vals=[r['curve'][n-5] for n in range(lo,hi+1) if n<=r['N'] and r['curve'][n-5] is not None]
  if vals:
   (dd if flag==0 else nn).append(float(np.median(vals)))
 data_day.append(dd);data_night.append(nn);counts_day.append(len(dd));counts_night.append(len(nn))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.5,'axes.titlesize':9.5,'axes.labelsize':8.8,'xtick.labelsize':7.8,'ytick.labelsize':7.8,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,1,figsize=(9.4,6.3),sharex=True,gridspec_kw={'height_ratios':[3,1],'hspace':.08})
ax=axes[0]; x=np.arange(len(bins)); w=.32
for vals,off,color,label in [(data_day,-w/2,'#2563EB','day'),(data_night,w/2,'#B35C1E','night')]:
 bp=ax.boxplot(vals,positions=x+off,widths=w*.9,patch_artist=True,showfliers=False,
               medianprops=dict(color='black',lw=1.2),whiskerprops=dict(color='#4B5563'),capprops=dict(color='#4B5563'),boxprops=dict(edgecolor='#4B5563'))
 for p in bp['boxes']: p.set_facecolor(color); p.set_alpha(.75)
ax.set_ylabel('raw log–log slope'); ax.set_title('A · day/night boxplots by aircraft-count bin; no truncation',loc='left')
ax.grid(True,axis='y',color='#E5E7EB',lw=.55); ax.set_xticks(x); ax.set_xticklabels([])
handles=[plt.Rectangle((0,0),1,1,color='#2563EB',alpha=.75),plt.Rectangle((0,0),1,1,color='#B35C1E',alpha=.75)]
ax.legend(handles,['day','night'],loc='lower right',frameon=False)
ax2=axes[1]; ax2.bar(x-w/2,counts_day,width=w,color='#2563EB',alpha=.7); ax2.bar(x+w/2,counts_night,width=w,color='#B35C1E',alpha=.7)
ax2.set_xticks(x); ax2.set_xticklabels(labels); ax2.set_ylabel('hours'); ax2.set_xlabel('aircraft count bin'); ax2.grid(True,axis='y',color='#E5E7EB',lw=.55)
fig.tight_layout(); fig.savefig(SRC/'figures/A-daynight-boxplot.png',dpi=300,bbox_inches='tight'); plt.close(fig)
print('saved')
