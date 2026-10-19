import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt']='atm-evaluation'
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
ROOT=Path(__file__).resolve().parents[1]
S=json.loads((ROOT/'results/summary.json').read_text());DATA=json.loads((ROOT/'results/experiment-results.json').read_text())
OUT=ROOT/'figures';OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'axes.titlepad':12,'savefig.facecolor':'white'})
COLORS=['#0072B2','#D55E00','#009E73','#CC79A7','#7B61A8']
FILES=[]
def save(fig,name):
    fig.savefig(OUT/f'{name}.png',dpi=200)
    svg_path=OUT/f'{name}.svg'
    fig.savefig(svg_path,metadata={'Date':None})
    svg_path.write_text('\n'.join(line.rstrip() for line in svg_path.read_text(encoding='utf8').splitlines())+'\n',encoding='utf8')
    FILES.append(name);plt.close(fig)

def facets(variant,scenes,name,delta=False):
    fig,axes=plt.subplots(3,2,figsize=(16,13.8))
    fig.subplots_adjust(top=.845,bottom=.06,left=.07,right=.98,hspace=.58,wspace=.24)
    fig.suptitle(f'Holding dose response | {variant.upper()} | '+('baseline-relative D' if delta else 'estimated D'),fontsize=20,y=.985)
    fig.text(.5,.951,'Outcome-selected truncation: one shared mean-curve peak per hour; peak requires at least 3 valid orders.',ha='center',fontsize=11)
    handles=[Line2D([0],[0],color=c,marker='o',markersize=3,lw=1,label=f'Order {i+1}') for i,c in enumerate(COLORS)]
    handles += [Line2D([0],[0],color='#182638',lw=2.5,label='Available-order mean'),Line2D([0],[0],color='#B7BDC6',marker='o',markersize=3,lw=1,label='Excluded after peak'),Line2D([0],[0],color='#D79823',ls='--',lw=2,label='Selected cutoff')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.925),ncol=4,frameon=False,fontsize=10)
    for ax,scene in zip(axes.flat,scenes):
        sid=scene['scene_id'];trials=[t for t in DATA[variant]['holding']['scenes'] if t['scene_id']==sid]
        peak=scene['peak'];cut=scene['cutoff'];base=scene['baseline_D'] if delta else 0
        for i,t in enumerate(trials):
            yy=np.array([p['dimension'] if p['status']=='ok' and p['dimension'] is not None else np.nan for p in t['dose_curve']])-base
            xx=np.arange(len(yy));ret=(xx<=cut) if cut is not None else np.zeros(len(xx),bool)
            ax.plot(xx,yy,color='#B7BDC6',lw=.8,alpha=.6,marker='.',ms=3)
            ax.plot(xx,np.where(ret,yy,np.nan),color=COLORS[i],lw=1,alpha=.6,marker='.',ms=3)
        mean=np.array([v if v is not None else np.nan for v in peak['mean_D']])-base;x=np.arange(len(mean))
        ax.plot(x,mean,color='#182638',lw=2,alpha=.85,zorder=5)
        if cut is not None:
            ax.axvspan(cut,scene['n_aircraft'],color='#DDE2E8',alpha=.33)
            ax.axvline(cut,color='#D79823',ls='--',lw=1.8)
            ax.scatter([cut],[mean[cut]],marker='*',s=100,color='#D79823',edgecolor='#785000',zorder=6)
        if scene['baseline_ok']:ax.axhline(0 if delta else scene['baseline_D'],color='#496B86',ls=':',lw=1)
        fr=scene['full'];rr=scene['retained'];fmt=lambda v:f'{v:.2f}' if v is not None else 'NA'
        cutoff=f'{cut}/{scene["n_aircraft"]} ({scene["cutoff_fraction"]:.0%})' if cut is not None else 'no eligible peak'
        ax.set_title(f'{sid} | N={scene["n_aircraft"]} | cutoff: {cutoff}\nMedian rho: full {fmt(fr["median"])} -> kept {fmt(rr["median"])}; curves {fr["n"]} -> {rr["n"]}',fontsize=11)
        ax.set_xlabel('Aircraft with injected holding (count)');ax.set_ylabel('D - baseline D' if delta else 'Estimated D')
        ax.xaxis.set_major_locator(MaxNLocator(integer=True,nbins=7));ax.set_xlim(0,scene['n_aircraft'])
    for ax in list(axes.flat)[len(scenes):]:ax.set_visible(False)
    save(fig,name)

