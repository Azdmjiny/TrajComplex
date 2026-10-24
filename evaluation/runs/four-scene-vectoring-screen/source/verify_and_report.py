"""Verify saved population invariants and summarize without rerunning solvers."""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json,sys
R=Path(__file__).resolve().parent;B=R.parent;S=R/'screening'
CODE=B/'vectoring-direction-repair/code'
sys.dont_write_bytecode=True
sys.path[:0]=[str(B/'evaluation-python-deps'),str(CODE)]
import numpy as np
from vectoring_population import array_hash,summarize
from vectoring_inputs import llh_to_enu
from position_timeline import position_grid,resample_positions
from run_vectoring_eval import _check_deformed_kinematics
import vectoring_path as path
from scipy.interpolate import make_interp_spline

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,d):(R/name).write_text(json.dumps(d,indent=2,allow_nan=False),encoding='utf8')
m=read(S/'manifest.json');old=read(B/'vectoring-direction-repair/screening/manifest.json')
summary=read(S/'summary.json')
assert m['state']==summary['state']=='complete'
for k in ['code_sha256','fit_model','direction_certificate','route_model','route_numerics','thresholds','numerical','versions']:
    assert m[k]==old[k],k
assert all(sha(CODE/n)==v for n,v in m['code_sha256'].items())
assert all(sha(m['source_paths'][k])==v for k,v in m['source_sha256'].items())
assert sha(R/'run_screen.py')==m['driver_sha256']
assert not m['forbidden_imports']
approved={(r['scene'],r['icao24']) for r in m['approved_candidates']}
rows=[];accepted=[];background_count=0;unchanged_raw=0;saved_fits=0
for scene in m['scenes']:
    source=B/'opensky-month-coverage/source-tracks'/(scene+'.json.gz')
    assert sha(source)==m['source_track_sha256'][scene]
    with gzip.open(source,'rt',encoding='utf8') as f:raw={r['icao24']:np.asarray(r['source_records']) for r in json.load(f)}
    records=read(S/(scene+'-records.json'));expected=set()
    with np.load(S/(scene+'-population.npz')) as pop,np.load(S/(scene+'-original-background.npz')) as original:
        assert set(original.files)==set(raw)=={r['icao24'] for r in records}
        for r in records:
            a=r['icao24'];p=pop[a+'_baseline'];expected.add(a+'_baseline');background_count+=1
            grid=position_grid(raw[a],sample_s=10)
            enu=llh_to_enu(raw[a][:,1],raw[a][:,2],raw[a][:,3])
            np.testing.assert_array_equal(original[a],resample_positions(raw[a],enu,grid))
            assert array_hash(original[a])==r['original_sha256']
            assert array_hash(p)==r['baseline_sha256'] and array_hash(grid)==r['grid_sha256']
            np.testing.assert_array_equal(p[:,2],original[a][:,2])
            assert r['fit_attempted']==((scene,a) in approved)
            if not r['fit_success']:
                np.testing.assert_array_equal(p,original[a]);unchanged_raw+=1
            else:
                with np.load(S/'references'/(scene+'-'+a+'.npz')) as f:
                    zero=np.zeros(len(f['times']))
                    mapping=make_interp_spline(f['times'],np.eye(len(zero)),k=5,
                         bc_type=([(3,zero),(4,zero)],[(3,zero),(4,zero)]))
                    xy=mapping(grid-f['epoch'])@f['fitted_xy']+f['origin']
                    np.testing.assert_array_equal(p[:,:2],xy)
                    assert np.all(np.linalg.norm(f['fitted_xy']-f['raw_xy'],axis=1)<=f['radii'])
                    saved_fits+=1
            if r['reference_pass']:
                d=r['reference_diagnostics']
                assert d['direction_certificate']['status']=='continuous_certificate_pass'
                assert d['direction_certificate']['nodes']<=path.MAX_VERIFY_NODES
                assert d['chord_progress']['status']=='passed' and d['curvature_status']=='bounded'
            for side,d in r['side_diagnostics'].items():
                if 'solver_budget_used' in d:assert d['solver_budget_used']<=path.SOLVER_MAXITER
                if 'peak_verification_work' in d:assert d['peak_verification_work']['used']<=path.MAX_VERIFY_NODES
            if r['injectable']:
                assert r['reference_pass'] and r['fit_success']
                start=(len(p)-60)//2;end=start+61
                detail={}
                for side,label in [('-1','left'),('1','right')]:
                    key=a+'_'+label;expected.add(key);q=pop[key];d=r['side_diagnostics'][side]
                    assert d['accepted'] and d['solver_success']
                    lo,hi=d['continuous_peak_distance_bounds_m']
                    assert path.PEAK-path.POSITION_TOL<=lo<=hi<=path.PEAK+path.POSITION_TOL
                    assert min(d['continuous_motion']['conservative_margins'])>=0
                    assert d['projection_intervals']>0
                    np.testing.assert_array_equal(q[:,2],p[:,2])
                    np.testing.assert_array_equal(q[:start],p[:start]);np.testing.assert_array_equal(q[end:],p[end:])
                    _check_deformed_kinematics(p[start-1:end+1],q[start-1:end+1],sample_s=10)
                    detail[label]=dict(continuous_peak_bounds_m=[lo,hi],solver_budget_used=d['solver_budget_used'],
                                      continuous_motion_margins=d['continuous_motion']['conservative_margins'])
                accepted.append(dict(scene=scene,icao24=a,sides=detail))
        assert set(pop.files)==expected
    rows.extend(records)
