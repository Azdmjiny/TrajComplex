# Local direction certificate repair and screening

Completed: 2026-10-24. Same 12 original September scenes and source hashes. Strict 10-second inputs, fixed 5 km target, all existing physical/quality/numerical thresholds, and the route generator are unchanged. This is screening only; no Encoder, D, or correlation was run.

## Result

`8a04ce` (2026-09-20T04Z): reference pass = **True**; both sides injectable = **True**. Remaining reasons: [].

| Stage | Before | After |
|---|---:|---:|
| Fixed baseline population | 384 | 384 |
| Full-track fits | 15 | 15 |
| All reference gates passed | 9 | 10 |
| Both sides injectable | 9 | 10 |
| Background only | 375 | 374 |

## Target: checks on both sides

| Side | Accepted | Continuous peak enclosure (m) | Solver budget used | Remaining reason |
|---|---|---|---:|---|
| Left | True | [4999.996250000002, 5000.006455090122] | 12 | None |
| Right | True | [4999.996250000002, 5000.003797290242] | 13 | None |

Acceptance requires the unchanged continuous motion, spatial projection, endpoint position/velocity/acceleration/heading, and sampled kinematic checks, in addition to the continuous peak enclosure. Passing the direction check alone is never enough.

## Six former direction rejections

| Scene (UTC) | Aircraft | Local direction | Chord progress | Injectable | Remaining reasons |
|---|---|---|---|---|---|
| 2026-09-07T10Z | 75054e | point_witness_failure | rejected | False | continuous_reference_direction_unreliable, reference_chord_progress_nonpositive |
| 2026-09-07T10Z | 8851e4 | continuous_certificate_pass | rejected | False | reference_chord_progress_nonpositive |
| 2026-09-10T06Z | 750333 | continuous_certificate_pass | rejected | False | reference_chord_progress_nonpositive |
| 2026-09-12T15Z | 750421 | point_witness_failure | rejected | False | continuous_reference_direction_unreliable, reference_chord_progress_nonpositive |
| 2026-09-20T04Z | 8a04ce | continuous_certificate_pass | passed | True | None |
| 2026-09-25T23Z | acb588 | point_witness_failure | rejected | False | continuous_reference_direction_unreliable, reference_chord_progress_nonpositive |

Reasons are counted once per aircraft-hour per distinct reason. They can overlap; the counts must not be added to infer unique rejected aircraft. The three direction failures also have a chord-progress failure.

## Implementation

The adopted natural-spline observation disks give an exact raw-centered velocity disk at each time: center `W'(t) y`, radius `sum |W'_i(t)| epsilon_i`. The local fitted velocity defines the unchanged 10-degree cone. Both cone half-spaces are bounded over whole polynomial intervals using Bernstein products, retaining dependence between raw and fitted velocities. Intervals whose bounds are inconclusive are subdivided under the existing 100,000-node verification ceiling shared across the full maneuver and both joining intervals. A point witness outside the cone rejects; exhausted budget or floating-point/nonfinite ambiguity rejects as unresolved. No disk shrinkage, missing-value fill, changed fit, or new generator is used.

The former recentered derivative-error bound and `forward > error` chord-progress rule remain unchanged as an independent gate. Existing curvature bounds are also retained. A nonpositive chord projection now receives its own reason, rather than being mislabeled as unknown local heading or infinite physical curvature. If no nonpositive point is witnessed but the forward bound cannot certify progress, the reason is `reference_chord_progress_uncertified`.

Rejection labels: `continuous_reference_direction_unreliable` means a concrete local-cone failure witness; `continuous_reference_direction_unresolved` means a numerical certificate was not established; `reference_chord_progress_nonpositive` identifies a nonpositive projection witness; `reference_chord_progress_uncertified` identifies unresolved forward certainty; `reference_curvature_bound_unresolved` identifies a nonfinite curvature bound. A curvature bound blocked by chord failure is diagnostic context, not a duplicate rejection count.

The fit method stays unchanged. Only the direction certificate provenance changes to `raw-velocity-disk-local-cone-adaptive-v1`. The old chord-based angle bound remains available explicitly as `legacy_chord_angle_bound_deg`; it is not reported as the new local-angle estimate.

## Per-scene counts

| Scene (UTC) | Fixed baseline | Fits | Reference passes | Injectable |
|---|---:|---:|---:|---:|
| 2026-09-01T01Z | 32 | 0 | 0 | 0 |
| 2026-09-04T08Z | 40 | 0 | 0 | 0 |
| 2026-09-07T10Z | 29 | 3 | 1 | 1 |
| 2026-09-10T06Z | 36 | 2 | 1 | 1 |
| 2026-09-12T15Z | 26 | 1 | 0 | 0 |
| 2026-09-15T06Z | 46 | 1 | 1 | 1 |
| 2026-09-18T00Z | 31 | 0 | 0 | 0 |
| 2026-09-20T04Z | 33 | 2 | 2 | 2 |
| 2026-09-23T10Z | 25 | 0 | 0 | 0 |
| 2026-09-25T23Z | 31 | 3 | 2 | 2 |
| 2026-09-28T07Z | 34 | 2 | 2 | 2 |
| 2026-09-30T15Z | 21 | 1 | 1 | 1 |

## Verification and limits

44 relevant regression tests passed, including exact disk recentering, off-grid failure, adaptive interval proof, refusal on budget exhaustion, join support, and independent rejection of reverse chord progress. All 384 saved baselines and all nine previously accepted pairs match the prior run bit for bit. All old screening files and original inputs remain unchanged. The generator source, fit model, source hashes, and physical/quality/numerical threshold dictionaries were verified unchanged.

The maximum number of injectable candidates in any one scene is 2. This remains insufficient for the existing five-valid-dose correlation rule. No positive correlation or paper validation is established by this repair. Direction guarantees remain conditional on the adopted natural-spline and NACp engineering-disk assumptions; they are not simultaneous statistical confidence guarantees or aircraft-specific flight certification.

The [previous peak-feedback report](vectoring-peak-feedback.md) and all older results are preserved. [Machine-readable comparison](../results/vectoring-direction-repair.json) contains the target certificates and manifests. Full per-aircraft records and NPZ populations are retained locally in `deliverables/vectoring-direction-repair/screening/`. No Git commit or push was performed.
