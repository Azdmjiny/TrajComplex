# Screening the four approved additional Vectoring scenes

> Archived stage report. Statements about work not yet run describe this stage only. See the [current combined report](../../../report/report.md) for subsequent results. Publication excludes raw trajectories and model weights; see the [bundle notes](../../../histry/publication-records/runs-index.md).

Date: 2026-10-24. Scope: the same four September scenes and 26 candidates whose complete NACp/NIC evidence was verified. No additional data, candidates, dates or experimental arms were introduced. Holding equal-duration control remains on hold.

## Result

| Local scene start (UTC+08) | Fixed basic-QC background | Quality-complete candidates | Accepted full-track fits | All reference gates passed | Both sides injectable | Maximum distinct doses including zero |
|---|---:|---:|---:|---:|---:|---:|
| 2026-09-14 14:00 +08:00 | 38 | 7 | 7 | 4 | 4 | 5 |
| 2026-09-15 15:00 +08:00 | 47 | 7 | 7 | 7 | 6 | 7 |
| 2026-09-19 15:00 +08:00 | 40 | 6 | 6 | 6 | 6 | 7 |
| 2026-09-27 13:00 +08:00 | 32 | 6 | 6 | 5 | 5 | 6 |

Total: **21 of 26 candidates are injectable on both sides**. The fixed scene populations contain 157 background members in total, including approved candidates. Rejections by first failed stage: {'reference': 4, 'generated_route': 1}.

All **26 of 26** candidates pass the continuous local-direction certificate. The four reference rejections are independent chord-progress failures: three have nonpositive projection witnesses, while `888170` cannot certify positive progress under the existing uncertainty bound (no nonpositive point was witnessed). They are not mislabeled as local-heading uncertainty.

The remaining candidate, `750596`, fails route solving on both sides: the left reaches the unchanged 100-iteration ceiling, and the right reports a positive directional derivative during line search. Both trial results retain longitudinal-acceleration constraint violations. Neither trial is accepted; no budget or limit was changed. This does not prove that every possible route is infeasible.

At least four injectable candidates are necessary to offer five distinct injection counts including zero under the existing correlation rule. These are possible counts, not valid D estimates: no Encoder, D, or correlation was run. Candidates cannot be pooled across hours to manufacture more doses within an hourly scene.

## Candidate-level decisions

| Scene UTC | Aircraft | Fit accepted | Local direction | All reference gates | Left route | Right route | Injectable | Reasons |
|---|---|---|---|---|---|---|---|---|
| 2026-09-14T06Z | 750424 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-14T06Z | 750447 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-14T06Z | 750480 | True | continuous_certificate_pass | False | not_run | not_run | False | reference_chord_progress_nonpositive |
| 2026-09-14T06Z | 75049d | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-14T06Z | 885110 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-14T06Z | 894098 | True | continuous_certificate_pass | False | not_run | not_run | False | reference_chord_progress_nonpositive |
| 2026-09-14T06Z | a03423 | True | continuous_certificate_pass | False | not_run | not_run | False | reference_chord_progress_nonpositive |
| 2026-09-15T07Z | 06a117 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-15T07Z | 750425 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-15T07Z | 7504c3 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-15T07Z | 75057a | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-15T07Z | 750596 | True | continuous_certificate_pass | True | no_validated_path_solver_failed | no_validated_path_solver_failed | False | no_validated_path_solver_failed |
| 2026-09-15T07Z | 7822bc | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-15T07Z | 8a0ab8 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-19T07Z | 750260 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-19T07Z | 750424 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-19T07Z | 750449 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-19T07Z | 7504c3 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-19T07Z | 750555 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-19T07Z | 8a0a67 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-27T05Z | 75033c | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-27T05Z | 750562 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-27T05Z | 750563 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-27T05Z | 750579 | True | continuous_certificate_pass | True | passed | passed | True | None |
| 2026-09-27T05Z | 888170 | True | continuous_certificate_pass | False | not_run | not_run | False | reference_chord_progress_uncertified |
| 2026-09-27T05Z | 8a0a84 | True | continuous_certificate_pass | True | passed | passed | True | None |

Each distinct rejection reason is counted once per candidate; different reasons may overlap. All-reference pass requires local direction, the unchanged independent chord-progress gate and finite curvature bounds. A direction failure is distinct from chord-progress rejection. Solver failure does not establish that every possible maneuver is infeasible.

## Unchanged method

The identical verified production modules were imported from `vectoring-direction-repair/code`, with hashes matching the preceding screening. The full-track natural-quintic, NACp-constrained minimum-jerk fit, adaptive raw-velocity-disk local-direction certificate, chord-normal degree-eight route family, fixed 5,000 m continuous spatial peak and 600-second maneuver duration are unchanged. Strict 10-second grids and barometric height are preserved.

All quality, geometry, motion and numerical limits are identical to the previous manifest, including the 10-degree direction cone, 500 m/s speed ceiling, 50% speed retention, 2 m/s² longitudinal acceleration, 35-degree lateral bank proxy, 0.03 m peak tolerance, existing solver budgets and verification ceilings. Rejection never shrinks the offset, changes the window, fills data, or relaxes a limit. Both sides must pass.

Background/candidate separation is retained. Every existing basic-QC track remains a scene member. Only the authorized 26 candidates enter fitting. Failed fits retain raw backgrounds; successful fits define fixed paired baselines before later acceptance gates. A subsequent route rejection does not switch the fitted baseline back. Accepted injections preserve baseline altitude and all samples outside the maneuver.

## Verification and preserved outputs

All 157 original background arrays were independently reconstructed from their cached source observations with the unchanged grid and alignment functions. 131 unfitted backgrounds match the originals bit for bit; 26 fitted backgrounds exactly reproduce their saved source-knot splines. Every accepted left/right pair was reread and checked for peak/motion certificates, unchanged altitude/outside samples, and the existing sampled kinematic gate. Source hashes, runtime versions and production code hashes match the frozen manifest.

The local driver adds only scoped input loading, output writing, and a passive fitted-knot recorder; it delegates every fit and acceptance decision to unchanged production functions. No software fix or parameter tuning was performed in this run. Prior source data, evidence, old screening, historical correlation results, and Holding work are untouched.

`screening/manifest.json` records code/source hashes and thresholds. `screening/*-records.json` retains every candidate/background decision and solver diagnostic; `screening/*-population.npz` stores paired fixed baselines and accepted routes; `screening/*-original-background.npz` preserves pre-fit arrays; `screening/references/` stores fitted source knots for diagnosis without rerunning fits. `comparison.json` and `verification.json` provide candidate-level results and integrity checks.

These results are conditional on the existing natural-spline and NACp engineering-disk assumptions and ground-motion proxies. Passing screening is not evidence of positive correlation or aircraft-specific flight certification.