assert background_count==157 and sum(r['fit_attempted'] for r in rows)==26
assert summarize(rows)==summary['totals']
assert { (r['scene'],r['icao24']) for r in rows if r['fit_attempted']}==approved
protected=read(R/'before-hashes.json');assert all(sha(p)==h for p,h in protected.items())
candidates=[r for r in rows if r['in_approved_candidate_scope']]
rejected=[r for r in candidates if not r['injectable']]
def stage(r):
    return 'fit_or_fitted_background_QC' if not r['fit_success'] else 'reference' if not r['reference_pass'] else 'generated_route'
counts=dict(Counter(stage(r) for r in rejected))
local_direction_pass=sum(r.get('reference_diagnostics',{}).get('direction_certificate',{}).get('status')=='continuous_certificate_pass' for r in candidates)
verification=dict(all_passed=True,production_code_and_thresholds_unchanged=True,approved_candidates_only=True,
    fixed_background_members=157,unfitted_backgrounds_bitwise_equal=unchanged_raw,
    fitted_backgrounds_reconstructed_exactly=saved_fits,accepted_pairs_verified=len(accepted),
    all_source_and_quality_files_unchanged=True,protected_files=len(protected),old_results_unchanged=True,
    encoder_calls=0,D_calls=0,correlation_calls=0,holding_runs=0)
write('verification.json',verification)
write('comparison.json',dict(summary=summary,local_direction_pass=local_direction_pass,rejection_stage_counts=counts,
    candidate_rejection_counts=dict(Counter(reason for r in rejected for reason in set(r['rejection_reasons']))),
    accepted=accepted,approved_candidate_records=candidates,verification=verification))
lines=['# Screening the four approved additional Vectoring scenes','',
'Date: 2026-10-24. Scope: the same four September scenes and 26 candidates whose complete NACp/NIC evidence was verified. No additional data, candidates, dates or experimental arms were introduced. Holding equal-duration control remains on hold.','',
'## Result','',
'| Local scene start (UTC+08) | Fixed basic-QC background | Quality-complete candidates | Accepted full-track fits | All reference gates passed | Both sides injectable | Maximum distinct doses including zero |','|---|---:|---:|---:|---:|---:|---:|']
for s in summary['scenes']:
    lines.append(f"| {s['local_time']} | {s['basic_retained']} | {s['full_quality_candidates']} | {s['fit_success']} | {s['reference_pass']} | {s['injectable']} | {s['injectable']+1} |")
