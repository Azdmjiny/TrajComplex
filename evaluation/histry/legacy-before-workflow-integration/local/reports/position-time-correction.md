# Horizontal position-time correction — 2026-10-22

Implementation change only. Existing evaluation outputs have not been rerun or overwritten. They describe the previous snapshot-time preprocessing and must not be presented as results of this correction.

- Interpolate horizontal positions using their existing `lastposupdate` values, not snapshot `time`.
- Use that same clock for horizontal speed QC, vectoring source brackets and local direction/curvature query times. Remove the former snapshot-to-update time warp.
- Retain the original snapshot-anchored five-second grid only within common observation support. Unsupported trailing samples are omitted rather than extrapolated; tracks below the existing length requirements are rejected. This may shift the midpoint slightly and change eligibility; no replacement scenes or duration changes are introduced.
- Reject invalid/missing/nonadvancing update times, repeated horizontal positions, stale observations and excessive gaps. The shared reader now applies the already approved 15-second age and 20-second gap rules to its full input track, because every resampled baseline point needs valid timing. Previously vectoring applied such checks only around the intervention. This deliberately changes baseline admission and must be reported in a future rerun.
- Preserve original source rows and source indices for exact quality-message lookup; no sorting by update time, deduplication of nonadvancing updates, quality filling or direction imputation is introduced.
- Keep vertical ENU coordinate interpolation and vertical speed QC on snapshot time. Horizontal and vertical message provenance differ; this change does not certify synchronized 3D observations.
- Keep the 5,000 m peak, existing vectoring construction and all motion/uncertainty thresholds unchanged. New generator decisions remain pending.

Both holding and vectoring use the shared reader. Their next approved evaluation must rebuild consistent baselines and explicitly identify the preprocessing change. No effect on correlation or eligible counts has been measured in this implementation task. The earlier 548 -> 0 result remains historical.

## Validation

Regression checks cover constant physical velocity with variable snapshot age, update-time interpolation brackets, rejection of invalid/repeated updates, no endpoint extrapolation, altitude timing preservation, separate horizontal/vertical QC clocks, fixed 5 km amplitude, and the previous geometry guards. These are software regression checks, not added evaluation experiments.

## Pending generator choices

1. Define 5 km as maximum spatial cross-track distance from the reference route, or retain the old corresponding-time normal-offset meaning. Recommended: spatial cross-track distance, explicitly acknowledged as a method change.
2. Permit a continuously fitted reference using only existing valid observations, or retain the conservative five-point model. No missing observations or unreliable directions may be inferred in either case. Model-error allowances require separate justification.
3. Require the same ten-minute window and matching endpoint position/speed/direction. Recommended: keep them and reject if no validated solution is found; never silently extend time or reduce offset.
4. Permit a declared smoothness objective for choosing among feasible paths. Recommended: a smoothness-based objective independent of D/correlation; its exact representation, error tolerance and numerical verification rules must be presented before implementation, without invented values.

No new experiments, threshold sweeps, aircraft replacement, retraining, or GitHub push are part of this change.
