# Holding / Vectoring evaluation after geometry repair and screening

Updated: 2026-10-19. This report replaces the former `evaluation-pilot.md`. Current results, figures, and reproduction code remain in `results/`, `figures/`, and `code/`. Git history retains earlier committed versions without separate dated directories. Complete dose curves remain available; truncation only determines which points enter the correlation calculation.

**Interpretation: the retained pre-peak Holding segment is strongly positively correlated, but its peak is selected from the same outcomes. This is a post hoc, exploratory local association, not independent validation, evidence that the declining segment is invalid, or proof that the algorithm has exceeded its operating range.** The full range still rises and then falls. Vectoring is not truncated, and its positive correlation remains after cleaning. Five random orders are within-hour repeats, not five independent hours; no confirmatory p-values are reported.

## Implemented fixes

- The second Holding turn no longer applies an extra initial heading rotation. Natural geometric closure is checked before pinning the endpoint to remove floating-point drift, avoiding the previous large jump.
- In addition to missing/nonfinite values, ground records, length, and time-gap screening, raw trajectories are checked for latitude/longitude bounds, altitude from −500 to 20000 m, horizontal speed, and absolute vertical speed ≤100 m/s. The entire aircraft-hour is rejected rather than interpolating away an anomalous jump. Primary horizontal speed is ≤500 m/s, with ≤350 m/s for strict sensitivity screening. These are diagnostic thresholds, not a validated flight envelope.
- Vectoring candidates must pass a ≤500 m/s speed screen for both left and right offsets. Failed candidates remain in the eligible baseline point cloud but are not injected. `safe` is only a run label and does not guarantee full physical feasibility. Changing coordinates changes speed; the maneuver cannot be described as preserving original speed.
- Correlation requires `status=ok`, finite D, and at least five valid points. Denominators reflect the actual number of computable curves. The final estimability bin includes the 100% dose, and subsample sizes exceeding the available aircraft count are skipped.
- Manual replacement of report numbers has been replaced by a unified data-generation workflow to prevent stale numbers from overwriting the report.

## Experimental conditions

The original 12 hours and five random injection orders per hour are fixed; cleaning does not replace scenes. Original aircraft order and Vectoring side are generated before excluding ineligible aircraft, preserving surviving aircraft order and side. Primary screening retains 761/771 aircraft-hour trajectories; strict screening retains 652/771.

The same frozen Encoder, sum pooling, and unnormalized Euclidean distances are used. Each scene has 64 fixed candidate radii derived from its baseline. Estimator gates are unchanged: at least 30 points, at least 8 fitted scales, a radius span of at least 2-fold, correlation-integral bounds 0.02–0.3, and R²≥0.98.

Holding adds 48 five-second samples per aircraft; length remains confounded with sum pooling. Neither an equal-length control nor a diversified Holding control has established the cause of the decline. Those unadopted controls are not included in the conclusions.

## Holding truncation rule

The five random orders within each hour share one cutoff. Compute mean valid D at each dose; only doses with at least three valid repeats can select the peak. Choose the earliest global maximum of mean D. Retain the peak and all preceding doses, without smoothing or selecting peaks separately for each curve. Local pre-peak declines remain; this does not remove every negative-slope segment.

## Holding: all available curves

| Screening | Sample scope | Full-range curves | Full-range median ρ | Retained curves | Retained-range median ρ | Retained positive correlations |
| --- | --- | --- | --- | --- | --- | --- |
| qc500 | All scenes | 60 | -0.110 | 50 | 0.913 | 50/50 |
| qc500 | Baseline-estimable only | 30 | 0.191 | 30 | 0.928 | 30/30 |
| qc350 | All scenes | 57 | -0.099 | 53 | 0.868 | 52/53 |
| qc350 | Baseline-estimable only | 35 | -0.176 | 35 | 0.863 | 34/35 |

All 50 retained QC500 curves are positive; 10 of the original 60 have too few valid points in the retained segment to compute correlation. QC350 has 52 positive curves out of 53. These denominator changes must not be ignored.

## Paired comparison of the same curves

| Screening | Sample scope | Curves computable in both ranges | Full-range median ρ | Retained-range median ρ |
| --- | --- | --- | --- | --- |
| qc500 | All scenes | 50 | 0.073 | 0.913 |
| qc500 | Baseline-estimable only | 30 | 0.191 | 0.928 |
| qc350 | All scenes | 53 | -0.067 | 0.868 |
| qc350 | Baseline-estimable only | 35 | -0.176 | 0.863 |

