#!/usr/bin/env python3
"""WSSS 2 Holding/Vectoring experiment with absolute and percent metrics.

Uses the fixed epoch-60 Encoder, no Holding distance cutoff, and persists dose-level
D plus sequence and scene summaries for both absolute and relative response."""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, math, os, sys, time
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.spatial.distance import pdist
from scipy.stats import theilslopes

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(Path(__file__).resolve().parent))
import wsss2_injection as W

REPEATS = W.REPEATS
SEED = W.SEED
EVENT_CAP = W.EVENT_CAP
DOSE_ZERO_POLICY = 'no baseline D cutoff; retain every estimable baseline scene'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def summarize_curve(doses, deltas):
    """Metrics on a contiguous per-sequence valid prefix, explicitly reported."""
    doses = np.asarray(doses, dtype=float); deltas = np.asarray(deltas, dtype=float)
    if len(doses) < 2 or doses[0] != 0 or doses[-1] <= 0:
        return {'dose_avg_delta_D': None, 'theil_sen_D_per_event': None, 'n_positive': None, 'n_negative': None, 'n_zero': None, 'support_k_max': int(doses[-1]) if len(doses) else None}
    kmax = doses[-1]
    area = float(np.trapz(deltas, doses) / kmax)
    slope = float(theilslopes(deltas, doses).slope)
    return {'dose_avg_delta_D': area, 'theil_sen_D_per_event': slope, 'positive_dose_points': int(np.sum(deltas[1:] > 0)), 'negative_dose_points': int(np.sum(deltas[1:] < 0)), 'zero_dose_points': int(np.sum(deltas[1:] == 0)), 'support_k_max': int(kmax)}