for variant in ['qc500','qc350']:
    scenes=S[variant]['holding']['scenes']
    for j in range(2):facets(variant,scenes[j*6:(j+1)*6],f'{variant}-holding-scenes-{j+1}')
facets('qc500',[s for s in S['qc500']['holding']['scenes'] if s['baseline_ok']],'holding-dose-response',True)

fig,axes=plt.subplots(1,2,figsize=(16,8.5));fig.subplots_adjust(left=.13,right=.98,top=.82,bottom=.1,wspace=.4)
fig.suptitle('Holding correlation: full range vs selected prefix',fontsize=20,y=.97)
fig.text(.5,.922,'Points are per-hour medians of random-order correlations. Counts at right show available curves (full / kept).',ha='center',fontsize=11)
fig.text(.5,.888,'Exploratory: the same observations select the peak and estimate the retained correlation.',ha='center',fontsize=11,color='#8A4F00')
for ax,variant in zip(axes,['qc500','qc350']):
    scenes=S[variant]['holding']['scenes']
    for i,s in enumerate(scenes):
        a=s['full']['median'];b=s['retained']['median']
        if a is not None and b is not None:ax.plot([a,b],[i,i],color='#CBD1D8',lw=2)
        if a is not None:ax.scatter(a,i,s=45,color='#63758A',marker='o',zorder=3)
        if b is not None:ax.scatter(b,i,s=50,color='#0072B2',marker='D',zorder=4)
        ax.text(1.09,i,f'{s["full"]["n"]} / {s["retained"]["n"]}',va='center',fontsize=10)
    ax.set_yticks(range(12),[s['scene_id'][5:] for s in scenes]);ax.invert_yaxis();ax.set_xlim(-1.08,1.48);ax.set_xticks([-1,-.5,0,.5,1]);ax.axvline(0,color='#A7ADB5',lw=1)
    ax.set_xlabel('Median Spearman rho within hour');ax.set_title(variant.upper(),fontsize=14)
fig.legend(handles=[Line2D([0],[0],marker='o',color='#63758A',lw=0,label='Full range'),Line2D([0],[0],marker='D',color='#0072B2',lw=0,label='Retained prefix')],loc='lower center',bbox_to_anchor=(.5,.015),ncol=2,frameon=False)
save(fig,'holding-correlation-comparison')

fig,ax=plt.subplots(figsize=(14,8.5));fig.subplots_adjust(left=.14,right=.98,top=.81,bottom=.18)
fig.suptitle('Vectoring: full-dose correlations retained unchanged',fontsize=20,y=.97)
fig.text(.5,.925,'No peak truncation. Each point is a within-hour median; absent points have no eligible correlation.',ha='center',fontsize=11)
variants=['qc500','qc350','qc500_safe','qc350_safe'];markers=['o','s','D','^'];colors=['#0072B2','#D55E00','#009E73','#CC79A7']
for j,(v,m,c) in enumerate(zip(variants,markers,colors)):
    scenes=S[v]['vectoring']['scenes']
    for i,s in enumerate(scenes):
        val=s['full']['median']
        if val is not None:ax.scatter(val,i+(j-1.5)*.13,s=50,c=c,marker=m)
ax.set_yticks(range(12),[s['scene_id'][5:] for s in scenes]);ax.invert_yaxis();ax.set_xlim(-1.05,1.05);ax.set_xlabel('Median Spearman rho within hour');ax.axvline(0,color='#A7ADB5',lw=1)
fig.legend(handles=[Line2D([0],[0],color=c,marker=m,lw=0,label=v.upper().replace('_SAFE',' + maneuver speed screen')) for v,m,c in zip(variants,markers,colors)],loc='lower center',bbox_to_anchor=(.5,.045),ncol=2,frameon=False)
save(fig,'vectoring-full-range')

