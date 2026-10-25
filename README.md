# Trajectory Representation and Scene Complexity

This project includes a trained trajectory Encoder, a scene-embedding point-cloud complexity estimator, and method and experiment records. The repository maintains a single top-level README and a single dependency manifest at `requirements.txt`.

The Encoder maps an individual trajectory to a vector; `Complexity` estimates the empirical correlation dimension of multiple vectors from one scene. Proxy metrics are not ground-truth human complexity labels.

## Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Encoder: Inference, Experiments, and Retraining](#encoder)
- [Complexity: Interface and Quality Rules](#complexity)
- [Validation](#validation)
- [Methods, Licensing, and Limitations](#methods)

| Path | Contents |
|---|---|
| `Encoder/` | Frozen weights, inference interface, training implementation, experiment logs, and reports |
| `Complexity/` | NumPy/SciPy complexity estimator, Python/CLI interfaces, and tests |
| `doc/` | Methodology, training plans, and integration notes |
| `requirements.txt` | The single dependency manifest for the project, including PyTorch |

<a id="installation"></a>
## Installation

Use **Python 3.10 or later**. Run these commands from the repository root; install only the root requirements file. There is no need to install dependencies separately from component directories.

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run subsequent commands in the activated environment. Recreate an existing Python 3.9 environment with Python 3.10 or later; rerunning `venv` does not upgrade the interpreter in an existing environment. Installing dependencies does not provide the original training data or CUDA drivers. Retraining also requires a suitable GPU environment; see the Encoder section.

<a id="quick-start"></a>
## Quick Start

### 1. Prepare trajectories

Save each aircraft trajectory as a separate `.npy` file containing finite `(T, 3)` ENU coordinates in metres, already sampled at 10-second intervals, with at least 30 points.

```text
trajectories/
  aircraft_001.npy
  aircraft_002.npy
  ...
```

Upstream processing must handle time-window assignment, coordinate and altitude-datum conversion, trajectory segmentation, flight-identity verification, and aircraft deduplication. A scene should contain only trajectories from the same time window, with one vector per aircraft. Do not combine different hours in one point cloud.

### 2. Encode and pool

Run the repository-root script directly. Place one `.npy` file per aircraft in `trajectories/`. Each file must contain finite `(T, 3)` local ENU coordinates in metres, already sampled at 10-second intervals, with at least 30 points. All files in this folder are treated as one scene and must come from the same time window.

```bash
python encode_scene.py
```

The script stacks one pooled embedding per input aircraft. The resulting array is ready for the complexity step below.

### 3. Estimate complexity

```bash
python -m Complexity artifacts/scene_001_embeddings.npy --output artifacts/scene_001_complexity.json
```

Inspect each result's `status`, `reason`, and fit diagnostics. `unestimable` must not be interpreted as complexity zero. The estimator computes all unordered pairs exactly by default, up to five million pairs.

<a id="encoder"></a>
## Encoder

### Checkpoint and experiment records

The 12 independent experiments in [PLAN.md](Encoder/PLAN.md) are complete, with 30 epochs each (360 epochs total). The selected frozen model is **16-dimensional, sum pooling, seed 43**, with RDP ε=120m and τ=0.01. Validation selected the epoch-30 checkpoint. CPU loading, parameter freezing, and inference on a real trajectory have been checked.

| File | Purpose |
|---|---|
| [encoder.pt](Encoder/encoder/encoder.pt) | Selected weights, including model configuration and training-set preprocessing parameters |
| [config.json](Encoder/encoder/config.json) | Model configuration, checkpoint epoch, and validation selection record |
| [embeddings.npz](Encoder/encoder/embeddings.npz) | Sum / mean / signed GeM-p2 vectors for all 16,183 trajectories; not an hourly scene archive |
| [example_input_output.npz](Encoder/encoder/example_input_output.npz) | One real TEST trajectory and its token/trajectory vectors |
| [checkpoint_manifest.json](Encoder/reports/checkpoint_manifest.json) | SHA256, file size, and seed for nine checkpoints |
| [checkpoints/](Encoder/checkpoints/) | Comparison checkpoints |
| [probe_summary.csv](Encoder/reports/probe_summary.csv) | Test metrics across three dimensions, three seeds, and three pooling methods |
| [three_seed_summary.json](Encoder/reports/three_seed_summary.json) | Mean and sample standard deviation across three seeds |
| [experiment_logs/](Encoder/experiment_logs/) | Per-epoch losses, settings, and validation records |
| [RESULTS_10s_ZH.md](Encoder/reports/RESULTS_10s_ZH.md) | Current 10-second results report (Chinese) |

The inference input is a finite `(T, 3)` array of ENU coordinates in metres, already sampled at ten-second intervals. Each trajectory must have at least 30 points. The model constructs nine input features internally and uses the training-set mean and standard deviation stored in the checkpoint; preprocessing statistics are not refit during inference. The model runs in evaluation mode with frozen parameters. Token vectors are L2-normalized; the sum-pooled vector is not additionally L2-normalized.

```python
from Encoder.trajectory_encoder.inference import FrozenEncoder

encoder = FrozenEncoder("Encoder/encoder/encoder.pt", pooling="sum", device="cpu")
result = encoder.encode(enu_m)
print(result["tokens"].shape)     # (T, 16)
print(result["embedding"].shape)  # (16,)
```

Supported pooling modes are `sum`, `mean`, and `gem2` (signed GeM-p2). The result also includes the sampled point count, pooling mode, and preprocessing ID. Checkpoints are loaded with `weights_only=False`; **load only trusted checkpoint files**. The current interface does not automatically adapt legacy bare `state_dict` files.

### Retraining

Download the six RKSIa TSV files and `RKSIa_stats.csv` into the same directory. Training requires a bf16-capable CUDA environment; the historical experiments used PyTorch 2.7.1+cu128. Select a PyTorch CUDA wheel compatible with your target environment. Install project dependencies from the root `requirements.txt`, activate that environment, and then run from `Encoder/`:

```bash
cd Encoder
python -m trajectory_encoder.data --source "PATH_TO_RKSIA_DATA" --out prepared
python -m trajectory_encoder.checks
python -m trajectory_encoder.benchmark
python complete_local.py
```

Training caches are written to `Encoder/runs/`; historical delivery records are in `Encoder/experiment_logs/` and should not be mistaken for training completed on the current machine.

<a id="complexity"></a>
## Complexity

### Scope and Python interface

The component is independent of the Encoder and directly depends only on NumPy/SciPy; install dependencies from the project root manifest. It does not load or train the Encoder, convert coordinates, run PCA, create time windows, flatten or pool trajectories, or identify/deduplicate aircraft IDs. Inputs must be finite real-valued `(N, D)` arrays. `(N, T, D)` arrays, NaN, Inf, complex values, and strings are rejected. Duplicate embeddings are retained and must not be removed as if they were duplicate aircraft.

Inputs are not standardized or L2-normalized by default. Setting `normalize=True` changes the point-cloud geometry and rejects zero vectors; keep the checkpoint, preprocessing, pooling, normalization, and distance rules fixed across experiments.

```python
import numpy as np
from Complexity import ComplexityConfig, estimate_complexity, correlation_integral

points = np.load("hour_01.npy", allow_pickle=False)
result = estimate_complexity(
    points, scene_id="2026-01-01T08:00:00Z",
    config=ComplexityConfig(normalize=False),
)
if result.status == "ok":
    print(result.dimension, result.r_squared)
else:
    print("Cannot estimate:", result.reason)

# Interface example only, not a recommended scale; scale depends on checkpoint/pooling.
result = estimate_complexity(points, fit_range=(0.05, 0.5))
curve = correlation_integral(points, np.geomspace(0.01, 1.0, 64))
```

Main function signatures:

```text
estimate_complexity(embeddings, *, config=None, radii=None, fit_range=None, scene_id=None)
correlation_integral(embeddings, radii, *, normalize=False, max_pairs=5_000_000)
```

`correlation_integral` requires at least two points. `result.to_dict()` can be serialized directly to JSON and includes:

- `status`: `ok` or `unestimable`; only `ok` provides `dimension`. `reason` gives the rejection reason, or `None` when successful.
- `scene_id`, `n_samples`, `embedding_dim`, `n_unique`, `n_pairs`, and `zero_distance_pairs`; counts may be `None` when rejected before distance calculation.
- `radii`, `correlation`, and `pair_counts`: the complete discrete curve; the curve may be absent for early rejections.
- `fit_indices`, `fit_radius_range`, `fit_slope`, `intercept`, and `r_squared`: candidate-fit diagnostics. A rejected candidate slope is not a valid `dimension`.
- `selection`, `requested_fit_range`, `config`, and `warnings`: selection rules and warnings.

Undefined results are represented as `None` (JSON `null`), not NaN or Inf. **An unestimable result is not complexity zero.**

### Method and quality criteria

The estimator computes exact Euclidean distances for unordered pairs, counting only `i < j` and excluding self-pairs:

```text
C(r) = count(distance(i,j) < r, i < j) / [N(N-1)/2]
log C(r) = D2 * log r + intercept
```

The comparison is strict: pairs exactly at radius `r` are excluded. The automatic mode uses engineering defaults, not thresholds guaranteed to be optimal by a paper:

1. At least 30 points; this does not guarantee an adequate sample.
2. Generate 64 log-spaced radii from the minimum positive distance to the maximum distance.
3. Select all radii with `0.02 <= C(r) <= 0.3` and at least 10 included pairs.
4. Require at least 8 fit radii and a maximum/minimum radius ratio of at least 2.
5. Fit an OLS line with intercept to `log(r)` and `log(C(r))`; output dimension only for a positive slope and `R² >= 0.98`.

The method does not search short windows for the highest R². With explicit `fit_range=(r_min, r_max)`, radii are generated in the interval unless supplied; supplied radii are selected within the closed interval. Explicit mode skips the `0.02..0.3` filter but still excludes `C=0` and `C=1` and retains pair-count, fit-count, span, and R² checks.

| `ComplexityConfig` parameter | Default |
|---|---:|
| `normalize` | `False` |
| `n_radii` | 64 |
| `min_samples` | 30 |
| `min_fit_points` | 8 |
| `min_pairs` | 10 |
| `correlation_bounds` | `(0.02, 0.3)` |
| `min_radius_ratio` | 2.0 |
| `min_r_squared` | 0.98 |
| `max_pairs` | 5,000,000 |

| `reason` | Meaning |
|---|---|
| `insufficient_samples` | Too few aircraft/points |
| `collapsed_point_cloud` | All distances are zero |
| `no_distance_scale_range` | All positive distances are equal; automatic scales cannot be generated |
| `insufficient_fit_scales` | Too few usable scales, possibly due to sparsity or saturation |
| `insufficient_scale_span` | Scale range is too narrow |
| `flat_correlation_curve` | No distinguishable growth in the correlation integral |
| `poor_linear_fit` | R² is below the threshold |
| `nonpositive_slope` / `nonfinite_fit` | Invalid slope or numerical fit failure |

Duplicate embeddings and zero distances are reported and retained in pair counts; near-duplicates are not merged and noise is not added. High R² does not prove true fractal structure. This is an empirical finite-sample slope, not a statistical confidence interval. Because C(r) values share pairs across radii, ordinary OLS standard errors should not be treated as reliable uncertainty estimates.

Distance calculation is `O(N²D)`, sorting is `O(P log P)`, and memory is `O(P + ND)`, where `P=N(N-1)/2`. The distance array for five million pairs is about 40 MB, plus temporary memory. Exceeding the resource limit raises an error rather than silently sampling; do not split a scene arbitrarily to work around the limit.

### Files and CLI

A single-scene `.npy` stores an `(N, D)` array. In a multi-scene `.npz`, each key is a scene ID and each value is an `(N_s, D)` array; scene sizes may differ.

```python
np.save("hour_01.npy", embeddings_hour_01)
np.savez("hours.npz", hour_01=embeddings_hour_01, hour_02=embeddings_hour_02)
```

```bash
python -m Complexity --help
python -m Complexity hour_01.npy -o result.json
python -m Complexity hours.npz -o results.json
python -m Complexity hours.npz --fit-range 0.05 0.5 --normalize -o results.json
```

The JSON top level contains `schema_version`, `method`, `metric`, `input`, and `results`. Without `-o`, output is written to stdout. NumPy files are loaded with `allow_pickle=False`; pickle is not supported. The output directory must already exist, and output must not overwrite the input.

Successful processing returns exit code 0, including files with `unestimable` scenes; callers must still inspect each status. Invalid formats, arguments, or resource-limit violations return 2. A batch with invalid input fails as a whole and does not emit partial results.

### Connecting to the Encoder

Stack each aircraft's `result["embedding"]` from the same hour into an `(N, 16)` array. An empty scene may use `(0, 16)`. Do not pass tokens, dictionaries, or a single `(16,)` vector. Each trajectory must have at least 30 sampled points; by default each scene also needs at least 30 aircraft and must pass fit-quality checks. See the [handoff notes](doc/atscc-handoff.md) for integration details. The legacy `ATSCC.load_model/encode_scene` entry points no longer apply.

**Do not use `Encoder/encoder/embeddings.npz` directly as an hourly scene archive.** Its keys are `sum`, `mean`, and `gem2`, and each value contains all 16,183 trajectories; it is not a `scene_id -> (N, D)` archive. Training data lacks absolute timestamps and real flight IDs, so true hourly scenes cannot be reconstructed from it. Different pooling outputs are not different scenes.


<a id="validation"></a>
## Validation

From the repository root, with the environment activated, run the Complexity tests:

```bash
python -m unittest discover -s Complexity/tests -v
```

Coverage includes hand-calculated pair counts, strict boundaries, brute-force comparisons, empirical line/plane dimensions, translation/scaling/permutation invariance, explicit scales and OLS, duplicates/collapse/empty scenes, invalid inputs, normalization, quality rejection, resource limits, CLI, and JSON.

Run the existing Encoder verification scripts from its directory, using the same activated root environment:

```bash
cd Encoder
python example.py
python verify_delivery.py
```

Historical validation records are in `Encoder/reports/`; they do not mean validation has been rerun on the current machine. Training checks and benchmarks require a suitable CUDA environment.

<a id="methods"></a>
## Methods, Licensing, and Limitations

- Complexity methodology: [trajectory-embedding-point-cloud-complexity.md](doc/trajectory-embedding-point-cloud-complexity.md). A finite-sample empirical correlation dimension and engineering fit thresholds do not prove true fractal structure or provide confidence intervals.
- Interface boundaries and integration: [atscc-handoff.md](doc/atscc-handoff.md). Hourly scenes require reliable timestamps, aircraft/flight identities, and consistent trajectory aggregation; do not treat the full-trajectory archive as hourly data.
- Encoder plan and frozen experiment protocol: [PLAN.md](Encoder/PLAN.md) and [PROTOCOL.md](Encoder/PROTOCOL.md).
- The implementation is based on a fixed revision of [ATSCC](https://github.com/petchthwr/ATSCC/tree/789ccd72b7496b52e03df7d8599d8c9e6659bdb9) and adapted as an ATSCC/ITSC-inspired Encoder. See [THIRD_PARTY_LICENSE_ATSCC.md](Encoder/THIRD_PARTY_LICENSE_ATSCC.md) for licensing and [CITATION.md](Encoder/CITATION.md) for citation.
- Original data, some weights, or training artifacts may be excluded due to size limits or ignore rules and may need to be obtained separately. Check actual files and verification records in the relevant directories and reports.
