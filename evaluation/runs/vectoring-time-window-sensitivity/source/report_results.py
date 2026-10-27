"""Report all three status windows and both shapes without selecting outcomes."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timedelta
import json,sys,hashlib
R=Path(__file__).resolve().parent;B=R.parent
sys.path.insert(0,str(B/'evaluation-python-deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
write=lambda p,x:Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf8')
ACTIVE=B/'changi-publication-repo/evaluation/runs/segmented-15km'
results=read(R/'evaluation-summary.json');screen=read(R/'screening/summary.json');qs=read(R/'quality-summary.json')
summary=results['comparisons'];scenes=sorted({x['scene'] for x in screen['comparison']})
local=lambda s:(datetime.strptime(s,'%Y-%m-%dT%HZ')+timedelta(hours=8)).strftime('Sep %d, %H:00')
fmt=lambda x:'NA' if x is None else f'{x:.3f}'
trials={};arrays={}
for window in [10,15,20]:
    for shape in ['segmented','smooth']:
        if window==10:
            raw=read(ACTIVE/'results'/('segmented' if shape=='segmented' else 'smooth-control')/'experiment-results.json')
            tt=raw['qc500_safe']['vectoring']['scenes']
        else:tt=read(R/f'window-{window}s'/shape/'results/experiment-results.json')['scenes']
        trials[window,shape]=tt
        for sid in scenes:
            rows=sorted([t for t in tt if t['scene_id']==sid],key=lambda x:x['replicate'])
            x=np.asarray([d['vectoring_aircraft'] for d in rows[0]['dose_curve']])
            ys=np.asarray([[d['dimension'] if d['status']=='ok' else np.nan for d in row['dose_curve']] for row in rows])
            assert ys.shape[0]==5 and np.isfinite(ys[:,0]).all()
            delta=ys-ys[:,0,None]
            arrays[window,shape,sid]=(x,delta,rows[0]['n_aircraft'],ys[0,0])
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
    'axes.edgecolor':'#9faab3','pdf.fonttype':42,'svg.fonttype':'none'})
navy='#203f53';colors=['#1683b5','#d58b29','#239b80','#c579a5','#8675b5']
handles=[Line2D([],[],ls='',marker='o',color=c,ms=4,label=f'Order {i+1}') for i,c in enumerate(colors)]
handles.append(Line2D([],[],color=navy,lw=2.3,label='Mean of five orders'))
def save(fig,name):
    for ext in ['png','pdf','svg']:fig.savefig(R/f'{name}.{ext}',dpi=260,facecolor='white')
    plt.close(fig)
for shape in ['segmented','smooth']:
    fig,axes=plt.subplots(3,4,figsize=(18.5,14))
    fig.subplots_adjust(left=.055,right=.985,top=.85,bottom=.09,hspace=.53,wspace=.32)
    title='Segmented Vectoring' if shape=='segmented' else 'Smooth Vectoring'
    fig.suptitle(title+': quality-message time-window comparison',x=.055,y=.978,ha='left',fontsize=23,fontweight='bold',color=navy)
    fig.text(.055,.94,'15 km peak · 10 s trajectory sampling · R² ≥ 0.94 · complete dose ranges · local time (UTC+08)',fontsize=12,color=navy)
    fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.05,.92),ncol=6,frameon=False,fontsize=11)
    for col,sid in enumerate(scenes):
        allvalues=np.concatenate([arrays[w,shape,sid][1].ravel() for w in [10,15,20]])
        lo,hi=min(0,np.nanmin(allvalues)),max(0,np.nanmax(allvalues));span=max(hi-lo,.005)
        maxdose=max(arrays[w,shape,sid][0].max() for w in [10,15,20])
        for row,window in enumerate([10,15,20]):
            ax=axes[row,col];x,y,N,base=arrays[window,shape,sid]
            med=next(s['median'] for s in summary[f'{window}s-{shape}']['scenes'] if s['scene']==sid)
            for k,c in enumerate(colors):ax.scatter(x,y[k],s=20,color=c,alpha=.8,lw=0,zorder=3)
            ax.plot(x,y.mean(axis=0),color=navy,lw=2.2)
            ax.axhline(0,color='#83949f',ls='--',lw=.8)
            ax.set_title(f'{window} s match | {local(sid)}\nN = {N}, K = {x.max()} | median order ρ = {fmt(med)}',loc='left',fontsize=11.5,pad=12,color=navy)
            ax.set(xlabel='Aircraft with added Vectoring',ylabel='D − baseline D',ylim=(lo-.12*span,hi+.12*span),xlim=(-.2,maxdose+.2))
            ax.xaxis.set_major_locator(MaxNLocator(nbins=6,integer=True));ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
            ax.grid(axis='y',alpha=.22,lw=.6)
    fig.text(.055,.022,'One shared ΔD scale per scene column; different columns use labelled scales. K: injectable aircraft. The 10 s September 14 correlation is NA (four doses).',fontsize=10.5,color=navy)
    save(fig,'vectoring-'+shape+'-time-window-delta')
fig,axes=plt.subplots(1,2,figsize=(15,6.5),sharey=True)
fig.subplots_adjust(left=.065,right=.985,top=.74,bottom=.17,wspace=.17)
fig.suptitle('Vectoring: all order correlations',x=.065,y=.97,ha='left',fontsize=24,fontweight='bold',color=navy)
window_colors={10:'#567b98',15:'#db9c33',20:'#239b80'}
fig.legend(handles=[Line2D([],[],ls='',marker='o',color=c,ms=6,label=f'{w} s match') for w,c in window_colors.items()],loc='upper left',bbox_to_anchor=(.06,.89),ncol=3,frameon=False)
for ax,shape in zip(axes,['segmented','smooth']):
    for i,sid in enumerate(scenes):
        for j,w in enumerate([10,15,20]):
            v=[c['rho'] for c in summary[f'{w}s-{shape}']['curves'] if c['scene']==sid]
            center=i+(j-1)*.24
            if all(x is None for x in v):
                ax.text(center,-1.12,'NA',ha='center',va='center',fontsize=9,color=window_colors[w]);continue
            ax.scatter([center+(k-2)*.025 for k in range(5)],v,s=26,color=window_colors[w],alpha=.8)
            ax.hlines(np.median(v),center-.09,center+.09,color=navy,lw=2)
    ax.axhline(0,color='#83949f',ls='--',lw=.8)
    ax.set(ylim=(-1.2,1.12),xlim=(-.5,3.5),xticks=range(4),xticklabels=['Sep 14','Sep 15','Sep 19','Sep 27'],ylabel='Spearman ρ',xlabel='Scene date (local UTC+08)')
    ax.set_title('Segmented 15 km (schematic)' if shape=='segmented' else 'Smooth 15 km (screened)',fontsize=14,loc='left',color=navy)
    ax.grid(axis='y',alpha=.22)
fig.text(.065,.06,'Points: five dependent injection orders per scene and time window. Dark bars: scene medians. All negative and zero coefficients retained.',fontsize=11,color=navy)
save(fig,'vectoring-time-window-correlations')

stage_rows=[];rho_rows=[];scene_rows=[];baseline_rows=[]
for sid in scenes:
    old=arrays[10,'segmented',sid][0].max()
    a=next(t for t in screen['comparison'] if t['window_s']==15 and t['scene']==sid)
    b=next(t for t in screen['comparison'] if t['window_s']==20 and t['scene']==sid)
    stage_rows.append(f'| {local(sid)} | {a["background"]} | {old} | {a["new_quality"]} | {a["injectable_after"]} | {b["new_quality"]} | {b["injectable_after"]} |')
    scene_rows.append('| '+local(sid)+' | '+' | '.join(fmt(next(x['median'] for x in summary[f'{w}s-{shape}']['scenes'] if x['scene']==sid)) for shape in ['segmented','smooth'] for w in [10,15,20])+' |')
    base=[arrays[w,'segmented',sid][3] for w in [10,15,20]]
    baseline_rows.append(f'| {local(sid)} | {base[0]:.6f} | {base[1]:.6f} | {base[2]:.6f} |')
common_stats={}
for shape in ['segmented','smooth']:
    for w in [10,15,20]:
        s=summary[f'{w}s-{shape}']['all'];zero=s['estimable']-s['positive']-s['negative']
        rho_rows.append(f'| {shape} | {w} s | {s["valid_D"]}/{s["attempted_D"]} | {s["positive"]}/{s["estimable"]} | {s["negative"]} | {zero} | {fmt(s["median"])} |')
        common=[c['rho'] for c in summary[f'{w}s-{shape}']['curves'] if c['scene']!=scenes[0] and c['rho'] is not None]
        common_stats[f'{w}s-{shape}']=dict(median=float(np.median(common)),positive=sum(v>0 for v in common),n=len(common))
stage_reason_counts=Counter()
for r in screen['new_candidates']:
    if not r['reference_pass']:reason='reference geometry/direction'
    elif not r['injectable']:reason='5 km route solve/check'
    elif not r['smooth15_pass']:reason='15 km route verification'
    elif not r['segmented15_pass']:reason='segmented construction'
    else:reason='accepted both shapes'
    stage_reason_counts[reason]+=1
candidate_rows=[]
for r in screen['new_candidates']:
    reasons=r['rejection_reasons']+r['stage15_reasons']+r['segmented_reasons']
    candidate_rows.append(f'| {r["scene"]} | {r["icao24"]} | {r["quality_windows"]["15"]["full_quality_pass"]} | {r["fit_success"]} | {r["reference_pass"]} | {r["injectable"]} | {r["paired_injectable"]} | {"; ".join(reasons) or "Accepted"} |')
report='''# Vectoring: 10-, 15- and 20-second quality-message matching

2026-10-27. Independent, user-authorized sensitivity versions. The original 10-second result, current publication figures and Holding results remain unchanged. All three windows and both route shapes are reported; no window or scene is selected by its correlation. No Git push.

## What changed

Only the maximum distance from a real position timestamp to each of its two agreeing positive NACp status messages changes: 10, 15 or 20 seconds. **This is not the trajectory sampling interval**: the Encoder input remains strict 10 seconds. Exact position/NIC matching, source-age/gap limits, direction/geometry/motion conditions, 600-second intervention, frozen Encoder and R² ≥ 0.94 D gates remain unchanged. The active stimulus is 15 km; the inherited 5 km route pre-screen is also retained.

The 15/20-second choices are engineering sensitivity values authorized before these D results, not standards-certified quality validity intervals. The 21 union candidates were frozen from cached status evidence before any new D. Four bounded queries returned exactly 1,891 matching airborne position messages for 1,891 listed original source points. All have unambiguous positive NIC/HCR evidence. No missing values or intermediate timestamps were filled.

## How many candidates were actually recovered?

| Local start (UTC+08) | Background N | Original 10 s injectable | Additional 15 s quality-complete | Final 15 s injectable | Additional 20 s quality-complete | Final 20 s injectable |
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(stage_rows)+'''
| **Total** | **157** | **19** | **10** | **22** | **21** | **25** |

Time matching was a real candidate bottleneck, but not the only one. All 21 newly quality-supported tracks fit successfully; 9 fail reference geometry/direction, 1 fails the inherited 5 km route solve/check, and 5 fail the subsequent 15 km verification. Only 6 pass both route shapes at 20 seconds; 3 of those are also eligible at 15 seconds. The remaining 69 of the originally flagged 90 records still do not satisfy the 20-second status rule, or have other status-evidence problems.

The nine reference failures consist of eight nonpositive chord-progress cases and one unreliable continuous direction case. Among the five 15 km failures, four encounter acceleration violations and three encounter unresolved projection precision, with two tracks having both reasons on different sides. These reason counts overlap; they are not seven separate rejected candidates. The reference/generator family and numerical caps were not changed to accept them.

## Complete-range correlation results

| Shape | Status window | Accepted D / attempted | Positive order coefficients | Negative | Zero | Median order ρ |
|---|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(rho_rows)+'''

All D fits pass in all six comparisons. Lowering R² cannot recover any further point in these runs. The original September 14 scene had four doses including baseline, below the existing five-valid-dose requirement for correlation; the expanded 15/20-second versions now have enough doses. Thus 10-second totals cover 15 computable curves in three scenes, while 15/20-second totals cover 20 curves in four scenes. These aggregate populations differ.

| Local scene | Segmented 10 s | Segmented 15 s | Segmented 20 s | Smooth 10 s | Smooth 15 s | Smooth 20 s |
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(scene_rows)+'''

![Segmented full-range response](vectoring-segmented-time-window-delta.png)

[Segmented vector PDF](vectoring-segmented-time-window-delta.pdf)

![Smooth full-range response](vectoring-smooth-time-window-delta.png)

[Smooth vector PDF](vectoring-smooth-time-window-delta.pdf)

![All order correlations](vectoring-time-window-correlations.png)

[Correlation vector PDF](vectoring-time-window-correlations.pdf)

**Figure caption.** Full dose-range change in D relative to each version's unmodified baseline. Rows use status matching distances of 10, 15 and 20 seconds per side; columns are the four fixed scenes. Colored points denote five injection orders, with the dark line their arithmetic mean; no smoothing or cutoff selection is applied. Each scene column shares its ΔD and dose axes across rows; different scene columns have individually labelled vertical scales. Panel rho is the median of per-order Spearman coefficients, not the correlation of the mean. The correlation summary retains negative, zero and unavailable coefficients. The repeats share aircraft and are dependent; they are not independent scenes or confidence intervals.

## What the comparison means

- Enlarging the status window genuinely increases the injectable population, from 19 to 22 or 25, and makes all four scenes correlation-estimable. It does not recover all 21 extra quality-complete candidates.
- The segmented 20-second median is 0.887, but 5/20 coefficients are negative and one is zero. Its positive fraction is 70%, compared with 86.7% among the original computable curves; the latter excludes the previously non-estimable September 14 scene. A higher median is not uniform improvement.
- September 15 remains strongly positive under every version and both shapes. September 19 remains problematic: adding one candidate at 20 seconds reduces its segmented scene median from 0.714 to 0.071, and the smooth median is -0.571. That directly contradicts a claim that more candidates necessarily produce stronger positive association.
- September 27's segmented median improves to 0.881 at 20 seconds, while two orders remain negative. The response still depends on the aircraft/side sequence. Smooth responses remain mixed, with aggregate medians around 0.6.
- Candidate scarcity contributes limited dose resolution, but the observed instability also reflects the intervention, left/right assignments and scene representation. No saved-result analysis here identifies a single causal mechanism or proves that the D estimator is intrinsically invalid.
- Segmented routes remain the existing schematic stimulus and do not inherit the smooth C2/acceleration/bank certificate. The new candidates must pass the smooth route checks to enter the shared cohort, but the segmented trajectories themselves are not motion-certified. This was not changed or newly bypassed by the time-window sensitivity.

## Baseline pairing, scales and order preservation

All variants retain the same 157 basic-QC background identities. In accordance with the existing population rule, each newly quality-qualified successful whole-track fit becomes that variant's baseline before route acceptance, even if the route later fails. Injected and baseline trajectories therefore receive the same processing. This can change baseline embeddings and D between time-window variants; this comparison is a screening-policy sensitivity, not a pure increase-N intervention with every baseline point fixed.

| Local scene | Baseline D, 10 s | Baseline D, 15 s | Baseline D, 20 s |
|---|---:|---:|---:|
'''+ '\n'.join(baseline_rows)+'''

The original baseline-derived 64-radius rule is retained. The grid is fixed within a scene/version and shared by both shapes, but can differ between status-window versions when the baseline changes. Adaptive fitting subsets and all original gates remain unchanged. ΔD is computed relative to each version's own baseline. Identical D values do not imply identical fitted trajectories: finite pair-count steps can yield the same dimension despite small coordinate changes.

Old candidates keep their original relative order and side assignments. Before route checks or D, a deterministic random interleaving extended each original sequence to the full 21-candidate union. Both variants and both shapes filter this same master sequence to accepted candidates; there is no outcome-driven reordering or side choice. Only the new trajectories require encoding; unchanged arrays reuse the frozen embeddings. Four baseline inference checks reproduce the archived embeddings exactly, and the four original baseline D values are reproduced.

## Candidate audit

Every listed track passes the 20-second full quality gate. The 15-second column indicates whether it also meets the stricter sensitivity window.

| Source UTC hour | Aircraft | Quality at 15 s | Fit | Reference | 5 km screen | Both 15 km shapes | Rejection detail |
|---|---|---|---|---|---|---|---|
'''+ '\n'.join(candidate_rows)+'''

## Artifacts and reproducibility

This directory contains the frozen `policy.json`, `tasks.json`, `assignments.json`, bounded exact-match query results, point-level quality evidence, per-candidate continuous route diagnostics, per-version populations, embeddings, every D fit/failed status, and comparison figures. `prepare.py`, `match_quality.py`, `screen_routes.py`, `run_evaluation.py` and `report_results.py` implement the stages. Cached status timestamps are reused; original source observations are never changed. Authentication tokens were kept in the query client's memory only and the process was closed after the four requests.

Original result hashes are preserved in the screening and evaluation manifests. These new independent versions and their derived data remain local. No main paper result is automatically replaced by whichever version has the largest coefficient.
'''
report+='\nFor the same three originally correlation-estimable scenes (excluding September 14), the descriptive aggregates are:\n\n| Shape | Window | Positive / computable | Median rho |\n|---|---|---:|---:|\n'
for shape in ['segmented','smooth']:
    for w in [10,15,20]:
        s=common_stats[f'{w}s-{shape}'];report+=f'| {shape} | {w} s | {s["positive"]}/{s["n"]} | {s["median"]:.3f} |\n'
report+='\nThis keeps the scene set fixed, but expanded candidate sets and paired baselines still differ. It is not a controlled causal attribution to candidate number alone.\n'
(R/'report.md').write_text(report,encoding='utf8')
write(R/'report-summary.json',dict(stage_reason_counts=dict(stage_reason_counts),same_three_scene_stats=common_stats,
    comparisons={k:v['all'] for k,v in summary.items()},figure_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('vectoring-*') if p.suffix in ['.png','.pdf','.svg']}))
print(json.dumps(dict(stage_reason_counts=dict(stage_reason_counts),same_three_scene_stats=common_stats),indent=2))
