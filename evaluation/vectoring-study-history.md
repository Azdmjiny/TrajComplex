# Vectoring study history and results

This report inventories existing evidence; no new experiment was run to write it. Screening, numerical repair, correlation evaluation and estimator diagnosis are different activities. They must not be counted as independent positive validation experiments. All counts are aircraft-hours unless stated otherwise. Orders within a scene are dependent repeats.

## Timeline and evidence

| Stage | What was done | Recorded result | What it establishes |
|---|---|---|---|
| Early evaluation, before the current quality/geometry repairs | Original synthetic offsets and earlier screening; archived QC500 and QC500-safe analyses | QC500 full-range median rho +0.848 (46 estimable orders); QC500-safe +0.832 (43 orders). Vectoring retained and full-range statistics are identical in this snapshot. | Historical positive associations exist, but do not validate the corrected intervention. Do not describe these Vectoring numbers as a new truncated experiment. [Saved summary](archive/legacy-before-workflow-integration/committed/results/summary.json). |
| Approved five-second rerun with stricter evidence and kinematic checks | Existing 12 scenes and old Encoder; fixed 5 km | 548 initial candidates, 31 after early evidence gates, 4 after local geometry checks, 0 after motion checks; no estimable correlation | Reject-only checks exposed unsupported/generated motion rather than confirming zero effect. [Stage report](archive/legacy-before-workflow-integration/local/reports/approved-rerun-comparison.md). |
| Horizontal position-time correction rerun | Same old Encoder and cosine-offset family; corrected source update support | 276 reach candidate screening, 11 reach geometry, 2 reach motion, 0 accepted | Timing artifacts were reduced, but evidence gaps and motion failures remained. This changed a declared whole-track policy as well as timing, so it is not an isolated causal timing experiment. [Stage report](archive/legacy-before-workflow-integration/local/reports/time-axis-rerun.md). |
| Continuous generator and numerical arithmetic repair | Continuous reference plus constrained chord-normal detours; stable derivatives and analytic Jacobians | The archived local root summary still has no estimable Vectoring correlations. Numerical regression checks were not a new positive dose experiment. | Solver arithmetic can be repaired without claiming that every reference or route is feasible. [Method record](archive/legacy-before-workflow-integration/local/reports/vectoring-continuous-generator.md), [saved summary](archive/legacy-before-workflow-integration/local/results/summary.json). |
| Strict-ten-second Encoder/input reference run | Existing twelve scenes rerun with the frozen ten-second Encoder | No estimable Vectoring correlations in any saved QC variant | Matching training/input cadence alone did not establish a usable dose relationship. [Historical reference](runs/strict-10s-reference/report.md), [summary](runs/strict-10s-reference/results/summary.json). |
| Background/candidate separation and whole-track fitting | Basic-QC background retained; stronger evidence gates apply to fit/injection candidates | 384 background, 264 length-qualified, 15 quality-complete fits, 9 reference passes, 2 candidates accepted on both sides | Preserves scene membership while distinguishing fit eligibility from injection eligibility. Screening only. [Stage report](archive/legacy-before-workflow-integration/local/reports/vectoring-population-screening.md). |
| Continuous peak feedback repair | Feed off-grid peak witnesses back into the unchanged solver budget | All 7 previously peak-rejected candidates pass; total 2 → 9; background and fitted baselines unchanged | Fixes sampled-peak/continuous-peak mismatch for these candidates. No new correlations. [Stage report](archive/legacy-before-workflow-integration/local/reports/vectoring-peak-feedback.md). |
| Direction-certificate calculation repair | Separate local-heading evidence from chord progress; improve the conditional uncertainty bound | Reference passes 9 → 10; both-side injectable 9 → 10. Candidate 8a04ce passes all checks | One recoverable calculation-related rejection resolved; other rejection reasons retained. No generator change or correlation rerun. [Stage report](archive/legacy-before-workflow-integration/local/reports/vectoring-direction-repair.md). |
| Four additional fixed scenes: evidence, fitting and route screening | Same airport/month, fixed scenes chosen for evidence/sample support before correlation; 26 candidates | 157 background, 26 fits, 21 both-side injectable: 4, 6, 6, 5. Four reference/chord-progress failures and one route-solver rejection | Enough possible doses for the existing correlation rule, not a guarantee of valid D. All 26 pass local-direction certification. [Screening report](runs/four-scene-vectoring-screen/report.md). |
| Four-scene full-range correlation evaluation | Frozen accepted arrays, strict ten-second Encoder, same processed baseline and injection references; all orders/doses retained | First three scenes: 0/95 accepted D attempts combined. Fourth: 30/30; three positive and two negative correlations | Corrected accepted routes do not produce a stable positive association. [Full report](runs/four-scene-vectoring-evaluation/report.md). |
| Diagnosis of the existing full-range results | Read stored fits, pair counts, scales and aircraft/side sequences | Baseline R² failures in first three scenes; fourth-scene steps cross fitting-scale eligibility boundaries | Identifies mechanisms, but does not isolate sample size from distribution or side from order. No new experimental arm. [Diagnosis](runs/vectoring-existing-result-diagnosis/report.md). |
| Fixed-baseline-scale diagnostic, fourth scene only | Reuse saved embeddings and original assignments; require every baseline scale to remain valid | 26/30 D attempts accepted; 4 rejected. Order 4 changes +0.771 → −0.319 with all doses retained | Scale selection affects the conclusion; fixing scales does not recover stable positive correlation. This is a diagnostic, not a replacement primary estimator. [Detailed report](runs/vectoring-fixed-baseline-scales/report.md). |
| 15 km segmented injection, R²≥0.94, no STAR (2026-10-25) | Same 19 candidates; original 9-feature Encoder; trapezoid 150/300/150 s with 30 s corner blend; smooth 15 km control | Segmented 13/15 positive, median rho 0.829, 3/3 scenes positive; smooth 9/15, 0.600, 1/3 | Shape matters: segmented vectoring is easier for sum-pooled embeddings to see. Schematic stimulus, not a C2-certified maneuver; no STAR. [Run package](runs/segmented-15km/README.md). |

