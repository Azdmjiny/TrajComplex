"""Re-evaluate existing dose outputs; preserve source data and full-range results."""
import argparse,csv,hashlib,json,platform
from collections import defaultdict
from pathlib import Path
import numpy as np
import scipy
from truncation import choose_cutoff,curve_correlation,finite_ok
ROOT=Path(__file__).resolve().parents[1]

def describe(rs):
    vv=[float(v) for v in rs if v is not None and np.isfinite(v)]
    return dict(n=len(vv),positive=sum(v>0 for v in vv),positive_fraction=sum(v>0 for v in vv)/len(vv) if vv else None,median=float(np.median(vv)) if vv else None)

def summarize(trials,kind,truncate=False):
    by=defaultdict(list)
    for t in trials:by[t['scene_id']].append(t)
    rows=[];scenes=[];selection=[]
    for sid,ts in sorted(by.items()):
        peak=choose_cutoff(ts) if truncate else None
        cutoff=peak['cutoff'] if peak else None
        base=ts[0]['dose_curve'][0];baseok=bool(finite_ok(base));start=len(rows)
        for t in ts:
            full=curve_correlation(t['dose_curve'],kind+'_aircraft')
            kept=curve_correlation(t['dose_curve'],kind+'_aircraft',cutoff) if (not truncate or cutoff is not None) else dict(rho=None,reason='no_eligible_peak',total=0,valid=0)
            rows.append(dict(scene=sid,replicate=t['replicate'],baseline_ok=baseok,n_aircraft=t['n_aircraft'],cutoff=cutoff,full=full,retained=kept))
            for p in t['dose_curve']:
                keep=not truncate or (cutoff is not None and p[kind+'_aircraft']<=cutoff)
                reason='after_cutoff_or_no_peak' if not keep else ('invalid_D' if not finite_ok(p) else kept['reason'])
                selection.append(dict(scene_id=sid,replicate=t['replicate'],dose=p[kind+'_aircraft'],D=p['dimension'],status=p['status'],within_retained_range=keep,included_in_retained_rho=bool(keep and finite_ok(p) and kept['rho'] is not None),exclusion_reason=reason,cutoff=cutoff))
        rr=rows[start:]
        scenes.append(dict(scene_id=sid,n_aircraft=ts[0]['n_aircraft'],baseline_ok=baseok,baseline_D=base['dimension'],cutoff=cutoff,cutoff_fraction=cutoff/ts[0]['n_aircraft'] if cutoff is not None else None,peak=peak,full=describe([r['full']['rho'] for r in rr]),retained=describe([r['retained']['rho'] for r in rr])))
    ss={}
    for group,rr in [('all',rows),('baseline_ok',[r for r in rows if r['baseline_ok']])]:
        both=[r for r in rr if r['full']['rho'] is not None and r['retained']['rho'] is not None]
        ss[group]={k:describe([r[k]['rho'] for r in rr]) for k in ['full','retained']}
        ss[group]['paired_comparison']={k:describe([r[k]['rho'] for r in both]) for k in ['full','retained']}
        ss[group]['point_counts']={k:dict(total=sum(r[k]['total'] for r in rr),valid=sum(r[k]['valid'] for r in rr),participating_in_rho=sum(r[k]['valid'] for r in rr if r[k]['rho'] is not None)) for k in ['full','retained']}
    ss['hour_level']={k:describe([s[k]['median'] for s in scenes]) for k in ['full','retained']}
    ss['hour_level_baseline_ok']={k:describe([s[k]['median'] for s in scenes if s['baseline_ok']]) for k in ['full','retained']}
    ss['scenes']=scenes;ss['curves']=rows
    return ss,selection

def main():
    out=ROOT/'results'
    source=out/'experiment-results.json'
    inputs=json.loads(source.read_text(encoding='utf8'))
    summaries={}
    for variant,kinds in inputs.items():
        summaries[variant]={}
        for kind,d in kinds.items():
            summary,selection=summarize(d['scenes'],kind,truncate=kind=='holding')
            summaries[variant][kind]=summary
            filename=f'{variant}-{kind}-point-selection.csv'
            with (out/filename).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(selection[0]));w.writeheader();w.writerows(selection)
    summaries['aircraft_count']=json.loads((out/'aircraft-count-sensitivity.json').read_text(encoding='utf8'))['comparisons']
    (out/'summary.json').write_text(json.dumps(summaries,indent=2,allow_nan=False),encoding='utf8')
    manifest=dict(method='Earliest maximum of per-scene available-replicate mean D; peak selection needs >=3 valid replicates; shared cutoff across 5 orders; no smoothing; peak included',scope='Holding only. Vectoring full dose retained; primary vectoring uses both-side maneuver speed screening.',interpretation='Outcome-selected exploratory association, not an independently validated operating range; no confirmatory p-values.',input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,out/'aircraft-count-sensitivity.json']},python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
    (out/'analysis-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('Updated consolidated summaries and selection CSVs.')
if __name__=='__main__':main()
