"""Complete before/after figures and report from saved results; no inference."""
from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter
import sys,json,hashlib
R=Path(__file__).resolve().parent;B=R.parent;OLD=B/'vectoring-time-window-sensitivity-2026-10-27'
sys.path.insert(0,str(B/'evaluation-python-deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
read=lambda p:json.loads(p.read_text(encoding='utf8'))
write=lambda p,v:p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
summary=read(R/'evaluation-summary.json');manifest=read(R/'run-manifest.json');comp=summary['comparisons']
assert manifest['state']=='complete' and summary['old_results_unchanged']
scenes=[s['scene'] for s in comp['segmented']['after']['scenes']]
local=lambda s:(datetime.strptime(s,'%Y-%m-%dT%HZ')+timedelta(hours=8)).strftime('Sep %d, %H:00')
fmt=lambda x:'NA' if x is None else f'{x:.3f}'
trials={};curves={};all_results=[]
for shape in ['segmented','smooth']:
    for version in ['before','after']:
        folder=OLD/'window-20s'/shape/'results' if version=='before' else R/shape/'results'
        tt=read(folder/'experiment-results.json')['scenes'];trials[shape,version]=tt
        for sid in scenes:
            rows=sorted([t for t in tt if t['scene_id']==sid],key=lambda t:t['replicate'])
            xs=np.array([d['vectoring_aircraft'] for d in rows[0]['dose_curve']])
            ys=np.array([[d['dimension'] if d['status']=='ok' and d['dimension'] is not None else np.nan for d in row['dose_curve']] for row in rows])
            delta=ys-ys[:,0,None]
            curves[shape,version,sid]=(xs,delta,rows[0]['n_aircraft'])
            for row in rows:
                for d in row['dose_curve']:all_results.append(dict(shape=shape,version=version,scene=sid,replicate=row['replicate'],**d))
colors=['#1683b5','#d58b29','#239b80','#c579a5','#8675b5'];navy='#203f53';grey='#87939c'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,
    'axes.edgecolor':'#9faab3','pdf.fonttype':42,'svg.fonttype':'none'})
def save(fig,name):
    for ext in ['png','pdf','svg']:fig.savefig(R/(name+'.'+ext),dpi=220,facecolor='white')
    plt.close(fig)

fig,axes=plt.subplots(2,4,figsize=(18.5,10.5))
fig.subplots_adjust(left=.06,right=.985,top=.80,bottom=.12,wspace=.32,hspace=.60)
fig.suptitle('Vectoring dose response: before and after certificate repair',x=.06,y=.975,ha='left',fontsize=23,fontweight='bold',color=navy)
fig.text(.06,.93,'20 s quality matching · 15 km peak offset · 10 s Encoder input · full dose range · R² ≥ 0.94',fontsize=12,color=navy)
handles=[Line2D([],[],color=c,marker='o',lw=0,ms=5,label=f'Order {i+1} (after)') for i,c in enumerate(colors)]
handles.extend([Line2D([],[],color=grey,lw=2,ls='--',label='Before: mean'),Line2D([],[],color=navy,lw=2.3,label='After: mean')])
fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.055,.905),ncol=7,frameon=False,fontsize=10.5)
for col,sid in enumerate(scenes):
    values=np.concatenate([curves[shape,version,sid][1].ravel() for shape in ['segmented','smooth'] for version in ['before','after']])
    finite=values[np.isfinite(values)];lo=min(0,float(finite.min())) if len(finite) else -.1;hi=max(0,float(finite.max())) if len(finite) else .1
    span=max(hi-lo,.005)
    for row,shape in enumerate(['segmented','smooth']):
        ax=axes[row,col];xb,yb,N=curves[shape,'before',sid];xa,ya,_=curves[shape,'after',sid]
        for k,c in enumerate(colors):
            ax.plot(xa,ya[k],color=c,lw=.6,alpha=.35,zorder=2)
            ax.scatter(xa,ya[k],s=20,color=c,alpha=.85,lw=0,zorder=3)
        # NA doses remain gaps; a mean is shown only when all five exist.
        ax.plot(xb,np.mean(yb,axis=0),color=grey,lw=2.6,ls='--',zorder=4)
        ax.plot(xa,np.mean(ya,axis=0),color=navy,lw=1.9,zorder=5)
        ax.axhline(0,color='#83949f',ls=':',lw=.9)
        b=next(s for s in comp[shape]['before']['scenes'] if s['scene']==sid)
        a=next(s for s in comp[shape]['after']['scenes'] if s['scene']==sid)
        title=('Segmented' if shape=='segmented' else 'Smooth')+' · '+local(sid)
        ax.set_title(f'{title}\nK: {xb[-1]} → {xa[-1]}   N = {N}   median ρ: {fmt(b["median"])} → {fmt(a["median"])}',loc='left',fontsize=10.5,pad=12,color=navy)
        ax.set(xlabel='Aircraft with added Vectoring',ylabel='D − baseline D',xlim=(-.18,7.2),ylim=(lo-.12*span,hi+.12*span))
        ax.xaxis.set_major_locator(MaxNLocator(nbins=8,integer=True));ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.grid(axis='y',alpha=.20)
        failures=int(np.count_nonzero(~np.isfinite(ya)))
        if failures:ax.text(.02,.98,f'{failures} failed D estimates (gaps)',transform=ax.transAxes,va='top',fontsize=9)