Under primary screening, all 30 curves from the six baseline-estimable hours remain. Median ρ rises from 0.191 to 0.928. The curve count is unchanged in this comparison, but peak-selection bias remains. Taking the median across repeats within each hour, QC500 has 11 computable retained-range hours, all positive, with an across-hour median of 0.904. QC350 also has 11 computable hours, with a median of 0.877.

## Per-hour cutoffs

| Screening | Hour (UTC) | Cutoff aircraft / scene aircraft | Curves: full → retained | Full-range hourly ρ | Retained-range hourly ρ |
| --- | --- | --- | --- | --- | --- |
| qc500 | 2026-09-01T01Z | 31/56 (55.4%) | 5 → 5 | 0.428 | 0.970 |
| qc500 | 2026-09-04T08Z | 42/73 (57.5%) | 5 → 5 | 0.370 | 0.970 |
| qc500 | 2026-09-07T10Z | 30/62 (48.4%) | 5 → 1 | -0.898 | 0.950 |
| qc500 | 2026-09-10T06Z | 28/71 (39.4%) | 5 → 5 | -0.735 | 0.844 |
| qc500 | 2026-09-12T15Z | 26/51 (51.0%) | 5 → 4 | -0.380 | 0.904 |
| qc500 | 2026-09-15T06Z | 36/87 (41.4%) | 5 → 5 | -0.366 | 0.877 |
| qc500 | 2026-09-18T00Z | 33/63 (52.4%) | 5 → 5 | -0.242 | 0.867 |
| qc500 | 2026-09-20T04Z | 36/67 (53.7%) | 5 → 5 | 0.234 | 0.937 |
| qc500 | 2026-09-23T10Z | 29/59 (49.2%) | 5 → 5 | 0.183 | 0.899 |
| qc500 | 2026-09-25T23Z | 30/51 (58.8%) | 5 → 5 | 0.094 | 0.752 |
| qc500 | 2026-09-28T07Z | 34/71 (47.9%) | 5 → 5 | 0.041 | 0.952 |
| qc500 | 2026-09-30T15Z | 24/50 (48.0%) | 5 → 0 | -0.950 | Not estimable |
| qc350 | 2026-09-01T01Z | 35/51 (68.6%) | 5 → 5 | 0.692 | 0.840 |
| qc350 | 2026-09-04T08Z | 41/62 (66.1%) | 5 → 5 | 0.361 | 0.851 |
| qc350 | 2026-09-07T10Z | 26/55 (47.3%) | 5 → 3 | -0.528 | 0.888 |
| qc350 | 2026-09-10T06Z | 25/63 (39.7%) | 5 → 5 | -0.427 | 0.886 |
| qc350 | 2026-09-12T15Z | 25/45 (55.6%) | 5 → 5 | -0.032 | 0.930 |
| qc350 | 2026-09-15T06Z | 32/78 (41.0%) | 5 → 5 | -0.300 | 0.877 |
| qc350 | 2026-09-18T00Z | 30/54 (55.6%) | 5 → 5 | -0.161 | 0.860 |
| qc350 | 2026-09-20T04Z | 31/55 (56.4%) | 5 → 5 | 0.216 | 0.943 |
| qc350 | 2026-09-23T10Z | 20/44 (45.5%) | 5 → 5 | -0.275 | 0.812 |
| qc350 | 2026-09-25T23Z | 17/42 (40.5%) | 5 → 5 | -0.184 | 0.713 |
| qc350 | 2026-09-28T07Z | 27/62 (43.5%) | 5 → 5 | -0.223 | 0.939 |
| qc350 | 2026-09-30T15Z | No eligible peak | 2 → 0 | -0.976 | Not estimable |

QC500 cutoff fractions range from approximately 39% to 59%; the rule does not uniformly remove doses above 50%. For QC350 on 2026-09-30T15Z, no dose has three valid repeats, so no peak is forced. QC500 has an eligible peak for that hour, but each retained curve still has fewer than five valid points and cannot produce a correlation.

## Vectoring: full range without truncation

| Screening | Computable curves | Median ρ | Positive curves |
| --- | --- | --- | --- |
| qc500 | 46 | 0.848 | 42/46 |
| qc350 | 45 | 0.807 | 39/45 |
| qc500_safe | 43 | 0.832 | 38/43 |
| qc350_safe | 40 | 0.820 | 36/40 |

