"""Summarize screening only and verify preserved inputs; no D/Encoder imports."""
from pathlib import Path
import json,hashlib,sys,shutil
R=Path(__file__).resolve().parent;B=R.parent;OUT=R/'screening-final'
OLD=B/'vectoring-time-window-sensitivity-2026-10-27';CODE=B/'changi-publication-repo/evaluation/code'
sys.dont_write_bytecode=True;sys.path.insert(0,str(B/'evaluation-python-deps'))
import numpy as np
read=lambda p:json.loads(p.read_text(encoding='utf8'))
write=lambda p,v:p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(OUT/'manifest.json');records=read(OUT/'summary.json')['records']
assert m['state']=='complete' and m['code_unchanged']
assert all(sha(Path(p))==h for p,h in m['protected_sources'].items())
assert all(sha(CODE/p)==h for p,h in m['code_sha256'].items())
assert len(records)==40
assert sum(r['old_paired_injectable'] for r in records)==25
assert all(r['paired_injectable'] for r in records if r['old_paired_injectable'])
recovered=[r for r in records if r['paired_injectable'] and not r['old_paired_injectable']]
assert [r['icao24'] for r in recovered]==['3c6709']
comparison=[]
for window in [10,15,20]:
    for sid in sorted({r['scene'] for r in records}):
        rows=[r for r in records if r['scene']==sid and (r['origin']=='original_10s' or r['quality_windows'][str(window)]['full_quality_pass'])]
        comparison.append(dict(window_s=window,scene=sid,before=sum(r['old_paired_injectable'] for r in rows),after=sum(r['paired_injectable'] for r in rows)))
old_new_array_checks=[]
for r in records:
    if not r['old_paired_injectable']:continue
    sid,a=r['scene'],r['icao24']
    if r['origin']=='original_10s':
        source=B/'vectoring-15km-star-2026-10-24/population-15km'/(sid+'-population.npz')
        with np.load(source) as z:old_arrays={name:z[a+'_'+name] for name in ['left','right']}
    else:
        source=OLD/'screening'/(sid+'-'+a+'-arrays.npz')
        with np.load(source) as z:old_arrays={name:z['smooth_'+name] for name in ['left','right']}
    with np.load(OUT/(sid+'-'+a+'-routes.npz')) as z:
        for name,q in old_arrays.items():
            start=(len(q)-60)//2
            error=float(np.max(np.abs(z['15000_'+name]-q[start:start+61,:2])))
            old_new_array_checks.append(dict(scene=sid,icao24=a,side=name,maximum_absolute_coordinate_difference_m=error))
snapshot=R/'code-snapshot';snapshot.mkdir(exist_ok=True)
for name,h in m['code_sha256'].items():
    dest=snapshot/name
    if dest.exists():assert sha(dest)==h
    else:shutil.copy2(CODE/name,dest)
validation=dict(old_results_unchanged=True,protected_file_count=len(m['protected_sources']),frozen_reference_files_unchanged=True,
    old_accepted_retained=25,newly_accepted=1,accepted_after=26,reference_rejections_unchanged=9,
    geometry_chord_rejections_unchanged=8,comparison=comparison,
    existing_route_coordinate_comparisons=old_new_array_checks,
    software_regressions_passed=24,new_encoder_calls=0,new_D_calls=0,new_reference_fits=0,
    output_sample_s=10,screening_stages_m=[5000,15000],source_script_sha256=sha(R/'screen_saved.py'))
write(R/'verification.json',validation)
# Make the aborted first development attempt explicit; it is not a result arm.
p=R/'priority-3c6709/manifest.json'
if p.exists():
    partial=read(p)
    if partial['state']=='running':
        partial.update(state='interrupted_development_attempt',included_in_final_counts=False)
        write(p,partial)
table=[]
for sid in sorted({r['scene'] for r in records}):
    values={w:next(t for t in comparison if t['window_s']==w and t['scene']==sid) for w in [10,15,20]}
    table.append(f"| {sid} | {values[10]['before']} → {values[10]['after']} | {values[15]['before']} → {values[15]['after']} | {values[20]['before']} → {values[20]['after']} |")
focus=[]
for a in ['3c6709','8a09f8','76d1c6']:
    r=next(t for t in records if t['icao24']==a)
    legs=r['stages']['15000']
    focus.append('| '+a+' | '+' | '.join('Passed' if legs[s]['accepted'] else legs[s]['rejection_reason'] for s in ['left','right'])+' | '+('Restored' if r['paired_injectable'] else 'Rejected')+' |')