t=summary['totals']
lines+=['',f"Total: **{t['injectable']} of 26 candidates are injectable on both sides**. The fixed scene populations contain 157 background members in total, including approved candidates. Rejections by first failed stage: {counts}.",'',
f"All **{local_direction_pass} of 26** candidates pass the continuous local-direction certificate. The four reference rejections are independent chord-progress failures: three have nonpositive projection witnesses, while `888170` cannot certify positive progress under the existing uncertainty bound (no nonpositive point was witnessed). They are not mislabeled as local-heading uncertainty.",'',
'The remaining candidate, `750596`, fails route solving on both sides: the left reaches the unchanged 100-iteration ceiling, and the right reports a positive directional derivative during line search. Both trial results retain longitudinal-acceleration constraint violations. Neither trial is accepted; no budget or limit was changed. This does not prove that every possible route is infeasible.','',
'At least four injectable candidates are necessary to offer five distinct injection counts including zero under the existing correlation rule. These are possible counts, not valid D estimates: no Encoder, D, or correlation was run. Candidates cannot be pooled across hours to manufacture more doses within an hourly scene.','',
'## Candidate-level decisions','',
'| Scene UTC | Aircraft | Fit accepted | Local direction | All reference gates | Left route | Right route | Injectable | Reasons |','|---|---|---|---|---|---|---|---|---|']
for r in candidates:
    direction=r.get('reference_diagnostics',{}).get('direction_certificate',{}).get('status','not_run')
    sides=[('passed' if r['side_diagnostics'][side]['accepted'] else r['side_diagnostics'][side].get('rejection_reason','rejected')) if side in r['side_diagnostics'] else 'not_run' for side in ['-1','1']]
    lines.append(f"| {r['scene']} | {r['icao24']} | {r['fit_success']} | {direction} | {r['reference_pass']} | {sides[0]} | {sides[1]} | {r['injectable']} | {', '.join(r['rejection_reasons']) or 'None'} |")
lines+=['','Each distinct rejection reason is counted once per candidate; different reasons may overlap. All-reference pass requires local direction, the unchanged independent chord-progress gate and finite curvature bounds. A direction failure is distinct from chord-progress rejection. Solver failure does not establish that every possible maneuver is infeasible.','',
'## Unchanged method','',
'The identical verified production modules were imported from `vectoring-direction-repair/code`, with hashes matching the preceding screening. The full-track natural-quintic, NACp-constrained minimum-jerk fit, adaptive raw-velocity-disk local-direction certificate, chord-normal degree-eight route family, fixed 5,000 m continuous spatial peak and 600-second maneuver duration are unchanged. Strict 10-second grids and barometric height are preserved.','',
'All quality, geometry, motion and numerical limits are identical to the previous manifest, including the 10-degree direction cone, 500 m/s speed ceiling, 50% speed retention, 2 m/s² longitudinal acceleration, 35-degree lateral bank proxy, 0.03 m peak tolerance, existing solver budgets and verification ceilings. Rejection never shrinks the offset, changes the window, fills data, or relaxes a limit. Both sides must pass.','',
'Background/candidate separation is retained. Every existing basic-QC track remains a scene member. Only the authorized 26 candidates enter fitting. Failed fits retain raw backgrounds; successful fits define fixed paired baselines before later acceptance gates. A subsequent route rejection does not switch the fitted baseline back. Accepted injections preserve baseline altitude and all samples outside the maneuver.','',
'## Verification and preserved outputs','',
f"All 157 original background arrays were independently reconstructed from their cached source observations with the unchanged grid and alignment functions. {unchanged_raw} unfitted backgrounds match the originals bit for bit; {saved_fits} fitted backgrounds exactly reproduce their saved source-knot splines. Every accepted left/right pair was reread and checked for peak/motion certificates, unchanged altitude/outside samples, and the existing sampled kinematic gate. Source hashes, runtime versions and production code hashes match the frozen manifest.",'',
'The local driver adds only scoped input loading, output writing, and a passive fitted-knot recorder; it delegates every fit and acceptance decision to unchanged production functions. No software fix or parameter tuning was performed in this run. Prior source data, evidence, old screening, historical correlation results, and Holding work are untouched.','',
'`screening/manifest.json` records code/source hashes and thresholds. `screening/*-records.json` retains every candidate/background decision and solver diagnostic; `screening/*-population.npz` stores paired fixed baselines and accepted routes; `screening/*-original-background.npz` preserves pre-fit arrays; `screening/references/` stores fitted source knots for diagnosis without rerunning fits. `comparison.json` and `verification.json` provide candidate-level results and integrity checks.','',
'These results are conditional on the existing natural-spline and NACp engineering-disk assumptions and ground-motion proxies. Passing screening is not evidence of positive correlation or aircraft-specific flight certification.','']
(R/'report.md').write_text('\n'.join(lines),encoding='utf8')
print(json.dumps(dict(verification=verification,rejection_stages=counts,
    scenes=[{k:s[k] for k in ['scene','approved_candidates','fit_success','reference_pass','injectable']} for s in summary['scenes']]),indent=2))