def write_csv(path, rows):
    if not rows:
        Path(path).write_text('', encoding='utf-8'); return
    with Path(path).open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader(); w.writerows(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--limit-scenes', type=int, default=None, help='Smoke test only')
    ap.add_argument('--no-percent-metrics', dest='output_percent', action='store_false', default=True, help='Disable percentage-response CSVs; absolute Delta-D outputs remain available')
    args = ap.parse_args()
    out = args.output.resolve()
    if out.exists(): raise FileExistsError(f'Refusing existing output directory: {out}')
    paths = sorted(W.HOURS.glob('*.npz'))
    if len(paths) != 720: raise RuntimeError(f'Expected exactly 720 archives, got {len(paths)}')
    if args.limit_scenes: paths = paths[:args.limit_scenes]
    checkpoint = W.CHECKPOINT.resolve()
    checkpoint_sha = sha(checkpoint)
    if checkpoint_sha != W.CHECKPOINT_SHA_EXPECTED: raise RuntimeError('Checkpoint SHA mismatch')
    import torch
    from Encoder.trajectory_encoder.inference import FrozenEncoder
    from complexity.calculator import ComplexityConfig, estimate_complexity
    torch.set_num_threads(2)
    try: torch.use_deterministic_algorithms(True)
    except Exception: pass
    enc = FrozenEncoder(checkpoint, pooling='sum', device='cpu')
    if enc.preprocess['preprocessor_id'] != W.PREPROCESSOR_ID_EXPECTED: raise RuntimeError('Preprocessor ID mismatch')
    cfg = ComplexityConfig(normalize=False, n_radii=64, min_samples=15, min_fit_points=8, min_pairs=10, correlation_bounds=(0.02, 0.30), min_radius_ratio=2.0, min_r_squared=0.90, max_pairs=5_000_000)
    out.mkdir(parents=True)
    dose_rows=[]; sequence_rows=[]; scene_rows=[]; event_rows=[]; started=time.time()
    for scene_i, path in enumerate(paths):
        scene=path.stem; tracks=W.load_scene(path); ids=sorted(tracks)
        if not ids:
            scene_rows.append({'scene_id':scene,'status':'no_eligible_tracks','n_tracks':0,'baseline_D':''}); continue
        base=np.asarray([enc.encode(tracks[a])['embedding'] for a in ids],dtype=float)
        distances=pdist(base); positive=distances[distances>0]
        if len(ids)<cfg.min_samples or not len(positive) or positive.min()==positive.max():
            scene_rows.append({'scene_id':scene,'status':'baseline_unestimable','n_tracks':len(ids),'baseline_D':'','reason':'insufficient_samples_or_distance_range'}); continue
        radii=np.geomspace(positive.min(),positive.max(),cfg.n_radii)
        baseline=estimate_complexity(base,config=cfg,radii=radii,scene_id=scene).to_dict()
        if baseline['status']!='ok' or baseline['dimension'] is None:
            scene_rows.append({'scene_id':scene,'status':'baseline_unestimable','n_tracks':len(ids),'baseline_D':'','reason':baseline['reason']}); continue
        d0=float(baseline['dimension']); scene_modes={} ; mode_missing={} ; vector_windows=0; holding_rejections={}
        for mode in ('holding','vectoring'):
            candidates={}; rejected=defaultdict(int)
            for aid,track in tracks.items():
                if mode=='holding':
                    c,reason=W.holding_candidate(track)
                    if c is not None: candidates[aid]=c
                    elif reason: rejected[reason]+=1
                else:
                    ws=W.vector_candidates(track); vector_windows+=len(ws)
                    if ws: candidates[aid]=ws
            if mode=='holding': holding_rejections=dict(rejected)
            if not candidates:
                maxdose=0; sequences=[[] for _ in range(REPEATS)]
                missing_reason='no_injection_candidates'
            else:
                maxdose=min(EVENT_CAP,len(candidates)) if mode=='holding' else min(EVENT_CAP,sum(len(ws) for ws in candidates.values()))
                sequences=[]
                for rep in range(REPEATS):
                    rng=np.random.default_rng(SEED+scene_i*100003+rep+(0 if mode=='holding' else 50000000))
                    if mode=='holding': seq=W.holding_sequence(candidates,rng)
                    else:
                        remaining={a:list(ws) for a,ws in candidates.items()}; seq=[]
                        for _ in range(maxdose):
                            available=sorted(a for a,ws in remaining.items() if ws)
                            if not available: break
                            aid=available[int(rng.integers(len(available)))]; j=int(rng.integers(len(remaining[aid])))
                            seq.append((aid,remaining[aid].pop(j),int(rng.choice([-1,1]))))
                    sequences.append(seq)
                missing_reason=''
            per_rep=[]
            for rep,seq in enumerate(sequences):
                current=base.copy(); holding_states={a:(tracks[a].copy(),['original']*len(tracks[a])) for a in ids} if mode=='holding' else None
                vector_tracks={a:tracks[a].copy() for a in ids} if mode=='vectoring' else None
                values=[0.0]; statuses=['ok']; reasons=['']; selected=[]
                dose_rows.append({'scene_id':scene,'mode':mode,'repeat':rep,'dose':0,'D':d0,'delta_D':0.0,'status':'ok','reason':'','r_squared':baseline['r_squared'],'fit_radius_min':baseline['fit_radius_range'][0],'fit_radius_max':baseline['fit_radius_range'][1],'n_tracks':len(ids)})
                for dose in range(1,maxdose+1):
                    if len(seq)<dose:
                        value=None; result=None; status='missing_dose_sequence'; reason='sequence_shorter_than_dose'
                    else:
                        if mode=='holding':
                            aid=seq[dose-1]; prev=holding_states[aid][0]
                            state,removed=W.holding_inject_trim(holding_states[aid],candidates[aid])
                            if aid in selected: raise AssertionError('holding repeated within sequence')
                            if removed!={'original':36,'holding':0} or state[1].count('holding')!=36 or np.array_equal(prev,state[0]): raise AssertionError('holding effective exposure invariant failed')
                            holding_states[aid]=state; current[ids.index(aid)]=enc.encode(state[0])['embedding']; selected.append(aid)
                            retained=sum(tags.count('holding') for _,tags in holding_states.values())
                            if retained!=36*dose: raise AssertionError('holding cumulative dose mismatch')
                            event={'scene_id':scene,'mode':mode,'repeat':rep,'dose':dose,'flight_id':aid,'retained_holding_points':retained,'removed_original_points':36,'anchor_distance_m':candidates[aid]['anchor_distance_m']}
                        else:
                            aid,w,side=seq[dose-1]; injected,diag=W.vector_segment(tracks[aid],w['start'],side)
                            vector_tracks[aid][w['start']:w['start']+W.VECTOR_WINDOW]=injected
                            current[ids.index(aid)]=enc.encode(vector_tracks[aid])['embedding']
                            event={'scene_id':scene,'mode':mode,'repeat':rep,'dose':dose,'flight_id':aid,'window_start':w['start'],'side':side,'peak_measured_m':diag['peak_measured_m']}
                        event_rows.append(event)
                        result=estimate_complexity(current,config=cfg,radii=radii,scene_id=scene).to_dict()
                        status=result['status']; reason=result.get('reason') or ''
                        value=float(result['dimension']-d0) if status=='ok' and result['dimension'] is not None else None
                    values.append(value); statuses.append(status); reasons.append(reason)
                    dose_rows.append({'scene_id':scene,'mode':mode,'repeat':rep,'dose':dose,'D':(d0+value if value is not None else ''),'delta_D':(value if value is not None else ''),'status':status,'reason':reason,'r_squared':(result.get('r_squared','') if result else ''),'fit_radius_min':(result['fit_radius_range'][0] if result and result.get('fit_radius_range') else ''),'fit_radius_max':(result['fit_radius_range'][1] if result and result.get('fit_radius_range') else ''),'n_tracks':len(ids)})
                # Include baseline record in per-sequence metric curve.
                valid_prefix=[0]
                for k in range(1,maxdose+1):
                    if values[k] is None: break
                    valid_prefix.append(k)
                if len(valid_prefix)>=2:
                    curve_vals=[values[k] for k in valid_prefix]
                    metrics=summarize_curve(valid_prefix,curve_vals)
                else:
                    metrics={'dose_avg_delta_D':None,'theil_sen_D_per_event':None,'positive_dose_points':None,'negative_dose_points':None,'zero_dose_points':None,'support_k_max':0}
                row={'scene_id':scene,'mode':mode,'repeat':rep,'max_dose':maxdose,'eligible_units':len(candidates) if mode=='holding' else sum(len(ws) for ws in candidates.values()),'valid_prefix_doses':len(valid_prefix),'valid_support_k_max':valid_prefix[-1],'missing_after_dose':(valid_prefix[-1]+1 if len(valid_prefix)<maxdose+1 else ''),'missing_reason':(reasons[valid_prefix[-1]+1] if len(valid_prefix)<maxdose+1 else ''),**metrics}
                sequence_rows.append(row); per_rep.append(row)
            # scene-level summaries are medians of per-sequence metrics, not metrics of a median curve.
            for metric in ('dose_avg_delta_D','theil_sen_D_per_event'):
                vals=[r[metric] for r in per_rep if r[metric] is not None]
                scene_modes[mode+'_'+metric+'_median']=float(np.median(vals)) if vals else ''
                scene_modes[mode+'_'+metric+'_q1']=float(np.quantile(vals,.25)) if vals else ''
                scene_modes[mode+'_'+metric+'_q3']=float(np.quantile(vals,.75)) if vals else ''
            signs=[r for r in per_rep if r['dose_avg_delta_D'] is not None]
            scene_modes[mode+'_direction_valid_repeats']=len(signs)
            scene_modes[mode+'_direction_positive']=sum(r['dose_avg_delta_D']>0 for r in signs)
            scene_modes[mode+'_direction_negative']=sum(r['dose_avg_delta_D']<0 for r in signs)
            scene_modes[mode+'_direction_zero']=sum(r['dose_avg_delta_D']==0 for r in signs)
            scene_modes[mode+'_effective_units']=len(candidates) if mode=='holding' else sum(len(ws) for ws in candidates.values())
            scene_modes[mode+'_max_dose']=maxdose; scene_modes[mode+'_missing_reason']=missing_reason
            mode_missing[mode]=missing_reason
        scene_rows.append({'scene_id':scene,'status':'baseline_estimable','n_tracks':len(ids),'baseline_D':d0,'baseline_R2':baseline['r_squared'],'holding_rejected_candidates':json.dumps(holding_rejections,sort_keys=True),**scene_modes})
        if (scene_i+1)%20==0 or scene_i+1==len(paths):
            print(json.dumps({'scenes_done':scene_i+1,'scenes_total':len(paths),'scene':scene,'elapsed_s':round(time.time()-started,1)}),flush=True)
    write_csv(out/'dose-repeat-results.csv',dose_rows)
    write_csv(out/'sequence-metrics.csv',sequence_rows)
    write_csv(out/'scene-metrics.csv',scene_rows)
    write_csv(out/'injection-events.csv',event_rows)
    if args.output_percent:
        baseline_by_scene = {r['scene_id']: float(r['baseline_D']) for r in scene_rows if r['status']=='baseline_estimable' and r.get('baseline_D') not in ('', None)}
        dose_percent_rows = []
        for r in dose_rows:
            d0 = baseline_by_scene.get(r['scene_id'])
            pct = (100.0 * float(r['delta_D']) / d0) if d0 not in (None, 0.0) and r['delta_D'] not in ('', None) else ''
            dose_percent_rows.append({**r, 'delta_D_percent': pct, 'baseline_D_for_percent': d0 if d0 is not None else ''})
        sequence_percent_rows = []
        percent_by_key = defaultdict(list)
        for r in dose_percent_rows:
            percent_by_key[(r['scene_id'], r['mode'], int(r['repeat']))].append(r)
        for old in sequence_rows:
            curve = sorted(percent_by_key[(old['scene_id'], old['mode'], int(old['repeat']))], key=lambda r:int(r['dose']))
            prefix = []
            for r in curve:
                if r['delta_D_percent'] in ('', None) or r['status'] != 'ok': break
                prefix.append((int(r['dose']), float(r['delta_D_percent'])))
            metrics = summarize_curve([x for x,_ in prefix], [y for _,y in prefix]) if len(prefix)>=2 else {'dose_avg_delta_D':None, 'theil_sen_D_per_event':None, 'positive_dose_points':None, 'negative_dose_points':None, 'zero_dose_points':None, 'support_k_max':0}
            sequence_percent_rows.append({'scene_id':old['scene_id'],'mode':old['mode'],'repeat':old['repeat'],'max_dose':old['max_dose'],'eligible_units':old['eligible_units'],'valid_prefix_doses':len(prefix),'valid_support_k_max':metrics['support_k_max'],'dose_avg_delta_D_percent':metrics['dose_avg_delta_D'] if metrics['dose_avg_delta_D'] is not None else '', 'theil_sen_percentage_points_per_event':metrics['theil_sen_D_per_event'] if metrics['theil_sen_D_per_event'] is not None else '', 'positive_dose_points':metrics['positive_dose_points'] if metrics['positive_dose_points'] is not None else '', 'negative_dose_points':metrics['negative_dose_points'] if metrics['negative_dose_points'] is not None else '', 'zero_dose_points':metrics['zero_dose_points'] if metrics['zero_dose_points'] is not None else ''})
        scene_by_id = {r['scene_id']:r for r in scene_rows}
        for mode in ('holding','vectoring'):
            grouped = defaultdict(list)
            for r in sequence_percent_rows:
                if r['mode']==mode and r['dose_avg_delta_D_percent']!='': grouped[r['scene_id']].append(r)
            for scene, rows in grouped.items():
                vals=[float(r['dose_avg_delta_D_percent']) for r in rows]
                slopes=[float(r['theil_sen_percentage_points_per_event']) for r in rows]
                sr=scene_by_id[scene]
                sr[mode+'_percent_area_median']=float(np.median(vals)); sr[mode+'_percent_area_q1']=float(np.quantile(vals,.25)); sr[mode+'_percent_area_q3']=float(np.quantile(vals,.75))
                sr[mode+'_percent_slope_median']=float(np.median(slopes)); sr[mode+'_percent_slope_q1']=float(np.quantile(slopes,.25)); sr[mode+'_percent_slope_q3']=float(np.quantile(slopes,.75))
                sr[mode+'_percent_direction_valid_repeats']=len(vals); sr[mode+'_percent_direction_positive']=sum(v>0 for v in vals); sr[mode+'_percent_direction_negative']=sum(v<0 for v in vals); sr[mode+'_percent_direction_zero']=sum(v==0 for v in vals)
        write_csv(out/'dose-repeat-percent-results.csv',dose_percent_rows)
        write_csv(out/'sequence-percent-metrics.csv',sequence_percent_rows)
        write_csv(out/'scene-percent-metrics.csv',scene_rows)
    snapshot=out/'runner-source.py'; snapshot.write_text(Path(__file__).read_text(encoding='utf-8'),encoding='utf-8')
    helper_path=Path(W.__file__).resolve(); helper_snapshot=out/'injection-helper-source.py'; helper_snapshot.write_text(helper_path.read_text(encoding='utf-8'),encoding='utf-8')
    input_hashes={p.name:sha(p) for p in paths}
    manifest={'state':'complete' if len(paths)==720 else 'smoke_test','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'scenes_processed':len(paths),'input_data_root':str(W.DATA),'input_files_sha256':input_hashes,'checkpoint':str(checkpoint),'checkpoint_sha256':checkpoint_sha,'preprocessor_id':enc.preprocess['preprocessor_id'],'complexity_config':cfg.__dict__,'pooling':'sum','repeats_per_dose':REPEATS,'seed_base':SEED,'baseline_d_cutoff':None,'metrics_scale':('absolute_delta_D_and_percent_change' if args.output_percent else 'absolute_delta_D_only'),'percent_formula':'100*(D_k-D_0)/D_0; denominator is the same scene baseline D0 for both modes','holding_policy':{'inherited_from':str(Path(W.__file__).resolve()),'sampling':'without_replacement','at_most_one_per_aircraft_per_repeat':True,'track_length_preserved':True,'duration_s':W.HOLDING_DURATION_S,'injected_points':36,'anchor_rule':'no minimum WSSS ARP distance'},'vectoring_policy':{'inherited_from':str(Path(W.__file__).resolve()),'window_s':600,'points':61,'peak_nearest_polyline_m':15000,'nonoverlapping_windows':True},'metric_definitions':{'paired_delta':'D_r(k)-D_r(0)','dose_avg_delta_D':'trapezoidal integral of sequence-specific Delta-D over contiguous valid dose prefix, divided by Kmax; units D','theil_sen_D_per_event':'Theil-Sen slope on sequence-specific Delta-D versus integer injected event dose; units D/event','percent_change':'100*(D_k-D_0)/D_0 using same-scene baseline D0','dose_avg_delta_D_percent':'trapezoidal integral of percentage change over contiguous valid dose prefix, divided by Kmax; units percent','theil_sen_percentage_points_per_event':'Theil-Sen slope on percentage change versus event dose; units percentage points/event','direction_counts':'Valid sequence-level average response signs; descriptive and uncalibrated, not detection probabilities','missing_policy':'Never impute failed D as zero; sequences without positive-dose support excluded from direction counts'},'runner_sha256':sha(snapshot),'imported_helper':str(helper_path),'imported_helper_sha256':sha(helper_path),'imported_helper_snapshot':'injection-helper-source.py','output_sha256':{}}
    for p in out.iterdir():
        if p.is_file() and p.name!='run-manifest.json': manifest['output_sha256'][p.name]=sha(p)
    (out/'run-manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'complete':manifest['state'],'scenes':len(paths),'dose_rows':len(dose_rows),'sequence_rows':len(sequence_rows),'scene_rows':len(scene_rows),'event_rows':len(event_rows),'output':str(out)}),flush=True)

if __name__=='__main__': main()