detail=next(r for r in records if r['icao24']=='3c6709')['stages']['15000']['left']
assert detail['accepted'] and len(detail['failure_feedback'])==1
text='''# Vectoring numerical certificate repair and screening

Date: 2026-10-27. Status: screening completed; no correlation rerun and no publication-result replacement.

## Outcome

The 20-second quality-matching arm increases from **25 to 26 eligible candidates**. All 25 previously eligible candidates remain eligible. The restored aircraft is **3c6709**, which has quality evidence for the 20-second arm only. The 15-second arm remains **22**, and the original 10-second arm remains **19**.

| Scene (UTC) | 10 s before → after | 15 s before → after | 20 s before → after |
|---|---:|---:|---:|
'''+ '\n'.join(table)+'''

The four scenes are September 14 at 14:00, September 15 at 15:00, September 19 at 15:00, and September 27 at 13:00 in Singapore local time. Matching windows in seconds are unrelated to route distance in kilometres. The existing pipeline's 5 km prerequisite and 15 km route stage were both retained, with 10-second route output.

## Implementation

- Velocity and acceleration polynomial controls are differentiated before subdivision and carried through refinement. They are no longer reconstructed by dividing tiny rounded position differences by tiny time intervals.
- The projection certificate preserves the dependence of position, tangent and acceleration on the **same reference parameter** using exact Bernstein products. This tightens an overly conservative envelope; the required positive distance curvature, unique nearest projection, forward progress, side and endpoint rules are unchanged.
- Reference intervals are refined as well as query intervals. Computational-budget exhaustion and floating-point resolution failure are distinct from witnessed geometry conflicts. Unresolved cases remain rejected.
- A nearest-reference branch conflict returns its query time, competing reference times and a negative-curvature witness. Motion violations return their actual time and margin. These witnesses are fed back to the same three-control degree-eight route solver, followed by complete continuous verification. Total SLSQP budget remains 100 iterations per side, shared across restarts.
- The projection solver aid enforces the existing sufficient convex-projection condition at the witness. It can be conservative and is not a proof that no other feasible route exists. No arbitrary nearest branch is selected to bypass a conflict.

Unchanged: fitted references and baselines, candidate quality evidence, eight chord-geometry rejections, route family, fixed offset targets, 600-second duration, 500 m/s maximum horizontal speed, 0.5 minimum speed ratio, 2.0 m/s² longitudinal cap, 35° lateral bank proxy, join tolerances, continuous acceptance criteria, and existing work caps. No missing observations were filled.

## Priority cases

| Aircraft | 15 km left | 15 km right | Candidate outcome |
|---|---|---|---|
'''+ '\n'.join(focus)+f'''

For **3c6709**, the original left route still has a nearest-reference branch conflict. It was **not relabelled as valid**. One conflict witness was fed back, producing a changed route with the same offset target. The new route passed continuous peak, motion, projection and joining checks. Left-side solver use: {detail['solver_budget_used']} of 100 iterations. Continuous peak bounds: {detail['continuous_peak_distance_bounds_m'][0]:.6f} to {detail['continuous_peak_distance_bounds_m'][1]:.6f} m.

For **76d1c6**, the formerly projection-failing right side now passes after feedback. The left side still fails the motion certificate, so the aircraft remains rejected. For **8a09f8**, the left-side solver fails after feedback and the right-side motion feedback stalls. Neither is counted as recovered.

## Remaining rejections and limits

Of 40 candidate identities reviewed, 9 retain their reference rejection (8 chord-geometry, 1 direction reliability), 26 pass, and 5 fail route screening:

- `06a110`: both sides fail the 5 km prerequisite solver.
- `8a09f8`: 15 km left solver failure and right motion-feedback stall.
- `7817ff`: 15 km left motion-feedback stall.
- `75052a`: 15 km right motion-feedback stall.
- `76d1c6`: 15 km left motion-feedback stall.

Some final motion violations are very close to the boundary. A solver's stopping tolerance does not override the physical acceptance limit, and a witness already present in the solver constraints can still fail the independent continuous check. Such cases are explicitly labelled feedback-stalled and remain rejected. This does not establish global infeasibility. The eight chord-geometry cases were not regenerated using another method or a different window.

This repair improves candidate eligibility and error interpretation. It says nothing new about the sign or strength of D correlation. No Encoder, D or correlation was computed.

## Validation and retained evidence

Twenty-four software regression tests passed, including analytic Jacobians, tiny-interval derivative stability, true nearest-branch conflicts, continuous off-grid motion failures, tighter convexity envelopes, work-cap rejection, fixed-distance joins and shared feedback budgets. All 25 previously accepted candidates were screened again, and all remain accepted. Their route coordinate differences are recorded, rather than assumed to be zero.

Saved screening/reference/population files were protected by SHA-256 comparisons. New records, accepted route segments, solver histories, failure witnesses and a source-code snapshot are stored separately. `screening-final/` is the only final screening run. `priority-*` and `debug-*` are development diagnostics, not extra experimental arms or result-selection opportunities.

Local reproducibility files:

- [Final records](screening-final/summary.json)
- [Run manifest and protected-source hashes](screening-final/manifest.json)
- [Validation and per-window counts](verification.json)
- [Screening driver](screen_saved.py)
- [Frozen implementation](code-snapshot/vectoring_path.py)
- [Frozen numerical certificates](code-snapshot/vectoring_certification.py)

Reproduction requires the retained local frozen references and populations. Use a new output directory; the screening driver refuses to overwrite one. No data download or model inference is needed.
'''
(R/'report.md').write_text(text,encoding='utf8')
print(json.dumps(dict(comparison=comparison,restored=[r['icao24'] for r in recovered],protected_files=len(m['protected_sources']),max_existing_coordinate_difference_m=max(x['maximum_absolute_coordinate_difference_m'] for x in old_new_array_checks)),indent=2))