The older committed snapshot and local snapshot are separately preserved because they contain different stages. Their before/after statistics are not a controlled comparison: Encoder, reference treatment, candidate populations and generation methods changed across stages. The archive inventory records exact file provenance. Missing stage-specific artifacts must not be reconstructed from conversational counts or silently treated as equivalent runs.

## Current full-range evaluation

| Scene start UTC (UTC+08) | Background | Injectable | Accepted / attempted D | Baseline R² |
|---|---:|---:|---:|---:|
| 2026-09-14T06Z (2026-09-14 14:00) | 38 | 4 | 0 / 25 | 0.97533 |
| 2026-09-15T07Z (2026-09-15 15:00) | 47 | 6 | 0 / 35 | 0.96632 |
| 2026-09-19T07Z (2026-09-19 15:00) | 40 | 6 | 0 / 35 | 0.95023 |
| 2026-09-27T05Z (2026-09-27 13:00) | 32 | 5 | 30 / 30 | 0.98836 |

Attempt counts repeat the shared baseline across orders; they are not independent observations. The first three scenes fail the existing R² >= 0.98 gate even before injection. Their aircraft counts (38, 47, 40) exceed the fourth scene's 32, so a simple “more aircraft always fixes it” explanation is unsupported. Finite-sample effects may still contribute; these records cannot quantify them separately from the embedding distribution.

## Fourth scene: original and fixed-scale results

| Order | Original rho | Fixed-scale rho | Accepted fixed-scale doses |
|---|---:|---:|---:|
| 1 | +0.577 | +0.577 | 6/6 |
| 2 | -0.406 | +0.051 | 5/6 |
| 3 | +0.754 | +0.754 | 6/6 |
| 4 | +0.771 | -0.319 | 6/6 |
| 5 | -0.829 | Unavailable | 3/6 |

- Order 4 retains every dose, so its sign change identifies fitting-scale sensitivity rather than loss of doses.
- Order 2 loses one dose. The original estimator on the same five retained doses also gives +0.051; that sign change must not be credited to scale fixing alone.
- Order 5 has only three valid doses and remains unestimable under the unchanged five-dose minimum.
- All four fixed-scale rejections have nine pairs at the smallest baseline scale: C(r)=9/496, below both the ten-pair and 0.02 bounds. Missing D is never filled or recoded as zero.
- In the original curves, aircraft 750579 is Right in both negative orders and Left in all three positive orders. Aircraft, direction, order and scale eligibility co-vary; this is an observation, not an isolated causal side experiment.

## What happened to the original three concerns?

1. **Undefined directions causing an offset to disappear:** accepted candidates require a continuous direction certificate. Missing or unreliable directions are rejected; no zero-vector fallback or invented neighboring direction is used.
2. **Inner-normal displacement collapsing a curved route into a cusp:** the current generator searches continuous chord-normal detours instead of moving each point along its changing local normal. Both sides must pass reference, spatial-projection, joining and continuous-peak acceptance. This addresses the original construction failure for accepted routes, not a claim that every candidate can be made feasible.
3. **A maximum-speed-only screen missing other pathological motion:** accepted routes must also pass the existing speed-retention, longitudinal/lateral acceleration, turning and continuous joining checks. The fixed 5 km spatial-distance target is independently checked between sample times. Failures and unresolved checks reject the candidate.

These are conditional engineering guarantees under the adopted reference and uncertainty model. NACp-derived engineering disks are not deterministic truth bounds; fitted between-observation motion is not directly observed; ground-motion proxies are not aircraft-specific flight certification. Solver failure is not proof that every possible maneuver is infeasible. The current tests do not establish universal flight realism.

## Paper implications

The current Vectoring evidence can be reported as a transparent negative/inconclusive validation result and an estimator-sensitivity study. It documents rejection-only input validation, preserved baselines, complete unsuccessful results and sensitivity to scale eligibility. It cannot support stable strong positive Vectoring correlation or complete validation of operational complexity. The old positive numbers must not replace the corrected results merely because they are larger.

No left/right swap experiment, sample-size sweep, alternative-estimator experiment or outcome-selected Vectoring cutoff was added to the current four-scene run. Holding's equal-duration control is separate and does not validate Vectoring. More data might improve estimability but cannot be promised to produce positive correlation.

See the [current combined report](report.md), [published evidence index](runs/README.md) and [historical archive inventory](archive/legacy-before-workflow-integration/inventory.json).
