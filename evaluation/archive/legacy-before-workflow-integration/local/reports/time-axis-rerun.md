# Evaluation rerun after horizontal time-axis correction

The existing 12-hour, five-order evaluation was rerun with the original frozen Encoder and unchanged 5,000 m cosine-offset generator. No continuous-fit generator, new threshold, new scene, control experiment or parameter sweep was introduced. Existing aircraft-count sensitivity settings were rerun as part of the existing suite.

**No vectoring candidates passed. This does not establish zero effect or a negative correlation: all vectoring curves contain baseline only, so the correlation remains unestimable.**

## Candidate accounting

| Stage | Candidates |
| --- | --- |
| Previous aircraft-hour candidates | 548 |
| Rejected by full-track nonadvancing update times | 240 |
| Rejected by full-track update gaps over 20 s | 27 |
| Too short after unsupported endpoint removal | 5 |
| Reach current vectoring screen | 276 |
| Rejected by quality metadata coverage/consistency | 265 |
| Reach geometry model | 11 |
| Rejected by quadratic-model disk consistency | 9 |
| Reach deformed-motion screen | 2 |
| Rejected by longitudinal acceleration | 2 |
| Accepted | 0 |

These are mutually exclusive sequential losses. The raw reader now checks the whole input track, not only the intervention interval. Therefore this is a rerun of the implemented time-axis correction plus its declared full-track reject-only policy; it is not an isolated causal experiment on interpolation alone.

The following reasons overlap and must not be added together:

| Reason | Aircraft-hour candidates |
| --- | --- |
| status_bracket_over_10_s | 216 |
| missing_quality_match | 124 |
| status_missing_unknown_or_conflicting | 60 |
| quadratic_model_inconsistent_with_error_disks | 9 |
| longitudinal_acceleration_over_2_m_s2 | 2 |
| position_quality_unknown | 1 |

The 124 missing-quality cases each need one source index outside the existing point-match file. Changing time support shifted interpolation brackets; this is missing audit coverage, not proof that OpenSky has no corresponding quality message. No missing value was filled and no new download/matching was performed. The previous 88510f and 8a04ce candidates now need source indices 70 and 73 respectively and stop at this quality gate; their corrected kinematics were not evaluated in this rerun.

## What happened to the previous four final-stage candidates?

All acceleration values below are maximum absolute longitudinal acceleration in m/s² over the checked interval.

| Aircraft | Old baseline | Corrected baseline | Negative offset | Positive offset |
| --- | --- | --- | --- | --- |
| 896218 | 16.984 | 1.656 | 5.443 | 5.368 |
| 88510f | 35.495 | not evaluated | not evaluated | not evaluated |
| 8a04ce | 10.481 | not evaluated | not evaluated | not evaluated |
| 750543 | 9.317 | 2.001 | 2.014 | 2.005 |

- **896218:** corrected baseline maximum is 1.656, below the existing 2 m/s² limit, while the two generated versions reach 5.443 and 5.368. The current displacement produces a longitudinal failure on a baseline that passes this particular check. This supports a remaining generator problem, but does not isolate whether the local fit switches, offset envelope or their interaction is responsible.
- **750543:** corrected baseline is already 2.001260, slightly above 2. The generated maxima are 2.013840 and 2.005004. No numerical allowance was added. This is a borderline baseline/method case, not clear evidence that the injection alone caused rejection. Its original largest artifact fell substantially, but the full candidate still fails the frozen rule.
- **88510f / 8a04ce:** stopped at missing quality coverage. Their lack of motion diagnostics is not a pass or failure of corrected motion.
- Neither final candidate has a recorded curvature-boundary or speed-collapse first failure in this run. Sequential first-failure logging does not prove every later condition passes.

## Baselines and Holding

Primary baseline aircraft-hour total changed from 761 to 441. Baseline-estimable hours changed from 6 to 4. This changes both trajectories and sample composition.

| Run | Scope | Full curves | Median full rho | Retained curves | Median retained rho | Positive retained |
| --- | --- | --- | --- | --- | --- | --- |
| Before | all | 60 | -0.110 | 50 | 0.913 | 50/50 |
| Before | baseline_ok | 30 | 0.191 | 30 | 0.928 | 30/30 |
| After | all | 45 | 0.122 | 40 | 0.857 | 36/40 |
| After | baseline_ok | 20 | 0.099 | 20 | 0.840 | 19/20 |

The five orders are repeats within an hour, not independent hours. Pre-peak correlations remain exploratory because the same outcomes choose the peak. The length/sum-pooling confound remains. Differences between runs cannot be assigned solely to the generator because preprocessing and baseline membership changed. Vectoring remains unestimable in all four variants.

## Per-hour primary baseline and eligibility

| Hour | Aircraft | Eligible vectoring | Baseline D status |
| --- | --- | --- | --- |
| 2026-09-01T01Z | 37 | 0 | unestimable |
| 2026-09-04T08Z | 48 | 0 | unestimable |
| 2026-09-07T10Z | 32 | 0 | unestimable |
| 2026-09-10T06Z | 40 | 0 | ok |
| 2026-09-12T15Z | 28 | 0 | unestimable |
| 2026-09-15T06Z | 53 | 0 | ok |
| 2026-09-18T00Z | 39 | 0 | unestimable |
| 2026-09-20T04Z | 37 | 0 | ok |
| 2026-09-23T10Z | 29 | 0 | unestimable |
| 2026-09-25T23Z | 35 | 0 | ok |
| 2026-09-28T07Z | 39 | 0 | unestimable |
| 2026-09-30T15Z | 24 | 0 | unestimable |

## Reproducibility and preserved results

Core inference/geometry code hashes match the run manifest; the quality-input hash and frozen checkpoint match the previous run. Reporting-only code was updated after inference to remove obsolete hardcoded counts; the report manifest records the current report generator. No inference method was changed during this rerun.

Full backup: `C:\Users\HP\Documents\ChatGPT\UVA World Model\deliverables\evaluation-before-time-axis-rerun`. The backup contains the previous results and the corrected source as it stood immediately before this rerun; the prior source snapshot is also retained in the earlier local backups.

Local `comparison.json` contains exact counts, source-index gaps and verification fields. The existing repository results and figures now describe this rerun. The historical key `legacy_replay` in aircraft-count output now means no horizontal speed QC on the corrected reader; it is NOT a reconstruction of the old snapshot-time input.

Remaining work, not performed here: complete exact quality matching for the newly required source rows, investigate residual generated-motion failures, and implement a separately approved generator if desired. No threshold relaxation or new generator was used to obtain a passing sample.
