# Trajectory Injection Evaluation

Unified Holding and Vectoring injection experiment for the full WSSS arrival-only archive (720 hourly scenes). Both modes use the fixed epoch-60 Encoder and the same gated correlation-dimension configuration, listed below. This configuration differs from the ungated estimator used in the other three evaluations. Holding uses the midpoint anchor with **no minimum distance cutoff** from WSSS ARP; Vectoring retains the calibrated 600-second, 61-point, 15 km offset segment.

## Run

From the repository root, place the 720 WSSS hourly archives under `data/WSSS/hours/`:

```bash
python eval/trajectory_injection/run_experiment.py --output eval/results/wsss-injection
python -m unittest eval/trajectory_injection/test_holding.py
```

The output directory must not already exist. Use `--limit-scenes N` only for a smoke test. The runner requires exactly 720 `.npz` archives and verifies checkpoint/preprocessor hashes before processing. Trajectory archives are external inputs; the matching checkpoint is included at `Encoder/encoder/encoder.pt`.

## $D$ estimator configuration

$D$ is computed with `complexity.estimate_complexity` and an explicit `ComplexityConfig`, set in [`run_experiment.py`](run_experiment.py). Every value is passed explicitly, so changes to the package defaults do not affect this experiment.

| Setting | Value |
|---|---|
| Trajectory eligibility | Fragments with at least 30 finite points at exactly 10 s spacing; positions rounded to float32 before encoding |
| Embedding | 16-D, temporal sum pooling, no post-pooling normalization (`normalize=False`) |
| Distance and pairs | Euclidean; all unordered pairs, including zero-distance pairs; strict `distance < r` |
| Radius grid | 64 geometric radii from the baseline scene's minimum positive to maximum pairwise distance; held fixed for every dose and repeat of that scene |
| Fit scales | Radii with $0.02 \le C(r) \le 0.30$, $0 < C(r) < 1$ and at least 10 pairs (`min_pairs=10`) |
| Fit | Ordinary least squares on $\log C(r)$ versus $\log r$; slope is $D$ |
| Minimum requirements | `min_samples=15` trajectories, `min_fit_points=8` fit scales, fit radius span ratio `min_radius_ratio=2.0`, positive slope |
| Quality gate | $R^2 \ge 0.90$ (`min_r_squared=0.90`) |
| Pair limit | `max_pairs=5,000,000` |
| Scene inclusion | Only scenes whose baseline (dose 0) estimate passes every gate; a dose whose estimate fails is reported missing, not zero |

## Metrics and files

For each scene and repeat, `delta_D = D(k)-D(0)` and `delta_D_percent = 100*(D(k)-D(0))/D(0)`. The runner always writes the absolute D/Delta-D curve and, by default, percentage-scale dose, sequence, and scene metrics. Use `--no-percent-metrics` to omit percentage CSVs. Dose-average response is the trapezoidal signed area over the contiguous valid dose prefix divided by its maximum dose; Theil–Sen slope is reported in D/event or percentage points/event. Failed estimates remain missing; sequences with no valid positive-dose support are excluded from direction counts, not counted as zero. Direction counts are descriptive and uncalibrated, not detection rates.

The output contains `dose-repeat-results.csv`, `sequence-metrics.csv`, `scene-metrics.csv`, `dose-repeat-percent-results.csv`, `sequence-percent-metrics.csv`, `scene-percent-metrics.csv`, `injection-events.csv`, and a run manifest with input, checkpoint, preprocessor, and source hashes.

## Scope and limitations

Each run uses ten repeats and up to 15 events per sequence. Holding inserts a closed 360-second racetrack (36 points) and trims 36 tail points, preserving track length; no aircraft repeats within a Holding sequence. Vectoring replaces non-overlapping 61-point windows. The synthetic maneuver geometry is an evaluation intervention, not proof of operational feasibility. No sham calibration is included, so response signs are not detection probabilities or significance claims.
