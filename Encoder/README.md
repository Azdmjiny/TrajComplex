# Trajectory Encoder

Frozen trajectory representations for downstream scene-complexity evaluation.
The current model takes ENU positions sampled every **10 seconds** and returns
**16-dimensional** token vectors and a sum-pooled trajectory vector.

## Quick start

Install the repository-root `requirements.txt`, then run from the repository root:

```bash
python Encoder/example.py
python Encoder/verify_delivery.py
```

Both scripts also work from `Encoder/` as `python example.py` and
`python verify_delivery.py`. Optional input/checkpoint arguments are relative to
your working directory; the bundled defaults are relative to the script.

```python
from Encoder.trajectory_encoder.inference import FrozenEncoder

encoder = FrozenEncoder("Encoder/encoder/encoder.pt", pooling="sum", device="cpu")
result = encoder.encode(enu_m)
embedding = result["embedding"]  # (16,)
tokens = result["tokens"]        # (T, 16)
```

Input must be a finite `(T, 3)` array in local ENU metres, sampled every 10 seconds,
with at least 30 points. The core API does not resample, convert geographic
coordinates, identify flights or assemble scenes. It uses the checkpoint's
training-set normalization; sum pooling does not apply additional L2 normalization.
Use the repository-root `encode_scene.py` to encode a folder of trajectories.

## Layout

| Path | Responsibility |
|---|---|
| `trajectory_encoder/` | Model, preprocessing, inference and training implementation |
| [encoder/](encoder/README.md) | Current frozen checkpoint, metadata and reference example |
| [tools/](tools/README.md) | Training launchers, diagnostics, reporting and packaging |
| [archive/](archive/README.md) | Saved experiment evidence, including the current model's records |

## Current model

| Setting | Value |
|---|---|
| Run | `encoder_10s_fixed90_seed43` |
| Sampling | Strict 10 seconds; no off-grid endpoint |
| Selection | Fixed epoch 90, seed 43 |
| Representation | 16 dimensions, sum pooling |
| Checkpoint SHA-256 | `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976` |
| Preprocessor ID | `52fabdb80ff5221882becc2e326e0e51089dbcf324a155bf7330f41442fa1477` |

See the [10-second results](archive/reports/RESULTS_10s_ZH.md),
[selection record](archive/reports/result/selection_10s.json), and
[export verification](archive/reports/result/export_verification.json).
`verify_delivery.py` checks the current export and nine archived candidate hashes,
preprocessing consistency, frozen loading, and saved-example inference on CPU.

The older five-second candidates and logs are separate historical experiments.
Their TEST scores do not apply to the current model. The current 10-second report
does not establish downstream intervention validity or controller workload.
Historical training tools are retained in [tools/](tools/README.md); they are not
a verified one-command reproduction of the current fixed-epoch model.

## Sources and citation

- **Data:** Thaweerath Phisannupawong, Joshua Julian Damanik, and Han-Lim Choi,
  *ATFMTraj: Aircraft Trajectory Classification Data for Air Traffic Management*
  (2024). [Author-provided dataset](https://huggingface.co/datasets/petchthwr/ATFMTraj),
  DOI [10.57967/hf/3356](https://doi.org/10.57967/hf/3356).
- **Method:** the same authors, *Aircraft Trajectory Segmentation-based Contrastive
  Coding: A Framework for Self-supervised Trajectory Representation*.
  [arXiv:2407.20028](https://arxiv.org/abs/2407.20028),
  DOI [10.1109/OJITS.2025.3574746](https://doi.org/10.1109/OJITS.2025.3574746).
- **Reference code:** [ATSCC, pinned commit
  789ccd72b7496b52e03df7d8599d8c9e6659bdb9](https://github.com/petchthwr/ATSCC/tree/789ccd72b7496b52e03df7d8599d8c9e6659bdb9).
  The retained license text is in [THIRD_PARTY_LICENSE_ATSCC.md](THIRD_PARTY_LICENSE_ATSCC.md).

The exact input files are identified by hashes in the
[data audit](archive/reports/result/data_audit.json), rather than the dataset's
current online version. Further preprocessing, supplied-paper and runtime-source
notes are preserved in the [archive](archive/README.md#source-and-preprocessing-notes).
