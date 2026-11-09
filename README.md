# Trajectory Embeddings for Airspace-Scene Geometry

This repository provides a frozen trajectory encoder, a scene-level empirical correlation-dimension estimator, and the code for four evaluations of terminal-airspace traffic. Each trajectory is represented by one vector; vectors from the same hourly scene form the point cloud used by the estimator.

## Repository contents

| Path | Purpose |
|---|---|
| `Encoder/` | Frozen WSSS encoder, inference implementation, model configuration, and a known-input example |
| `complexity/` | Pairwise correlation-sum and finite-scale slope estimator |
| `eval/traffic-volume/` | Changi sample-size sensitivity experiment and hourly embedding cache |
| `eval/cross_airport/` | Four-airport hourly comparison and airport-specific encoder training |
| `eval/encoder_comparison/` | Comparison of encoder dimensions and training periods on common scenes |
| `eval/trajectory_injection/` | Holding and vectoring trajectory-intervention experiment |
| `eval/_hourly.py` | Shared hourly scene loading, encoding, and dimension calculation |
| `eval/_training.py`, `eval/_training_model.py` | Shared training data and model code |
| `encode_scene.py` | Encode trajectory files from one scene |
| `requirements.txt` | Python dependencies used by the repository |

## Setup

Use Python 3.12. From the repository root, create and activate an environment, then install the shared dependencies:

```bash
python -m venv .venv
```

Linux or macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Training the comparison encoders requires a BF16-capable CUDA GPU. The CPU option is available for inference where noted in the experiment documentation.

## Encode a scene and estimate its descriptor

The bundled WSSS encoder maps an eligible trajectory to a 16-dimensional vector using temporal sum pooling. Inputs are local ENU coordinates in metres sampled every 10 seconds and must contain at least 30 finite points. Coordinate conversion, resampling, trajectory selection, and assignment to an hourly scene are upstream steps.

Save each trajectory as a `(T, 3)` NumPy array in its own `.npy` file, then run from the repository root:

```bash
python encode_scene.py \
  --input-dir /path/to/one-scene-trajectories \
  --output eval/results/scene-embeddings.npy

python -m complexity eval/results/scene-embeddings.npy \
  --output eval/results/scene-complexity.json
```

The estimator computes the empirical correlation sum over unordered pairs and fits a finite-scale log–log slope. A scene for which the fit is undefined is reported as missing, not as zero. The estimator options and defaults are available with `python -m complexity --help`.

## Reproduce the evaluations

The Changi sample-size embedding cache is included, so its published curves and figures can be regenerated without the source trajectory archive or encoder inference:

```bash
python eval/traffic-volume/run_experiment.py \
  --embeddings eval/traffic-volume/embeddings.npz \
  --output eval/results/traffic-volume/reproduction
```

The other evaluations require prepared trajectory scenes and/or training archives that are not distributed in this repository. Their experiment READMEs specify input formats, selection rules, commands, and output files.

| Evaluation | Inputs and instructions |
|---|---|
| Changi sample-size sensitivity | The embedding cache is included. For preparation and re-encoding from the authorized archive, see [`eval/traffic-volume/README.md`](eval/traffic-volume/README.md). |
| Cross-airport comparison | Prepared hourly scenes for WSSS, RJTT, WMKK, and RKSI, plus three non-WSSS checkpoints. See [`eval/cross_airport/README.md`](eval/cross_airport/README.md). |
| Encoder comparison | WSSS training archive and prepared common scenes; training requires BF16-capable CUDA. See [`eval/encoder_comparison/README.md`](eval/encoder_comparison/README.md). |
| Holding and Vectoring | 720 prepared WSSS 2 hourly scene archives. See [`eval/trajectory_injection/README.md`](eval/trajectory_injection/README.md). |

The frozen WSSS checkpoint is at `Encoder/encoder/encoder.pt`; its configuration, checksum, preprocessing identity, and example input/output are documented under `Encoder/`. Experiment outputs are written to new directories under `eval/results/`, which Git ignores. Raw trajectory data and generated results are not included unless stated above.

## Interpretation

The descriptor summarizes the finite-scale geometry of learned trajectory embeddings in a selected scene. It is a geometric traffic descriptor; by itself, it does not measure controller workload or establish causal effects of operational interventions.
