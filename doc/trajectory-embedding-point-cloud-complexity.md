# Trajectory-embedding point-cloud complexity

This note documents the current implementation in [complexity/calculator.py](../complexity/calculator.py). It replaces a missing documentation target; it does not reconstruct an earlier research protocol.

## Inputs and scene construction

Encode each aircraft-window trajectory using the same frozen Encoder, preprocessing, and pooling rule. Stack the pooled embeddings into a finite real array of shape `(N, D)`: one aircraft-window per row. Do not pass token sequences or treat different pooling variants as different scenes.

The calculator does not assemble hours, align timestamps, or infer flight identities. Those decisions belong to the upstream pipeline. A trajectory point cloud does not directly encode synchronized aircraft separation, conflicts, or controller workload.

## Estimator

For each positive radius `r`, compute the fraction of unordered aircraft pairs whose Euclidean distance is strictly less than `r`:

```text
C(r) = number of pairs (i < j) with ||z_i - z_j|| < r / (N * (N - 1) / 2)
```

There are no self-pairs. Duplicate embeddings remain distinct observations; their zero-distance pairs contribute at every positive radius and produce a warning. Optional per-embedding L2 normalization changes the geometry; normalization is disabled by default and in the current evaluation.

Fit an ordinary least-squares line to `log C(r)` against `log r`. Its slope is the empirical D estimate. This is a finite-sample geometric statistic, not proof of fractal structure or a calibrated workload score.

## Default quality gates

- At least 30 aircraft-window embeddings.
- 64 logarithmically spaced candidate radii when none are provided.
- At least 10 contributing pairs at each fitted scale.
- Automatic fit selection uses all candidate scales with `0.02 <= C(r) <= 0.3`.
- At least 8 fitted scales, spanning a radius ratio of at least 2.
- Positive slope and fit R-squared of at least 0.98.

An explicit `fit_range` overrides the correlation-bound selection, but not the other quality gates. The estimator does not search for a smaller high-R-squared subwindow. Invalid inputs raise errors; valid inputs without an acceptable fit return `status="unestimable"` and no D. Never replace this missing D with zero.

## Comparability and interpretation

The current evaluation supplies candidate radii derived from each scene's baseline and holds that grid fixed across doses. However, the subset that passes the correlation bounds can change at every dose, so the actual fitted radius interval is not necessarily fixed. Inspect `fit_radius_range`, fit quality, and missing-estimate rates alongside D.

Keep the checkpoint, preprocessing, pooling, normalization, scene construction, and scale-selection policy consistent. Even then, aircraft count, trajectory duration, and spatial coverage may affect estimates. Sum pooling can confound trajectory length with embedding geometry. Quality gates are engineering diagnostics, not confidence intervals or guarantees of physical validity.

In the current Holding analysis, selecting a peak from the observed outcomes and retaining only its preceding segment is exploratory. It cannot establish an independent operating range or invalidate the declining segment. See the [evaluation report](../evaluation/reports/evaluation-pilot.md) for current results and limitations.

## Usage

From the repository root:

```python
from complexity import estimate_complexity

result = estimate_complexity(scene_embeddings)
if result.status == "ok":
    print(result.dimension)
else:
    print(result.reason)
```

```bash
python -m complexity --help
python -m complexity scene.npy -o scene.complexity.json
python -m complexity hours.npz -o hours.complexity.json
python -m unittest discover -s complexity/tests -v
```

A `.npy` file contains one scene. A `.npz` file maps scene IDs to `(N_s, D)` arrays. The pooled whole-dataset Encoder export is not automatically an hourly scene archive. See the [handoff note](atscc-handoff.md) for Encoder input requirements.
