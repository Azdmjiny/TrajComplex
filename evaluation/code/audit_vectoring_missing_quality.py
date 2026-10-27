"""Replay cached status evidence for 90 scoped background records and plot saved delta D.

No downloads, imputation, trajectory fitting/generation, Encoder calls or D fits.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from plot_holding_midpoint_response import ROOT, COLORS, NAVY, label, sha


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def run(base,out):
    active=ROOT/'runs/segmented-15km'
    month=base/'opensky-month-coverage'
    paths=[]
    target={};sources={};scenes=[];populations={}
    for p in sorted((active/'population').glob('*-records.json')):
        paths.append(p);sid=p.name.replace('-records.json','');scenes.append(sid)
        populations[sid]=read(p)
        for r in populations[sid]:
            if 'missing_quality_matches' in r['rejection_reasons']:target[sid,r['icao24']]=r
        p=month/'source-tracks'/(sid+'.json.gz');paths.append(p)
        with gzip.open(p,'rt',encoding='utf8') as f:sources[sid]={r['icao24']:r for r in json.load(f)}
    assert len(target)==90
    old_path=month/'status-screen.json';paths.append(old_path)
    old={(r['scene'],r['icao24']):r for r in read(old_path)['tracks']}
    jobs_path=month/'status-jobs.json';paths.append(jobs_path)
    rows=defaultdict(list);query_source={}
    for job in read(jobs_path):
        if not set(job['scenes'])&set(scenes):continue
        p=month/'queries'/(job['name']+'.json');paths.append(p);q=read(p)
        assert q['stats']['state']=='FINISHED'
        for values in q['data']:
            r=dict(zip(q['columns'],values));key=r['scene'],r['icao24']
            if key in target:rows[key].append(r);query_source[key]=dict(path=str(p),query_id=q['query_id'])
    assert set(rows)==set(target)
    # This module has no side effects; it reproduces the existing grid and gates.
    code=base/'vectoring-direction-repair/code';sys.path.insert(0,str(code))
    from position_timeline import position_grid
    paths.append(code/'position_timeline.py')
    details=[];point_records=[]
    for key in sorted(target):
        rr=sorted(rows[key],key=lambda r:r['source_index']);raw=np.array(sources[key[0]][key[1]]['source_records'],float)
        assert len(rr)==len(raw)
        grid=position_grid(raw,sample_s=10);assert len(grid)==target[key]['grid_points']
        start=(len(grid)-60)//2;join_low=grid[start-1];join_high=grid[start+61]
        # Diagnostic support only: includes the raw source knots bracketing both joins.
        lo=max(0,int(np.searchsorted(raw[:,4],join_low,side='right')-1))
        hi=min(len(raw)-1,int(np.searchsorted(raw[:,4],join_high,side='left')))
        why=Counter();sub=Counter();bad=[];lags=[];inside_bad=[];inside_hard=[]
        for i,r in enumerate(rr):
            assert i==r['source_index'] and raw[i,4]==r['pt'] and not r['any_bad_time']
            before,after=r['previous_t'],r['next_t']
            agree=(before is not None and after is not None and r['previous_known'] and r['next_known'] and
                   r['previous_quality']==r['next_quality'] and
                   (r['exact_category_count']==0 or(r['exact_category_count']==1 and r['exact_quality']==r['previous_quality'])))
            subreasons=[];lag=None
            if not agree:
                reason='status_missing_unknown_or_conflicting'
                if before is None or after is None:subreasons.append('missing_neighbor')
                if (before is not None and not r['previous_known']) or(after is not None and not r['next_known']):subreasons.append('unknown_nonpositive_or_ambiguous_neighbor')
                if before is not None and after is not None and r['previous_quality']!=r['next_quality']:subreasons.append('neighbor_category_disagreement')
                if r['exact_category_count']>1 or(r['exact_category_count']==1 and r['exact_quality']!=r['previous_quality']):subreasons.append('exact_category_conflict')
                sub.update(subreasons)
                if lo<=i<=hi:inside_hard.append(i)
            else:
                lag=max(r['pt']-before,after-r['pt']);assert lag>=0;lags.append(lag)
                reason='status_bracket_over_10_s' if lag>10 else None
                if float(r['previous_quality'].split('|')[1]) not in range(1,12):reason='unsupported_nacp'
            if reason:
                why[reason]+=1;bad.append(i)
                if lo<=i<=hi:inside_bad.append(i)
            point_records.append(dict(scene=key[0],icao24=key[1],source_index=i,position_time=r['pt'],
                                      previous_time=before,next_time=after,previous_quality=r['previous_quality'],
                                      next_quality=r['next_quality'],reason=reason,subreasons=subreasons,max_side_gap_s=lag,
                                      in_maneuver_and_join_support=lo<=i<=hi))
        assert bad==old[key]['bad_indices'] and dict(why)==old[key]['reasons']
        only_time=set(why)=={'status_bracket_over_10_s'}
        details.append(dict(scene=key[0],icao24=key[1],source_points=len(raw),grid_points=len(grid),
                            status_reasons=dict(why),detailed_reason_counts=dict(sub),timing_only=only_time,
                            required_symmetric_status_window_s=max(lags) if only_time else None,
                            bad_source_indices=bad,join_support_source_range=[lo,hi],
                            bad_join_support_indices=inside_bad,unknown_or_conflicting_join_indices=inside_hard,
                            passes_10s_in_local_support=not inside_bad,query=query_source[key],
                            newly_accepted=False,exact_nic_status='not supplemented in approved 26-candidate cache'))
    # Verify that existing exact evidence is explicitly scoped to the approved 26.
    nic_path=base/'coverage-nic-supplement/candidate-matches.json';paths.append(nic_path)
    nic=read(nic_path)
    # Index only known evidence records, never infer quality from a filename or nearby timestamp.
    nic_evidence=base/'coverage-nic-supplement/point-evidence.jsonl.gz';paths.append(nic_evidence)
    nic_keys=set()
    with gzip.open(nic_evidence,'rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);nic_keys.add((r['scene'],r['icao24']))
    assert len(nic_keys)==26 and not nic_keys&set(target)
    timing=[r for r in details if r['timing_only']]
    assert len(timing)==46
    byscene=[]
    for sid in scenes:
        rr=[r for r in details if r['scene']==sid]
        byscene.append(dict(scene=sid,missing=len(rr),time_only=sum(r['timing_only'] for r in rr),
                            unresolved_status=sum(not r['timing_only'] for r in rr),
                            timing_15s=sum(r['timing_only'] and r['required_symmetric_status_window_s']<=15 for r in rr),
                            timing_20s=sum(r['timing_only'] and r['required_symmetric_status_window_s']<=20 for r in rr),
                            local_10s_only_pass=sum(r['passes_10s_in_local_support'] for r in rr)))
    summary=dict(target_records=90,already_status_checked=90,status_replay_mismatches=0,
                  timing_only=46,missing_unknown_or_conflicting=44,newly_accepted=0,
                  timing_gap_quantiles_s=np.quantile([r['required_symmetric_status_window_s'] for r in timing],[0,.25,.5,.75,1]).tolist(),
                  scenes=byscene,exact_nic_supplement_overlap=0,
                  restrictions=dict(network_data_queries=0,new_trajectory_fits=0,new_generated_routes=0,new_encoder_calls=0,new_D_fits=0,threshold_changes=0))
    (out/'candidate-audit.json').write_text(json.dumps(details,indent=2)+'\n',encoding='utf8')
    with gzip.open(out/'point-audit.jsonl.gz','wt',encoding='utf8') as f:
        for r in point_records:f.write(json.dumps(r)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    near=sorted([r for r in timing if r['required_symmetric_status_window_s']<=15],key=lambda r:(r['scene'],r['icao24']))
    (out/'possible-15s-sensitivity-tasks.json').write_text(json.dumps(near,indent=2)+'\n',encoding='utf8')
    with (out/'candidate-audit.csv').open('w',newline='',encoding='utf8') as f:
        keys=['scene','icao24','source_points','timing_only','required_symmetric_status_window_s','passes_10s_in_local_support','newly_accepted']
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:r[k] for k in keys} for r in details)

    # Full-range delta-D view of the unchanged, published 15 km arms.
    arms={};summaries={}
    for arm in ['segmented','smooth-control']:
        p=active/'results'/arm/'experiment-results.json';paths.append(p)
        arms[arm]=read(p)['qc500_safe']['vectoring']['scenes']
        p=active/'results'/arm/'summary.json';paths.append(p);summaries[arm]=read(p)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,4,figsize=(19,10.5))
    fig.subplots_adjust(left=.06,right=.985,top=.78,bottom=.18,hspace=.48,wspace=.30)
    fig.suptitle('Vectoring: complete dose response relative to baseline',x=.06,y=.97,ha='left',fontsize=23,color=NAVY,fontweight='bold')
    fig.text(.06,.927,'All four scenes • 15 km peak • five saved orders • R² ≥ 0.94 • no truncation or smoothing • times UTC+08',fontsize=12)
    handles=[Line2D([],[],marker='o',ls='',color=c,ms=5,label=f'Order {i+1}') for i,c in enumerate(COLORS)]
    handles+=[Line2D([],[],color=NAVY,lw=2.5,label='Mean of five orders')]
    fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.055,.896),ncol=6,frameon=False)
    for col,sid in enumerate(scenes):
        allvals=[]
        for row,arm in enumerate(['segmented','smooth-control']):
            ax=axes[row,col];rr=sorted([r for r in arms[arm] if r['scene_id']==sid],key=lambda r:r['replicate'])
            baseline=rr[0]['dose_curve'][0]['dimension'];x=np.array([p['vectoring_aircraft'] for p in rr[0]['dose_curve']])
            y=np.array([[p['dimension']-baseline if p['status']=='ok' else np.nan for p in r['dose_curve']] for r in rr])
            assert np.isfinite(y).all() and all(r['dose_curve'][0]['dimension']==baseline for r in rr)
            allvals.extend(y.ravel());ss=next(s for s in summaries[arm]['scenes'] if s['scene_id']==sid)
            for k,c in enumerate(COLORS):ax.scatter(x,y[k],color=c,s=27,alpha=.8,linewidths=0,zorder=3)
            ax.plot(x,y.mean(0),color=NAVY,lw=2.4,zorder=4)
            ax.axhline(0,ls='--',lw=.85,color='#728492')
            rho=ss['full']['median'];rho_text='NA (only 4 doses)' if rho is None else f'{rho:.3f}'
            shape='Segmented (schematic)' if row==0 else 'Smooth (screened)'
            ax.set_title(f'{label(ss)} | {shape}\nN={rr[0]["n_aircraft"]}, K={rr[0]["n_vectoring_eligible"]} | median order ρ={rho_text}',loc='left',fontsize=10.5,pad=12,color=NAVY)
            ax.set(xlabel='Injected Vectoring aircraft',ylabel='D − baseline D',xlim=(-.15,x[-1]+.15))
            ax.xaxis.set_major_locator(MaxNLocator(integer=True,nbins=7));ax.grid(axis='y',alpha=.22)
        lo=min(0,min(allvals));hi=max(0,max(allvals));span=max(hi-lo,.001)
        for ax in axes[:,col]:ax.set_ylim(lo-.16*span,hi+.16*span)
    fig.text(.06,.115,'Each column uses its own labelled vertical scale, shared between the two shapes. Across-column apparent slopes do not compare effect sizes.',fontsize=10)
    fig.text(.06,.085,'All 115/115 D fits pass in each arm. September 14 has four dose levels, so its order correlations remain NA under the existing five-dose rule.',fontsize=10)
    fig.text(.06,.055,'All orders and signs retained. Shared candidates, side assignments and baselines; dependent repeats, not independent scenes. No confidence interval implied.',fontsize=10)
    fig.text(.06,.025,'Segmented routes are schematic and bypass the smooth route motion certificate. ΔD changes the vertical origin only, not Spearman correlation.',fontsize=10)
    for ext in ['png','pdf','svg']:fig.savefig(out/f'vectoring-full-range-delta.{ext}',dpi=220,facecolor='white')
    plt.close(fig)
    rows='\n'.join(f'| {r["scene"]} | {r["missing"]} | {r["time_only"]} | {r["unresolved_status"]} | {r["timing_15s"]} | {r["timing_20s"]} | {r["local_10s_only_pass"]} |' for r in byscene)
    tasks='\n'.join(f'| {r["scene"]} | {r["icao24"]} | {r["required_symmetric_status_window_s"]:.3f} | {len(r["bad_source_indices"])} / {r["source_points"]} |' for r in near)
    report='''# Vectoring: audit of 90 missing-quality labels and full-range delta-D display

2026-10-27. All work uses existing local records. No OpenSky data query, new fit, route generation, Encoder inference, D estimation, threshold change or Git push. Current accepted population remains 19. Original results and reports remain unchanged.

## The earlier generic label was incomplete

All 90 records labelled missing_quality_matches in the final population had already undergone source-by-source NACp/status screening in the monthly coverage audit. This replay matches every source index and actual position-update timestamp to cached server results, and reproduces all old failed indices and reason counts with zero mismatches. None passes the existing full-track status rule. They were not simply 90 unexamined aircraft omitted arbitrarily from the 26-candidate scope.

Of these, 46 have known, matching status categories on both sides at every source point but exceed the 10-second per-side age rule somewhere. The other 44 have at least one missing, unknown, nonpositive, ambiguous or conflicting status bracket; some also have timing failures. These are mutually exclusive track categories. They describe available evidence, not proof of physical trajectory corruption or permanent irrecoverability.

| UTC scene | Audited missing labels | Timing-only | Other status issue | Would pass status at <=15 s | Would pass status at <=20 s | Only local support passes current 10 s |
|---|---:|---:|---:|---:|---:|---:|
'''+rows+'''

The 15/20-second columns are counterfactual inventory counts, not accepted candidates, new production thresholds or validation experiments. Only timing-only tracks are counted: no conflicting/unknown category is silently filled. Exact position/NIC matching, fitting, direction and both route checks remain outstanding. The existing 26-candidate exact-NIC supplement contains no records for these 90 scene-aircraft pairs.

The last column checks the existing 600-second midpoint maneuver and its one-sample joins, plus the source knots bracketing those joins. It is only a localization diagnostic. The current full-track spline depends on observations outside that span, so passing this subset cannot justify keeping the full-track fit while ignoring outside quality. A local-fit alternative would change the reference method and must be designed and verified separately.

The timing-only records require per-side maxima ranging from about 10.412 seconds to 12,287.112 seconds; median about 25.015 seconds. This is not uniformly small timestamp jitter. Very long gaps must not be accepted as fresh evidence. A 15-second sensitivity would expose 10 additional status-eligible records (4/1/1/4 across scenes), while 20 seconds would expose 21 (6/3/5/7). Neither number predicts the final injectable count.

## Ten nearest candidates for a possible bounded sensitivity, not executed

| UTC scene | Aircraft | Required per-side maximum (s) | Current failed points / total |
|---|---|---:|---:|
'''+tasks+'''

## What a reduced requirement would mean

The most localized relaxation to consider is the status matching age, with both sides still known, positive and identical, all exact NIC evidence still required, and all original geometry/motion conditions retained. A <=15 s engineering sensitivity could be declared before any D outcome is examined for these ten records, kept separate from the <=10 s analysis. It is NOT a standards-certified validity interval. Do not reduce position-accuracy categories, fill missing quality, accept conflicting statuses, relax direction/peak/acceleration gates, or shorten the maneuver solely to increase count.

The U.S. ADS-B equipment requirement describes broadcasting changes in NACp/NACv/SDA/SIL within 10 seconds; this is a change-announcement latency, not a rule guaranteeing that two received equal categories bracket a position accurately, nor a direct legal requirement for this Singapore research matcher. It does not validate a 15- or 20-second matching window. [Official CFR text](https://www.govinfo.gov/content/pkg/CFR-2025-title14-vol2/pdf/CFR-2025-title14-vol2-part91-subpartC.pdf).

OpenSky's decoded tables summarize duplicate messages with first/last reception times and counts. The cached status query uses those endpoints and sensor endpoints. Therefore an apparent endpoint gap does not by itself prove no intermediate reception occurred; equally, it does not authorize inventing intermediate timestamps. [OpenSky historical-data documentation](https://openskynetwork.github.io/opensky-api/trino).

## Separate geometry and solver audit

- Four of the original 26 quality-complete candidates fail the independent chord-progress condition: three have witnessed nonpositive progress, one cannot certify positive progress. Local direction reliability passed for all 26. This is a limitation of the chosen chord-normal reference/generator, not a reason to relabel their directions unreliable or waive the condition in the same generator.
- Candidate 750596 fails the 5 km route solve: left reaches 100 iterations; right reports a line-search directional derivative failure. Trial longitudinal acceleration remains invalid. More iterations or another search may be investigated separately; current failures are not accepted routes and do not prove global infeasibility.
- The 15 km stage further rejects 750447 for left longitudinal acceleration and 750449 for right continuous-peak feedback stalling. The latter legacy error string still contains “5km”; stage configuration is 15 km. Embedded side_diagnostics in the copied records describe the earlier 5 km passes and must not be quoted as 15 km certificates.
- The segmented cohort inherits the 19 smooth-accepted candidates. Its own generation accepts all 19 and skips the smooth deformed-motion certificate. Dropping the inherited cohort restriction would change the matched comparison and does not confer physical validity on segmented routes.

## Full-range delta-D display

![All four scenes, full-range delta D](vectoring-full-range-delta.png)

[Vector PDF](vectoring-full-range-delta.pdf) · [SVG](vectoring-full-range-delta.svg)

Both shapes retain all orders, all dose levels, negative responses and NA correlations. Each column has one scale shared by both shapes; scales differ between scene columns. The plotted black line is the mean of all five available orders (all fits pass), whereas panel rho is the median of five order coefficients. These are different summaries. Baselines, assignments and results are unchanged; subtraction cannot alter the order coefficients. This display supplements, rather than replaces, the existing absolute-D figures.

## Next decision

The local audit is complete and restores zero new accepted candidates under the existing rule. Before a new correlation run, decide whether to pursue missing reception evidence under the original rule, or a clearly separated <=15 s engineering sensitivity for the ten nearest records. Either route needs exact position/NIC evidence and unchanged downstream checks. No automatic broad download or source-data imputation is performed here.

Source-point audits and proposed tasks remain local. Candidate counts are not independent flight counts across the month. Primary results remain unchanged, and no favorable subset is selected using D.
'''
    (out/'report.md').write_text(report,encoding='utf8')
    hashes={str(p):sha(p) for p in paths}
    (out/'source-manifest.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary,indent=2));print('Local audit and delta-D figures complete.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('Choose a new directory; old outputs are protected.')
    a.output.mkdir(parents=True);run(a.base,a.output)
