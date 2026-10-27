# Vectoring numerical certificate repair and screening

> Publication note: this package contains reports, figures and execution-source snapshots only. Population arrays, embeddings, per-dose JSON, assignments, quality evidence and manifests remain local. Statements about “no Git push” describe the original experiment run; this reviewed presentation was subsequently published. No experiment was rerun for publication.

Date: 2026-10-27. Status: screening completed; no correlation rerun and no publication-result replacement.

## Outcome

The 20-second quality-matching arm increases from **25 to 26 eligible candidates**. All 25 previously eligible candidates remain eligible. The restored aircraft is **3c6709**, which has quality evidence for the 20-second arm only. The 15-second arm remains **22**, and the original 10-second arm remains **19**.

| Scene (UTC) | 10 s before → after | 15 s before → after | 20 s before → after |
|---|---:|---:|---:|
| 2026-09-14T06Z | 3 → 3 | 5 → 5 | 6 → 6 |
| 2026-09-15T07Z | 6 → 6 | 6 → 6 | 6 → 7 |
| 2026-09-19T07Z | 5 → 5 | 5 → 5 | 6 → 6 |
| 2026-09-27T05Z | 5 → 5 | 6 → 6 | 7 → 7 |

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
| 3c6709 | Passed | Passed | Restored |
| 8a09f8 | no_validated_path_solver_failed | continuous_motion_feedback_stalled | Rejected |
| 76d1c6 | continuous_motion_feedback_stalled | Passed | Rejected |

For **3c6709**, the original left route still has a nearest-reference branch conflict. It was **not relabelled as valid**. One conflict witness was fed back, producing a changed route with the same offset target. The new route passed continuous peak, motion, projection and joining checks. Left-side solver use: 17 of 100 iterations. Continuous peak bounds: 14999.996250 to 15000.008641 m.

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

- Final records (local-only: `screening-final/summary.json`)
- Run manifest and protected-source hashes (local-only: `screening-final/manifest.json`)
- Validation and per-window counts (local-only: `verification.json`)
- [Screening driver](source/screen_saved.py)
- [Frozen implementation](../../code/vectoring_path.py)
- [Frozen numerical certificates](../../code/vectoring_certification.py)

Reproduction requires the retained local frozen references and populations. Use a new output directory; the screening driver refuses to overwrite one. No data download or model inference is needed.
