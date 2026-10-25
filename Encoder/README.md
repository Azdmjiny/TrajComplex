# Trajectory Encoder

Start with the frozen inference interface for downstream use. Training, diagnostics, and packaging are separate workflows; none is required merely to encode a trajectory.

## Directory map

| Path | Purpose |
| --- | --- |
| `trajectory_encoder/` | Model, preprocessing, inference, training, and evaluation implementation |
| [encoder/](encoder/README.md) | Selected checkpoint, preprocessing/configuration, example, and pooled dataset export |
| [checkpoints/](checkpoints/README.md) | Nine candidate checkpoints for the dimension/seed comparison |
| [experiment_logs/](experiment_logs/README.md) | Historical text records for 12 runs, including screening |
| [reports/](reports/README.md) | Saved results, selection records, figures, and provenance |
| `offline_guard/` | Python networking guard used by offline launchers |
| `prepared/`, `runs/`, `.runtime_cache/` | Local generated data and training caches; ignored by Git |

Checkpoint files and the selected export are tracked in the current repository. Historical logs are not resumable training state: `runs/` contains local training outputs such as `best.pt`, while `experiment_logs/` contains the delivered text evidence.

## Use the frozen model

Install dependencies from the repository's `requirements.txt`. From the repository root:

```bash
python Encoder/example.py --checkpoint Encoder/encoder/encoder.pt --input Encoder/encoder/example_input_output.npz
python Encoder/verify_delivery.py
```

For Python integration:

```python
from Encoder.trajectory_encoder.inference import FrozenEncoder

encoder = FrozenEncoder("Encoder/encoder/encoder.pt", pooling="sum", device="cpu")
result = encoder.encode(enu_m)
embedding = result["embedding"]
```

Input is a finite `(T, 3)` ENU-metre array already sampled every ten seconds, with at least 30 points. The interface does not convert latitude/longitude, resample, or assemble scenes. The selected export is `encoder_10s_fixed90_seed43`, with 16-dimensional embeddings and sum pooling, trained for a fixed 90 epochs. See [PROTOCOL.md](PROTOCOL.md).

### Evaluation checkpoint identity

The checked-in `encoder/encoder.pt` is the strict-10-second epoch-90 checkpoint required by the evaluation workflow: SHA-256 `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`, preprocessor `52fabdb80ff5221882becc2e326e0e51089dbcf324a155bf7330f41442fa1477`. Its `preprocess.json` records `stride_s=10` and `include_endpoint=false`.

The older five-second candidate checkpoints remain in `checkpoints/` and `experiment_logs/` as historical sensitivity artifacts. They are not the selected export and must not be substituted without a separate evaluation rerun.

## Script responsibilities

| Script | Role and prerequisites |
| --- | --- |
| `example.py` | Encode the supplied example or a user trajectory |
| `verify_delivery.py` | Verify candidate/export hashes and inference against the saved example |
| `run_offline.py` | Launch `probe`, `checks`, `benchmark`, `pipeline`, or `finalize`; stages may require CUDA and prepared data |
| `complete_local.py` | Resume training through export, diagnostics, report generation, and verification |
| `posthoc_diagnostics.py` | Recompute diagnostics using local prepared data and training outputs |
| `make_report.py` | Regenerate reports; reads local `runs/` histories as well as saved results |
| `package_delivery.py` | Package a completed local run; requires completion status and local `runs/` |
| `package_text.py` | Export selected text files for delivery; not a training or inference entry point |

These scripts are not redundant aliases. Their paths are retained because launchers and packaging scripts refer to them.

## Retraining and report regeneration

Read [PLAN.md](PLAN.md) and [PROTOCOL.md](PROTOCOL.md) before starting. The original RKSIa data and prepared arrays are not included. From `Encoder/`, the preparation command is:

```bash
python -m trajectory_encoder.data --source "PATH_TO_RKSIA_DATA" --out prepared
```

Training stages also require the documented environment and benchmark/check outputs. `complete_local.py` writes training and report files; it is not a read-only verification command. Do not rename historical `experiment_logs/` to `runs/` to bypass missing training state. Saved reports can be read without rebuilding them.

## Evidence preservation

Keep candidate checkpoints, screening logs, and manifests: they support selection and sensitivity claims. Preserve historical manifests as records of their original execution rather than updating hashes to disguise later changes. Dataset-level pooled embeddings are not hourly scene data, and Encoder proxy performance does not establish controller-workload validity.

This organization pass adds navigation and local-cache ignore rules only. It does not alter model code, weights, training configuration, saved results, or scientific conclusions.
