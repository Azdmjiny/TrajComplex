# Trajectory Representation and Scene Complexity

This project includes a trained trajectory Encoder, a scene-embedding point-cloud complexity estimator, OpenSky data around Singapore Changi Airport, and method and experiment records. The repository maintains a single top-level README and a single dependency manifest at `requirements.txt`.

The Encoder maps an individual trajectory to a vector; `Complexity` estimates the empirical correlation dimension of multiple vectors from one scene. The OpenSky integration script is runnable, but transfer from RKSI to WSSS and hourly complexity results have not been conclusively validated. Proxy metrics are not ground-truth human complexity labels.

## Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Encoder: Inference, Experiments, and Retraining](#encoder)
- [Complexity: Interface and Quality Rules](#complexity)
- [OpenSky Data: Definition and Usage](#opensky-data)
- [Validation](#validation)
- [Methods, Licensing, and Limitations](#methods)

| Path | Contents |
|---|---|
| `Encoder/` | Frozen weights, inference interface, training implementation, experiment logs, and reports |
| `Complexity/` | NumPy/SciPy complexity estimator, Python/CLI interfaces, and tests |
| `data/OpenSky_Changi_2026-09/` | September 2026 OpenSky data around Changi, quality records, and extraction tools |
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

Save each aircraft trajectory as a separate `.npy` file containing a finite real-valued `(T, 3)` array of local ENU coordinates in metres (east, north, up), ordered by time and sampled at 5-second intervals. The current checkpoint uses RKSI-local coordinates; do not pass latitude/longitude or unprocessed OpenSky columns directly. Each trajectory must contain at least 30 points after sampling.

```text
trajectories/
  aircraft_001.npy
  aircraft_002.npy
  ...
```

Upstream processing must handle time-window assignment, coordinate and altitude-datum conversion, trajectory segmentation, flight-identity verification, and aircraft deduplication. A scene should contain only trajectories from the same time window, with one vector per aircraft. Do not combine different hours in one point cloud.

### 2. Encode and pool

Save the following as `encode_scene.py` in the repository root, then run `python encode_scene.py`:

```python
from pathlib import Path
import numpy as np
from Encoder.trajectory_encoder.inference import FrozenEncoder

encoder = FrozenEncoder(
    "Encoder/encoder/encoder.pt", pooling="sum", device="cpu"
)
vectors = []
for path in sorted(Path("trajectories").glob("*.npy")):
    enu_m = np.load(path, allow_pickle=False)
    result = encoder.encode(enu_m, resample_from_1hz=False)
    vectors.append(result["embedding"])

scene_embeddings = np.stack(vectors) if vectors else np.empty((0, 16))
Path("artifacts").mkdir(exist_ok=True)
np.save("artifacts/scene_001_embeddings.npy", scene_embeddings)
print(scene_embeddings.shape)
```

This example treats every file in `trajectories/` as one scene. `FrozenEncoder.encode()` returns both per-token vectors and a pooled trajectory embedding; pass an `(N, D)` array made from the pooled embeddings to `Complexity`.

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
| [RESULTS_ZH.md](Encoder/reports/RESULTS_ZH.md) | Results report (Chinese) |

The inference input is an `(T, 3)` array of RKSI-local ENU coordinates in metres. Each trajectory must have at least 30 sampled points. The model constructs nine input features internally and uses the training-set mean and standard deviation stored in the checkpoint; preprocessing statistics are not refit during inference. The model runs in evaluation mode with frozen parameters. Token vectors are L2-normalized; the sum-pooled vector is not additionally L2-normalized.

```python
from Encoder.trajectory_encoder.inference import FrozenEncoder

encoder = FrozenEncoder("Encoder/encoder/encoder.pt", pooling="sum", device="cpu")
result = encoder.encode(enu_m, resample_from_1hz=False)
print(result["tokens"].shape)     # (T_sampled, 16)
print(result["embedding"].shape)  # (16,)
```

Supported pooling modes are `sum`, `mean`, and `gem2` (signed GeM-p2). The result also includes the sampled point count, pooling mode, and preprocessing ID. Checkpoints are loaded with `weights_only=False`; **load only trusted checkpoint files**. The current interface does not automatically adapt legacy bare `state_dict` files.

### Experiments and results

Training data came from RKSIa in the public [ATFMTraj dataset](https://huggingface.co/datasets/petchthwr/ATFMTraj). The train/validation/test split contains 6,877 / 1,214 / 8,092 trajectories. The validation set was split from the official TRAIN set; the official TEST set was reserved for final evaluation. SHA256 hashes for six local TSV files match the public dataset version; see [public_data_verification.json](Encoder/reports/public_data_verification.json). The original TSV files are not included in the repository.

The model uses nine input features, a four-layer causal Transformer, width 256, FFN 512, four heads, dropout 0.35, 20% input masking, and RDP flat-SNN. Four 8-dimensional screening runs varied ε=120/1200m and τ=0.01/0.05; then dimensions 4/8/16 were compared across three seeds each. Training used batch size 16, AdamW with learning rate 1e-5, and bf16. The historical training device was an RTX 5060 Laptop GPU with 8 GB. Sum pooling was fixed in advance as the primary method; mean and signed GeM-p2 were sensitivity analyses.

Hyperparameters, embedding dimension, and representative seed were selected using validation data only, before TEST evaluation. See [PROTOCOL.md](Encoder/PROTOCOL.md) for the protocol, [implementation_checks.json](Encoder/reports/implementation_checks.json) for implementation checks, and [export_verification.json](Encoder/reports/export_verification.json) for export validation. The selected model did not outperform the stronger of the two baselines on any of the four proxies; these results do not establish that self-supervised training adds geometric-proxy prediction capability.

![Training curves](Encoder/reports/training_curves.png)

![Test results and baselines](Encoder/reports/baseline_comparison.png)

![Dimension and pooling comparison](Encoder/reports/dimension_pooling.png)

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

Stack each aircraft's `result["embedding"]` from the same hour into an `(N, 16)` array. An empty scene may use `(0, 16)`. Do not pass tokens, dictionaries, or a single `(16,)` vector. Each trajectory must have at least 30 sampled points; by default each scene also needs at least 30 aircraft and must pass fit-quality checks. See the [handoff notes](doc/atscc-handoff.md) for integration details and OpenSky processing. The legacy `ATSCC.load_model/encode_scene` entry points no longer apply.

**Do not use `Encoder/encoder/embeddings.npz` directly as an hourly scene archive.** Its keys are `sum`, `mean`, and `gem2`, and each value contains all 16,183 trajectories; it is not a `scene_id -> (N, D)` archive. Training data lacks absolute timestamps and real flight IDs, so true hourly scenes cannot be reconstructed from it. Different pooling outputs are not different scenes.

<a id="opensky-data"></a>
## OpenSky Data

The files described below are in `data/OpenSky_Changi_2026-09/`. Use `progress.json` and the final `data_quality.json` to check status. The month is considered complete only after all 720 hours finish and pass local validation.

### Extraction definition

- Singapore local time: 2026-09-01 00:00:00 inclusive to 2026-10-01 00:00:00 exclusive (Asia/Singapore, UTC+08:00).
- UTC: 2026-08-31 16:00:00 to 2026-09-30 16:00:00, covering 720 complete hours.
- Center: WSSS Airport Reference Point (control tower), 1.3592111111° N, 103.989325° E; airport elevation 6.66 m.
- Coverage: a circular research area within 100 km of the center. This is an extraction definition, not the official TMA boundary.
- Altitude is not truncated and on-ground records are retained. The data includes all aircraft actually received within the area, potentially including nearby-airport and overflight traffic; it does not mean every aircraft arrived at or departed from Changi.
- States whose Unix second is divisible by 10 are retained as observed. No points are added, interpolated, or fabricated during this raw extraction. Interpolation used in later Encoder integration is a separate step.

### Files

| Path | Contents |
|---|---|
| `raw/` | UTC-hour CSV.gz files with raw 10-second sampled states, including stale positions and missing fields |
| `sampled_10s/` | Excludes records with unknown position/receive time or lag over 15 seconds; keeps the last observed record per aircraft per 10-second bucket; other missing fields remain |
| `manifest/` | Per-hour row counts, aircraft counts, interval statistics, query IDs, execution details, and SHA256 |
| `queries/` | Prepared SQL; completed queries are identified by manifest IDs and explicitly filter hour partitions, time, geographic bounds, and circular distance |
| `config.json` | Airport, time, area, sampling, and cleaning parameters |
| `progress.json` | Monthly download status |
| `flight_metadata/` | OpenSky-inferred WSSS arrival/departure information by UTC end date, with an extra following day; not a complete airport flight list |
| `hourly_summary.csv`, `data_quality.json` | Local hourly statistics and quality report |
| `extract.mjs` | Reusable extraction module; credentials remain in memory and are not included in delivered files |

### Fields and reading data

| Field | Meaning / units |
|---|---|
| `time` | State time, UTC Unix seconds |
| `icao24` | Transponder address; hexadecimal string, preserving leading zeros |
| `callsign` | Broadcast callsign; may be empty or contain trailing spaces and is not guaranteed unique |
| `lat / lon` | WGS84 latitude / longitude, degrees |
| `baroaltitude / geoaltitude` | Barometric / geometric altitude, metres |
| `velocity` | Ground speed, m/s |
| `heading` | Direction of motion relative to true north, degrees |
| `vertrate` | Vertical speed, m/s; positive means climbing |
| `onground` | Ground state, true / false |
| `lastposupdate / lastcontact` | Most recent position update / signal reception time, UTC Unix seconds |
| `hour` | Database UTC-hour partition, Unix seconds |

Empty CSV fields mean missing values; do not replace them with zero. Read one hour at a time rather than loading the whole month. Run this example from the repository root:

```python
import pandas as pd

df = pd.read_csv(
    "data/OpenSky_Changi_2026-09/sampled_10s/2026-08-31T16Z.csv.gz",
    dtype={"icao24": "string", "callsign": "string"},
)
df["time_sgt"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("Asia/Singapore")
```

Each file covers a half-open one-hour window; aircraft spanning hours have a segment in each file. Do not identify flights by callsign alone, connect trajectories across long gaps, or label nearby/overflight traffic as WSSS flights without verification. Metadata first/last observations are not actual takeoff/landing times, and estimated airport fields may be missing.

### Encoder integration for hourly scenes

The raw data has not been converted into the nine features used in the training pipeline, and normalization parameters have not been fitted. Check altitude datum, direction calculations, missing values, continuous trajectory segments, and date/flight splits; then freeze a preprocessing version.

`Encoder/opensky_scene.py` filters valid airborne observations, groups by ICAO24 and UTC hour, and splits segments at gaps over 60 seconds. It keeps the longest segment per aircraft per hour with at least 16 real observations. After converting WGS84 to WSSS ENU, it linearly interpolates to the model's 5-second cadence, applies frozen sum pooling, and applies the existing Complexity quality checks.

```bash
# Trial one hour first
python Encoder/opensky_scene.py --pattern '2026-09-01T00Z.csv.gz'
# After review, process all inputs
python Encoder/opensky_scene.py
```

Options include `--input-dir`, `--output-dir`, `--checkpoint`, `--device`, and `--max-gap-seconds`. By default, output is written to the ignored directory `data/OpenSky_Changi_2026-09/encoder_scenes/` and includes `hourly_embeddings.npz`, `hourly_complexity.json`, diagnostics, and a trajectory filtering manifest.

Inference transfers the model from RKSI training to WSSS. Five-second points interpolated between 10-second observations are estimates, and altitude datum may differ. Outputs are exploratory, not validated WSSS complexity results. OpenSky receiver coverage is incomplete; handle empty/sparse windows and missing fields using the quality report, and do not claim complete coverage of all airport flights.

### Query and usage references

- [OpenSky historical data and efficient queries](https://openskynetwork.github.io/opensky-api/trino.html)
- [Singapore AIP WSSS, September 2026 edition](https://aim-sg.caas.gov.sg/aim-content/uploads/aip/17-SEP-2026/AIP/2026-09-03-000000/html/eAIP/SG-AD-2-WSSS-en-GB.html)
- [Trino `great_circle_distance`, which returns kilometres](https://trino.io/docs/current/functions/geospatial.html#great_circle_distance)

This extraction follows the approved non-commercial research use. It allows at most two concurrent queries, each covering a small number of explicit hourly partitions. If a query has not completed after five minutes, stop and inspect it rather than expanding the query.

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