fig.text(.06,.045,'Only Sep 15 gains an injectable aircraft (3c6709); all other curves overlap exactly. N: background aircraft; K: injectable aircraft.',fontsize=10.5,color=navy)
fig.text(.06,.02,'Local time UTC+08. Same vertical scale within each scene column. Segmented is schematic; its trajectory does not inherit the smooth motion certificate.',fontsize=10.5,color=navy)
save(fig,'vectoring-full-range-before-after')

fig,axes=plt.subplots(1,2,figsize=(13.8,10),sharey=True)
fig.subplots_adjust(left=.14,right=.97,top=.83,bottom=.09,wspace=.18)
fig.suptitle('Vectoring: every injection-order correlation',x=.06,y=.975,ha='left',fontsize=23,fontweight='bold',color=navy)
fig.text(.06,.935,'20 s quality matching · 25 → 26 candidates · unchanged settings · complete dose range',fontsize=12,color=navy)
fig.legend(handles=[Line2D([],[],marker='o',ls='',ms=7,mfc='white',mec=grey,label='Before (25 candidates)'),
    Line2D([],[],marker='o',ls='',ms=5,color=navy,label='After (26 candidates; colour indicates order)')],loc='upper left',bbox_to_anchor=(.055,.91),ncol=2,frameon=False)
yticks=[];labels=[]
for i,sid in enumerate(scenes):
    for k in range(5):yticks.append(i*6+k);labels.append((local(sid)+' · ' if k==0 else '')+f'O{k+1}')
for ax,shape in zip(axes,['segmented','smooth']):
    for i,sid in enumerate(scenes):
        if i%2==0:ax.axhspan(i*6-.5,i*6+4.5,color='#f1f5f7',zorder=0)
        before=[c for c in comp[shape]['before']['curves'] if c['scene']==sid]
        after=[c for c in comp[shape]['after']['curves'] if c['scene']==sid]
        for k,(b,a) in enumerate(zip(before,after)):
            y=i*6+k
            if b['rho'] is not None and a['rho'] is not None:ax.plot([b['rho'],a['rho']],[y,y],color=colors[k],lw=1.6,zorder=1)
            if b['rho'] is not None:ax.scatter([b['rho']],[y],s=68,facecolor='white',edgecolor=grey,lw=1.4,zorder=2)
            if a['rho'] is not None:ax.scatter([a['rho']],[y],s=24,color=colors[k],zorder=3)
            if a['rho'] is None:ax.text(-1.,y,'NA: '+a['reason'],fontsize=8,va='center')
    ax.axvline(0,color=grey,ls='--',lw=1)
    ax.set(xlim=(-1.07,1.07),ylim=(23,-1),yticks=yticks,yticklabels=labels,xlabel='Spearman ρ')
    ax.set_title('Segmented 15 km (schematic)' if shape=='segmented' else 'Smooth 15 km (screened)',loc='left',fontsize=14,color=navy)
    ax.grid(axis='x',alpha=.2)
fig.text(.06,.035,'Five dependent injection orders per scene. Negative, zero and positive coefficients all retained; overlapping markers indicate no change.',fontsize=10.5,color=navy)
save(fig,'vectoring-order-correlations-before-after')

