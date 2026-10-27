# Continuous peak feedback repair and screening

Completed: 2026-10-24. Screening only, on the same original 12 September scenes. No Encoder, geometric-dimension calculation, dose curve, correlation, new scene selection or threshold change. Counts are aircraft-hours, not distinct aircraft across the month.

## Result

Of the seven candidates previously rejected by continuous peak acceptance, **7 now pass both sides**. The total injectable count changes from **2 to 9**. All 384 fixed baseline trajectories are bitwise identical to the prior screening, including all 15 fitted tracks. The original two accepted candidates and their injection arrays are also unchanged.

| Stage | Before | After |
| --- | ---: | ---: |
| Fixed baseline population | 384 | 384 |
| Length-qualified candidates | 264 | 264 |
| Full quality evidence | 15 | 15 |
| Accepted full-track fits | 15 | 15 |
| Reliable continuous reference | 9 | 9 |
| Both sides injectable | 2 | 9 |
| Background only | 382 | 375 |

## The seven previously rejected candidates

| Scene start (UTC) | Aircraft | Both sides pass | Added feedback rounds, left / right | Total SLSQP iterations, left / right |
| --- | --- | --- | --- | --- |
| 2026-09-07T10Z | 7c384f | Yes | 1 / 0 | 7 / 11 |
| 2026-09-10T06Z | 750453 | Yes | 1 / 0 | 8 / 9 |
| 2026-09-15T06Z | 88510f | Yes | 1 / 1 | 13 / 11 |
| 2026-09-25T23Z | 75052a | Yes | 1 / 1 | 15 / 9 |
| 2026-09-25T23Z | 80168c | Yes | 0 / 1 | 14 / 10 |
| 2026-09-28T07Z | 750543 | Yes | 0 / 1 | 12 / 14 |
| 2026-09-30T15Z | 8a095b | Yes | 1 / 0 | 13 / 9 |

## Per-scene population

| Scene start (UTC) | Fixed baseline | Fits | Reference passes | Injectable before | Injectable after |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-09-01T01Z | 32 | 0 | 0 | 0 | 0 |
| 2026-09-04T08Z | 40 | 0 | 0 | 0 | 0 |
| 2026-09-07T10Z | 29 | 3 | 1 | 0 | 1 |
| 2026-09-10T06Z | 36 | 2 | 1 | 0 | 1 |
| 2026-09-12T15Z | 26 | 1 | 0 | 0 | 0 |
| 2026-09-15T06Z | 46 | 1 | 1 | 0 | 1 |
| 2026-09-18T00Z | 31 | 0 | 0 | 0 | 0 |
| 2026-09-20T04Z | 33 | 2 | 1 | 1 | 1 |
| 2026-09-23T10Z | 25 | 0 | 0 | 0 | 0 |
| 2026-09-25T23Z | 31 | 3 | 2 | 0 | 2 |
| 2026-09-28T07Z | 34 | 2 | 2 | 1 | 2 |
| 2026-09-30T15Z | 21 | 1 | 1 | 0 | 1 |

## What changed

The solver starts with the unchanged five-second collocation points and reference knots. After each successful solve, the existing continuous verifier encloses the maximum spatial distance. If the enclosure is outside the unchanged acceptance band, its off-grid witness time is added to both peak and sampled-motion constraints. The next solve starts from the previous controls. The objective normalization, three-control degree-eight route family, fitted reference, 600-second duration, initial solve and 5,000 m target are unchanged.

Every updated route receives a fresh continuous peak check. A changed route is not accepted using an old witness. Once the full enclosure lies in 4,999.97–5,000.03 m, the unchanged continuous motion/projection, endpoint and sampled-motion checks still have to pass. Both sides remain mandatory.

The 100-iteration SLSQP limit is shared across all solves for one side. A zero-iteration solver return consumes one budget unit to prevent unbounded restarts. The 100,000 peak-subdivision budget is also shared across feedback rounds; no restart resets it. Existing separate reference-cover, motion and projection verification ceilings remain unchanged. Solver failure, an unresolved check, budget exhaustion or a repeated unusable witness rejects the candidate.

Observed maximums per side: 15 SLSQP budget units, 1 added feedback rounds, and 76 peak subdivisions. No extra iteration or refinement allowance was used.

The numerical implementation is recorded as `direct-offset-derivatives/adaptive-continuous-peak-feedback-v3`. Failed and successful states retain sampled peak errors, continuous enclosures, witness times, control values, per-round counts and final rejection reasons. The Encoder output cadence stays strictly 10 seconds; adaptive internal solver times are not new Encoder samples.

## Remaining limits

6 fitted candidates still fail the unchanged direction-reliability gate and remain fitted backgrounds. Missing quality evidence and insufficient maneuver/connection support still exclude other tracks from injection, without removing their basic-QC backgrounds.

The largest per-scene injectable count is 2. Consequently these scenes still do not supply the existing minimum of five dose levels (including zero) required for a correlation. Candidates from different hours cannot be pooled into one hourly scene to bypass that requirement. This repair establishes successful geometric/kinematic screening under the conditional model; it does not establish positive correlation, general aircraft flyability, or complete certainty about recorded positions.

## Verification and preservation

58 relevant software regression tests passed. New regressions reproduce an off-grid peak, verify feedback and warm starts, enforce shared budgets, preserve both output cadences, and ensure solver failure or final motion rejection cannot be bypassed. Stored population arrays and certificates were independently reread. All baseline arrays match the prior run bit for bit; source hashes, fitted-reference method, route family and all threshold dictionaries match.

The previous [background/candidate screening](vectoring-population-screening.md), historical correlation outputs, Holding files and local artifacts are preserved. This report and its [machine-readable comparison](../results/vectoring-peak-feedback.json) are new screening artifacts. No Git commit or push is performed by this repair.

Full local evidence is under `deliverables/vectoring-peak-feedback/screening/`: input/code manifest, per-aircraft records, refinement histories and baseline/injection NPZ arrays. The historical correlation entrypoint remains unrun; future authorized analysis must consume the paired baseline/injection arrays together.