fig,axes=plt.subplots(1,2,figsize=(14,6.5));fig.subplots_adjust(top=.77,bottom=.20,left=.08,right=.97,wspace=.27)
fig.suptitle('Aircraft-count sensitivity: unchanged full-point-cloud analysis',fontsize=18,y=.97)
fig.text(.5,.915,'Only hours with an estimable full-scene baseline enter these summaries; 50 random subsamples per setting.',ha='center',fontsize=10)
fig.text(.5,.878,'Contributing hours at N=30/40/50: legacy 6/6/6; QC500 6/6/6; QC350 7/7/5.',ha='center',fontsize=10)
for j,(v,c) in enumerate(zip(['legacy_replay','qc500','qc350'],colors)):
    rr=S['aircraft_count'][v];xx=np.array([30,40,50])+(j-1)*1.3
    for ax,key,label in [(axes[0],'valid_rate','Median estimability across hours'),(axes[1],'median_abs_delta','Median absolute D error vs full cloud')]:
        vals=[];nn=[]
        for n in [30,40,50]:
            a=[r[key] for r in rr if r['n']==n and r['full_D'] is not None and r[key] is not None];vals.append(float(np.median(a)));nn.append(len(a))
        ax.plot(xx,vals,marker='o',color=c,label=v.upper(),lw=2)
        ax.set_xticks([30,40,50]);ax.set_xlabel('Aircraft per subsample');ax.set_ylabel(label);ax.margins(y=.24)
axes[0].set_ylim(0,1.15)
fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.035),ncol=3,frameon=False)
save(fig,'aircraft-count-sensitivity')
# Replace the original estimability figure names with corrected full-dose data.
for kind,variant in [('holding','qc500'),('vectoring','qc500_safe')]:
    fig,ax=plt.subplots(figsize=(12,5.8));fig.subplots_adjust(top=.78,bottom=.18,left=.09,right=.97)
    fig.suptitle(f'{kind.title()} estimability | {variant.upper()} | full dose range',fontsize=18,y=.97)
    fig.text(.5,.90,'Invalid D counts as a failed estimate, never as zero. Final bin includes 100% dose.',ha='center',fontsize=10)
    points=[]
    for t in DATA[variant][kind]['scenes']:
        denom=t['n_aircraft'] if kind=='holding' else t['n_vectoring_eligible']
        for p in t['dose_curve']:
            points.append((p[kind+'_aircraft']/denom,p['status']=='ok' and p['dimension'] is not None))
    rates=[];ns=[]
    for j in range(10):
        pp=[good for frac,good in points if int(min(9,np.floor(frac*10)))==j]
        rates.append(np.mean(pp));ns.append(len(pp))
    ax.plot(np.arange(10)*.1+.05,rates,'o-',color='#0072B2',lw=2)
    ax.set_xticks(np.arange(10)*.1+.05,[f'{j*10}-{(j+1)*10}%'+chr(10)+f'n={ns[j]}' for j in range(10)],fontsize=9)
    ax.set_ylim(0,1.05);ax.set_ylabel('Fraction of estimates passing quality gates');ax.set_xlabel('Dose fraction bins; n = total estimate points')
    save(fig,f'{kind}-d-estimability')

fig,ax=plt.subplots(figsize=(12,6.5));fig.subplots_adjust(top=.78,bottom=.16,left=.1,right=.97)
fig.suptitle('Vectoring dose response | QC500 + maneuver speed screen',fontsize=18,y=.97)
fig.text(.5,.90,'Baseline-estimable hours; within-hour average of valid orders, then equal-weight average across hours.',ha='center',fontsize=10)
curves=[];fractions=np.array([0,.25,.5,.75,1.])
for scene in S['qc500_safe']['vectoring']['scenes']:
    if not scene['baseline_ok']:continue
    ts=[t for t in DATA['qc500_safe']['vectoring']['scenes'] if t['scene_id']==scene['scene_id']]
    values=[]
    for f in fractions:
        pp=[t['dose_curve'][round(f*t['n_vectoring_eligible'])] for t in ts]
        vs=[p['dimension'] for p in pp if p['status']=='ok' and p['dimension'] is not None]
        values.append(np.mean(vs)-scene['baseline_D'] if vs else np.nan)
    curves.append(values);ax.plot(fractions,values,marker='.',lw=1.2,alpha=.7,label=scene['scene_id'][5:])
mean=np.nanmean(curves,axis=0)
ax.plot(fractions,mean,color='#152433',lw=3,marker='o',label='Mean across hours')
ax.set_xticks(fractions,[f'{x:.0%}' for x in fractions]);ax.axhline(0,color='#667788',lw=1,ls=':');ax.set_xlabel('Injected aircraft / speed-screened eligible aircraft');ax.set_ylabel('D - baseline D')
ax.legend(loc='upper left',ncol=2,fontsize=9,frameon=True)
save(fig,'vectoring-dose-response')

(OUT/'index.json').write_text(json.dumps(dict(figures=FILES,matplotlib=matplotlib.__version__,formats=['PNG at 200 dpi','SVG']),indent=2))
print('Saved',len(FILES),'figures in PNG and SVG')