aggregate=[];scene_table=[];order_table=[]
for shape in ['segmented','smooth']:
    b=comp[shape]['before']['all'];a=comp[shape]['after']['all']
    aggregate.append(f'| {shape} | {fmt(b["median"])} → {fmt(a["median"])} | {b["positive"]} → {a["positive"]} | {b["negative"]} → {a["negative"]} | {b["zero"]} → {a["zero"]} | {b["valid_D"]}/{b["attempted_D"]} → {a["valid_D"]}/{a["attempted_D"]} |')
    for b,a in zip(comp[shape]['before']['curves'],comp[shape]['after']['curves']):
        assert (b['scene'],b['replicate'])==(a['scene'],a['replicate'])
        order_table.append(f'| {shape} | {local(a["scene"])} | {a["replicate"]+1} | {fmt(b["rho"])} | {fmt(a["rho"])} | {a["reason"] or "—"} |')
for sid in scenes:
    vals=[]
    for shape in ['segmented','smooth']:
        b=next(s for s in comp[shape]['before']['scenes'] if s['scene']==sid);a=next(s for s in comp[shape]['after']['scenes'] if s['scene']==sid)
        vals.append(f'{fmt(b["median"])} → {fmt(a["median"])}')
    xb,_,N=curves['segmented','before',sid];xa,_,_=curves['segmented','after',sid]
    scene_table.append(f'| {local(sid)} | {N} | {xb[-1]} → {xa[-1]} | '+' | '.join(vals)+' |')
failed=[d for d in all_results if d['version']=='after' and d['status']!='ok']
exclusions=read(R/'screening-exclusions.json')['records']
reasons=Counter(r['status'] for r in exclusions)
report='''# Vectoring: repaired 20-second version versus the prior 25-candidate result

2026-10-27. New results are saved separately. No Git push or replacement of published results.

## Main result

**The added candidate improves positive association slightly in the September 15 scene, but does not improve the aggregate correlation median or the number of positive orders.** The other three scenes reproduce exactly.

The restored `3c6709` belongs to the scene that already had five positive orders. It does not add candidates to the scenes with mixed or negative responses. The aggregate medians remain 0.887 (segmented) and 0.625 (smooth); the September 15 values change without moving the middle-ranked coefficients in the aggregate.

## What was held fixed

- Same four scenes and 157 background aircraft; all baseline trajectory arrays and embeddings unchanged.
- Same 25 existing intervention trajectories and embeddings. Add only the screened `3c6709` intervention, with two sides for each existing shape. Its original altitude, cadence, length and points outside the intervention are retained.
- Same frozen 10-second, nine-feature Encoder checkpoint `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`, sum pooling and preprocessing.
- Same 20-second quality-message matching rule, fixed 15 km intervention, inherited 5 km prerequisite, and physical checks. The matching time is not the Encoder sampling interval.
- Same five master injection orders, seeds and left/right assignments frozen before the previous evaluation. `3c6709` takes its original position in those master orders; it was not placed to improve D.
- Same exact saved 64-radius grid per scene, R² ≥ 0.94, minimum 30 aircraft, minimum 8 fit scales, minimum 10 pairs, C(r) in [0.02, 0.3], and minimum radius span ratio 2. The existing automatic fit-subrange selection remains unchanged; fixing the radius grid does not lock that subrange.
- Complete dose ranges, including baseline. Failed D would remain NA, and correlation still requires at least five valid doses. No peak selection, truncation, smoothing of the response or dropping of negative orders.

Both existing shapes are retained. **Segmented is a schematic geometric stimulus:** membership is inherited from smooth-route screening, but the segmented trajectory itself does not inherit the smooth C2/motion certificate. Smooth is the continuously checked route. Their results must not be presented as interchangeable evidence of physically feasible vectoring.

## Aggregate results

Each shape has four independent scenes and five dependent injection orders per scene. The reported median is over 20 order coefficients, not a pooled correlation or 20 independent experiments. Repeated baseline records are included in the displayed D-record counts.

| Shape | Median order ρ, before → after | Positive / 20 | Negative / 20 | Zero / 20 | Valid D / recorded doses |
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(aggregate)+'''