The primary result is `qc500_safe.vectoring` in the consolidated `experiment-results.json`, combining QC500 with candidate-maneuver speed screening. QC500 and QC350 without candidate screening are sensitivity comparisons in the same file. Positive correlation supports a response to synthetic deformation, not validity for real controller workload.

## Aircraft-count sensitivity

Across the six QC500 hours with estimable full baselines, median hourly estimability rates at N=30, 40, and 50 are 52%, 67%, and 92%. Median absolute D differences from the full point cloud are 0.235, 0.126, and 0.048. Each size uses 50 random subsamples. Under strict screening at N=50, only five hours have enough aircraft and an estimable baseline; changes in sample composition must not be interpreted as a pure aircraft-count effect.

## Figures

Matplotlib produces 200 dpi PNGs and vector SVGs. Colored segments show retained Holding doses, gray segments show excluded doses, black lines are means across available repeats at each dose, and orange dashed lines/stars mark selected peaks. Missing D is not replaced by zero; the number of repeats contributing to the mean may vary. Every figure retains the full range for reference.

### qc500-holding-scenes-1

![qc500-holding-scenes-1](figures/qc500-holding-scenes-1.png)

[Vector SVG](figures/qc500-holding-scenes-1.svg)

### qc500-holding-scenes-2

![qc500-holding-scenes-2](figures/qc500-holding-scenes-2.png)

[Vector SVG](figures/qc500-holding-scenes-2.svg)

### qc350-holding-scenes-1

![qc350-holding-scenes-1](figures/qc350-holding-scenes-1.png)

[Vector SVG](figures/qc350-holding-scenes-1.svg)

### qc350-holding-scenes-2

![qc350-holding-scenes-2](figures/qc350-holding-scenes-2.png)

[Vector SVG](figures/qc350-holding-scenes-2.svg)

### holding-dose-response

![holding-dose-response](figures/holding-dose-response.png)

[Vector SVG](figures/holding-dose-response.svg)

### holding-correlation-comparison

![holding-correlation-comparison](figures/holding-correlation-comparison.png)

[Vector SVG](figures/holding-correlation-comparison.svg)

### vectoring-full-range

![vectoring-full-range](figures/vectoring-full-range.png)

[Vector SVG](figures/vectoring-full-range.svg)

### aircraft-count-sensitivity

![aircraft-count-sensitivity](figures/aircraft-count-sensitivity.png)

[Vector SVG](figures/aircraft-count-sensitivity.svg)

### holding-d-estimability

![holding-d-estimability](figures/holding-d-estimability.png)

[Vector SVG](figures/holding-d-estimability.svg)

### vectoring-d-estimability

![vectoring-d-estimability](figures/vectoring-d-estimability.png)

[Vector SVG](figures/vectoring-d-estimability.svg)

### vectoring-dose-response

![vectoring-dose-response](figures/vectoring-dose-response.png)

[Vector SVG](figures/vectoring-dose-response.svg)

## Data and reproduction

- [All statistics and per-hour results](results/summary.json)
- [Consolidated full-dose data](results/experiment-results.json)
- [Holding point-level inclusion and exclusion reasons](results/qc500-holding-point-selection.csv)
- [Strict-screening point-level decisions](results/qc350-holding-point-selection.csv)
- [Raw trajectory rejection audit](results/quality_audit.json)
- [Aircraft-count sensitivity data](results/aircraft-count-sensitivity.json)
- [Runtime environment and source hashes](results/run-manifest.json)
- [Statistical rules and input hashes](results/analysis-manifest.json)
- [Execution instructions](README.md)

Regenerate statistics, figures, and this report from saved full results without raw trajectories or a checkpoint:

```bash
python evaluation/code/refresh_outputs.py
```

To rerun Encoder inference and all experiments from raw trajectories, set `ATM_DATA_ZIP` and `ATM_ENCODER_CHECKPOINT`:

```bash
python evaluation/code/run_evaluation.py
python evaluation/code/refresh_outputs.py
```

Inference environment: PyTorch `2.14.0+cu130` ; device `cuda`. Checkpoint SHA256:`d3abfc192a2e7a0f84bb1c4207ee04cfc4a4880755530da475124c5f711753ea`.
