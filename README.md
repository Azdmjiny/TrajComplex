# Trajectory Representation and Scene Complexity

This project brings together trajectory representation learning and air-traffic scene complexity analysis. It includes a trained trajectory encoder, an independent point-cloud complexity estimator, OpenSky data around Singapore Changi Airport, and supporting method and experiment documentation.

> **Current scope:** The Encoder maps an individual trajectory to a vector. `Complexity` estimates the empirical correlation dimension of a set of vectors from one scene. The components can be connected, but an end-to-end hourly complexity workflow based on verified flight identities and time windows has not yet been validated.

## Project Structure

| Path | Contents |
|---|---|
| [`Encoder/`](Encoder/README.md) | Trained and frozen trajectory encoder, inference interface, experiment records, and results. |
| [`Complexity/`](Complexity/README.md) | Standalone NumPy/SciPy component for estimating the empirical correlation dimension of an `(N, D)` scene-embedding point cloud, with Python and CLI interfaces. |
| [`doc/`](doc/) | Complexity methodology, Encoder training plans, and downstream integration notes. |
| [`requirements.txt`](requirements.txt) | Root Python dependencies. Install PyTorch separately for your CPU or CUDA environment. |

## Quick Start

The example below assumes PyTorch and the packages in `requirements.txt` are installed. It uses the frozen checkpoint at `Encoder/encoder/encoder.pt`.

### 1. Prepare trajectory inputs

Save each aircraft trajectory as a separate NumPy `.npy` file containing a finite `(T, 3)` array of local ENU positions in metres, ordered by time: east, north, up, sampled at 5-second intervals. The checkpoint expects RKSI-local coordinates; do not pass latitude/longitude or raw OpenSky columns directly. Each trajectory must contain at least 30 sampled points.

```text
trajectories/
  aircraft_001.npy   # (T1, 3), ENU metres
  aircraft_002.npy   # (T2, 3), ENU metres
  ...
```

Coordinate conversion, altitude handling, trajectory segmentation, identity resolution, and time-window assignment must be done upstream using consistent rules.

### 2. Encode and pool each trajectory

`FrozenEncoder.encode()` runs the model and pooling in one call. `pooling="sum"` is the selected default; `"mean"` and `"gem2"` are also supported. The returned `tokens` array contains one 16-dimensional vector per sampled point. The returned `embedding` is the pooled 16-dimensional vector for the whole trajectory.

Save this as `encode_scene.py` in the repository root and pass the `.npy` files assigned to one scene/time window:

```python
from pathlib import Path
import numpy as np
from Encoder.trajectory_encoder.inference import FrozenEncoder

encoder = FrozenEncoder(
    "Encoder/encoder/encoder.pt", pooling="sum", device="cpu"
)
trajectory_files = sorted(Path("trajectories").glob("*.npy"))

vectors = []
for path in trajectory_files:
    enu_m = np.load(path, allow_pickle=False)  # (T, 3), ENU metres
    result = encoder.encode(enu_m, resample_from_1hz=False)
    vectors.append(result["embedding"])

scene_embeddings = np.stack(vectors) if vectors else np.empty((0, 16))
Path("artifacts").mkdir(exist_ok=True)
np.save("artifacts/scene_001_embeddings.npy", scene_embeddings)
print("Saved", scene_embeddings.shape, "to artifacts/scene_001_embeddings.npy")
```

From the repository root, run the script manually with the project's Python environment:

```bash
python encode_scene.py
```

This processes every `.npy` file in `trajectories/` as one scene and writes the pooled embedding matrix to `artifacts/scene_001_embeddings.npy`. Then run the Complexity command below to write `artifacts/scene_001_complexity.json`.

### 3. Estimate scene complexity

Run from the repository root:

```bash
python -m Complexity artifacts/scene_001_embeddings.npy --output artifacts/scene_001_complexity.json
```

The JSON result is saved at the path supplied to `--output`. Check each result's `status` and diagnostics; `unestimable` is not a complexity value of zero. The estimator uses exact pairwise distances and has a default limit of five million pairs.

The `Complexity` API does not load the Encoder, create time windows, convert coordinates, or deduplicate aircraft IDs. Different scenes should be estimated separately. See [`Complexity/README.md`](Complexity/README.md) for input requirements and fit criteria, and [`Encoder/README.md`](Encoder/README.md) for inference and training details.

## Typical Data Flow

1. Organize trajectories by aircraft and time window; verify coordinate system, units, missing values, and trajectory segmentation.
2. Use the frozen Encoder to produce one fixed-dimensional vector per trajectory. The selected model is 16-dimensional, with sum pooling and seed 43.
3. Stack the vectors for one scene into an `(N, D)` array and pass it to `Complexity`. Estimate each scene separately; do not combine different hours in one point cloud.
4. Inspect the result's `status`, `reason`, and fit diagnostics. `unestimable` means the estimate could not be established; it does not mean complexity is zero.

The complexity component does not load the Encoder, preprocess or pool trajectories, deduplicate flight IDs, or create time windows. Upstream code must prepare the point cloud consistently. See [`Complexity/README.md`](Complexity/README.md) and [`doc/atscc-handoff.md`](doc/atscc-handoff.md) for the interface and boundaries.

## Tests and Validation

Run the complexity component tests from the repository root:

```bash
python -m unittest discover -s Complexity/tests -v
```

Encoder artifact verification and experiment reproduction steps are documented in [`Encoder/README.md`](Encoder/README.md). Encoder training requires a suitable CUDA/PyTorch environment and separately obtained training data; it is not ready to run with only the root dependencies installed.

## Data, Results, and Limitations

- The Encoder report states that its test-set proxy metrics did not outperform the stronger of the two baselines. These experiments therefore do not establish that self-supervised training improves geometric-proxy prediction. Proxy metrics are not ground-truth human complexity labels. See [`Encoder/reports/RESULTS_ZH.md`](Encoder/reports/RESULTS_ZH.md).
- `Complexity` computes an empirical correlation dimension from a finite sample. Its automatic scale selection and fit-quality thresholds are engineering rules; they do not establish true fractal structure or provide statistical confidence intervals.
- OpenSky data consists of receiver-network observations and may have incomplete coverage. Observations in the airport's surrounding area do not necessarily represent flights arriving at or departing from Changi. See [`data/OpenSky_Changi_2026-09/README.md`](data/OpenSky_Changi_2026-09/README.md) for scope, quality, and usage notes.
- Hourly scene complexity requires reliable absolute timestamps, aircraft/flight identities, and trajectory aggregation within each window. Current data and handoff notes state that these prerequisites are not yet sufficient for end-to-end hourly complexity validation. Do not treat the existing all-trajectory embedding archive as hourly scene data.
- Some raw data or training artifacts may need to be obtained separately or may be excluded due to size or ignore rules. Check the relevant subdirectory README and reports for available files and verification records.

## Methods and Attribution

The complexity method is described in [`doc/trajectory-embedding-point-cloud-complexity.md`](doc/trajectory-embedding-point-cloud-complexity.md). Encoder methods, the frozen experiment protocol, and third-party licensing are documented in [`Encoder/README.md`](Encoder/README.md), [`Encoder/PROTOCOL.md`](Encoder/PROTOCOL.md), [`Encoder/CITATION.md`](Encoder/CITATION.md), and [`Encoder/THIRD_PARTY_LICENSE_ATSCC.md`](Encoder/THIRD_PARTY_LICENSE_ATSCC.md).