## Scene results

Times are Singapore local time (UTC+08). N is background aircraft and K is injectable candidates. D at dose zero is exactly unchanged in every scene.

| Local scene | N | K, before → after | Segmented median ρ | Smooth median ρ |
|---|---:|---:|---:|---:|
'''+ '\n'.join(scene_table)+'''

The September 15 segmented median rises from 0.964 to 0.976; four orders increase slightly and one remains 1.000. Its smooth median rises from 0.929 to 0.952, and all five orders increase. All were positive before the repair. The September 19 smooth median remains −0.571, so the principal negative-response problem is unchanged.

![All scenes and full dose ranges](vectoring-full-range-before-after.png)

[Vector PDF](vectoring-full-range-before-after.pdf) · [Editable SVG](vectoring-full-range-before-after.svg)

![All individual correlations](vectoring-order-correlations-before-after.png)

[Vector PDF](vectoring-order-correlations-before-after.pdf) · [Editable SVG](vectoring-order-correlations-before-after.svg)

## What the comparison supports

The numerical repair restores one usable aircraft-hour without changing earlier inputs, and its inclusion modestly strengthens an already positive scene. It does **not** establish that vectoring generally raises D across scenes, or that simply admitting more candidates ensures a positive response. The segmented median of 0.887 coexists with five negative and one zero coefficient. The smooth result retains eight negative coefficients.

All 150 dose records per shape pass the unchanged D gate; lowering R² would not recover any further plotted point in this run. This before/after comparison does not diagnose every remaining source of mixed response, and a one-aircraft increase is not enough to conclude what a much larger sample would do.

## Failures and preservation

There are **zero failed D records** and **zero unavailable correlations** in the new evaluation. Negative and zero coefficients remain in every summary and figure. The 14 screening exclusions remain saved separately: nine reference rejections (including the unchanged eight chord-geometry cases), and five route rejections. No excluded trajectory is silently restored.

All 290 old dose records across both shapes were recomputed from their frozen embeddings and matched the full saved diagnostics exactly. The three unaffected scenes and the pre-addition portions of all five changed-scene orders also match exactly. Four Encoder baseline probes reproduced exactly; only four new trajectory embeddings were required (two sides × two shapes). There were 8 Encoder calls including probes and 518 D-estimator calls including the old-result replay. New reported dose records total 300 because baseline estimates are reused across orders.

Protected old files and screening records were checked by SHA-256. The new run did not refit references, regenerate routes, alter thresholds, download data, or change the repository's published results.

## Complete correlation ledger

| Shape | Local scene | Order | Before ρ | After ρ | Unavailable reason |
|---|---|---:|---:|---:|---|
'''+ '\n'.join(order_table)+'''

## Files and reproduction

- [Run configuration and protected-source hashes](run-manifest.json)
- [Summary, reproduction and pairing checks](evaluation-summary.json)
- [All screening exclusions](screening-exclusions.json)
- [All D failures, including an explicit empty list when none fail](failed-D-records.json)
- [Segmented results and diagnostics](segmented/results/experiment-results.json)
- [Smooth results and diagnostics](smooth/results/experiment-results.json)
- [Evaluation script](run_evaluation.py)
- [Report and figure script](report_results.py)

The local package also contains population arrays, embeddings, per-scene radius grids, five order lists, and complete fit diagnostics at every dose. These derived data stay local. Reproduction needs the preserved local inputs and frozen checkpoint; the runner refuses to overwrite an existing run manifest.
'''
write(R/'failed-D-records.json',dict(count=len(failed),records=failed))
assert not failed
assert all(sha(Path(p))==h for p,h in manifest['protected_sources'].items())
(R/'report.md').write_text(report,encoding='utf8')
write(R/'report-verification.json',dict(source_summary_sha256=sha(R/'evaluation-summary.json'),all_scenes_retained=True,
    all_dose_ranges_retained=True,all_order_coefficients_reported=40,new_failed_D_records=len(failed),
    screening_exclusions=len(exclusions),screening_exclusion_classes=dict(reasons),old_sources_unchanged=True,
    figure_files={p.name:sha(p) for pattern in ['*.png','*.pdf','*.svg'] for p in R.glob(pattern)}))
print('Report and complete-range figures generated; old source hashes verified.')
