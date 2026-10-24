# Vectoring population screening — 2026-10-24

This is a candidate-screening result, not a correlation evaluation. The original 12 scenes, strict 10-second cadence, barometric altitude, fixed 5 km target and existing thresholds are unchanged. All counts below are aircraft-hours, not distinct aircraft across the month.

## Results

| Stage | Aircraft-hours |
| --- | ---: |
| Fixed basic-QC scene population | 384 |
| Length supports maneuver and both joins | 264 |
| Full-track quality-evidenced fit candidates | 15 |
| Accepted full-track fits | 15 |
| Reliable continuous maneuver reference | 9 |
| Both sides accepted for injection | 2 |
| Background only | 382 |
| Background only: original processing | 369 |
| Background only: successfully fitted | 13 |

The 15 fits are a subset of the 384 scene members, not additional aircraft. Two of those fits are injectable; the other 13 remain fitted backgrounds. Missing candidate metadata no longer deletes otherwise basic-QC background aircraft.

Previously, the full-track-evidence requirement applied to every baseline member and left 27 tracks across these scenes. The revised policy retains all 384 basic-QC members. Eight of the 12 scenes have at least 30 baseline tracks. Neither this count nor a successful fit establishes D estimability.

Earlier candidate summaries counted tracks with at least 61 samples. The generator already required 63 to include both joins. Applying that existing requirement at the initial length gate changes 275 preliminary candidates to 264; quality-complete preliminary candidates change from 16 to 15. The excluded quality-complete case is 7505a4 at 2026-09-28T07Z, with 62 samples. This is an accounting correction, not a new duration threshold.

## Per-scene counts

| Scene start (UTC) | Fixed population | Fits accepted | Reference accepted | Injectable | Background only |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-09-01T01Z | 32 | 0 | 0 | 0 | 32 |
| 2026-09-04T08Z | 40 | 0 | 0 | 0 | 40 |
| 2026-09-07T10Z | 29 | 3 | 1 | 0 | 29 |
| 2026-09-10T06Z | 36 | 2 | 1 | 0 | 36 |
| 2026-09-12T15Z | 26 | 1 | 0 | 0 | 26 |
| 2026-09-15T06Z | 46 | 1 | 1 | 0 | 46 |
| 2026-09-18T00Z | 31 | 0 | 0 | 0 | 31 |
| 2026-09-20T04Z | 33 | 2 | 1 | 1 | 32 |
| 2026-09-23T10Z | 25 | 0 | 0 | 0 | 25 |
| 2026-09-25T23Z | 31 | 3 | 2 | 0 | 31 |
| 2026-09-28T07Z | 34 | 2 | 2 | 1 | 33 |
| 2026-09-30T15Z | 21 | 1 | 1 | 0 | 21 |

## Accepted candidates

| Scene (UTC) | Aircraft | Left continuous peak enclosure (m) | Right continuous peak enclosure (m) |
| --- | --- | --- | --- |
| 2026-09-20T04Z | 75043e | 4999.996221–5000.005013 | 4999.995351–5000.004305 |
| 2026-09-28T07Z | 750423 | 4999.996100–5000.005431 | 4999.996052–5000.004650 |

These are 2026-09-20 12:00 and 2026-09-28 15:00 in UTC+8. Both sides also passed continuous motion/projection and sampled joining checks. Altitude and outside-maneuver samples are identical to their frozen fitted baseline.

## Remaining rejections

- Six accepted fits failed the conditional direction-reliability check; five also lacked a finite forward-based curvature envelope. The sets overlap. These tracks stay fitted backgrounds. Smoothness did not replace their uncertainty evidence.
- Nine references reached the unchanged route search. All 18 side-specific solver attempts reported success, but independent continuous checks rejected nine sides belonging to seven aircraft-hours for the fixed-5 km peak acceptance condition. Nine individual sides passed; only two aircraft-hours passed both sides. No one-sided candidate was admitted.
- The seven rejected candidates have not been proved globally infeasible. A sampled solver target can meet its equality while the continuous maximum fails the much tighter spatial acceptance condition. These failures were not relabeled as bad source data or repaired by reducing offset/loosening tolerances. Later motion checks are not claimed to have passed when peak acceptance rejected first.

Each scene has at most one injectable aircraft. With only zero and one injection, the current five-valid-dose correlation requirement is not met. This screening does not establish positive or negative Vectoring correlation. Holding results and all previous evaluation outputs remain unchanged.

## Implementation and verification

See [population and fitting policy](vectoring-population-policy.md). The independent strict-10-second entrypoint is `code/screen_vectoring_candidates.py`. Historical correlation/holding entrypoints are not migrated or executed. Future correlation work must use these paired baseline/injection arrays together.

52 relevant software regression tests passed, covering raw/fitted background fallback, fixed dose membership, full-track evidence, numerical fitting, no zero-direction substitution, cusp/collapse rejection, continuous motion, fixed distance, time handling and deduplicated rejection counts. Stored NPZ populations were independently reread and checked against the original QC500 reader, preserved heights, frozen outside samples, accepted-side certificates and input/code hashes.

The initial redundant nullspace solve was corrected to the mathematically equivalent zero-jerk-first formulation before final screening. Preliminary implementation outputs are retained locally for traceability and are not the final counts. No physical threshold, NACp radius, observation or experimental condition was changed.

Machine-readable totals: [screening summary](../results/vectoring-population-screening.json). Full local artifacts: `deliverables/vectoring-population-screen/final-screening/` (manifest, records, QC audit and frozen population arrays). Old results and checkpoints are preserved; no Encoder, D or correlation was run.
