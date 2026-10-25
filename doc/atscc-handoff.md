# Current Encoder-to-complexity interface handoff

This note replaces the old ATSCC framework handoff; its filename is retained for existing links. Current code lives in `Encoder/` and lowercase `complexity/`. Legacy ATSCC object interfaces are no longer the entry points; root-level `encode_scene.py` remains a valid scene-encoding CLI. Use the actual case of module names and paths for Linux compatibility.

## Current model and entry points

- Frozen model: `Encoder/encoder/encoder.pt`, corresponding to `d16_e120_t0p01_s43`, 16 dimensions, sum pooling, seed 43, epoch 30. The current repository includes this exported checkpoint; see the Encoder README for its distinction from the separately recorded evaluation checkpoint.
- Backbone: nine input features, width 256, four layers, four heads, FFN 512; per-token L2, with no additional L2 on pooled embeddings.
- Imports from the repository root: `from Encoder.trajectory_encoder.inference import FrozenEncoder` and `from complexity import estimate_complexity`.
- Examples run inside `Encoder/` still use `from trajectory_encoder.inference import FrozenEncoder`; see `Encoder/example.py`.
- Complexity directly depends only on NumPy/SciPy. Install the full project's root `requirements.txt`, which also includes Torch. See the [root README](../README.md#installation), [Encoder section](../README.md#encoder), [PLAN.md](../Encoder/PLAN.md), and [PROTOCOL.md](../Encoder/PROTOCOL.md) for installation and retraining.

## Input and preprocessing contract

`FrozenEncoder.encode(enu_m)` processes one trajectory already sampled at five-second intervals:

- A finite real `(T,3)` array in ENU metres; latitude/longitude/altitude, NaN padding, and Inf are not accepted.
- The interface does not resample; at least 30 points are required.
- Features are `[east,north,up,direction_e,direction_n,direction_u,radius,sin(theta),cos(theta)]`, standardized using training means/stds stored in the checkpoint without refitting. Direction uses forward differences, repeating the final direction.
- The returned dictionary includes `tokens: (T,16)`, `embedding: (16,)`, `n_points`, `pooling`, and `preprocessor_id`. Supported pooling modes are `sum`, `mean`, and `gem2` (signed GeM-p2).
- Weights load with strict state_dict matching; the model is put in eval mode with frozen parameters. The loader uses `torch.load(..., weights_only=False)`: load only trusted checkpoints. Legacy bare state_dict adaptation is not provided.

## Connecting trajectories to complexity

Pass an `(N,16)` array, not token sequences, the output dictionary, or a single `(16,)` vector. An empty scene can be `(0,16)`. Insufficient samples or unacceptable fits return `unestimable`, not zero complexity. See the [method note](trajectory-embedding-point-cloud-complexity.md) for default gates, explicit scales, and interpretation limits.

Save a single hour as `.npy`, or multiple hours as a `.npz` mapping `scene_id -> (N_s,D)`:

```python
np.savez("hours.npz", hour_01=z1, hour_02=z2)
```

```bash
python -m pip install -r requirements.txt
python -m complexity --help
python -m complexity hour_01.npy -o hour_01.complexity.json
python -m complexity hours.npz -o hours.complexity.json
```

**`Encoder/encoder/embeddings.npz` is not an hourly scene archive.** It stores all 16183 trajectories under `sum/mean/gem2`; it cannot be treated as multi-hour input or three pooling modes as three scenes. Fix the checkpoint, preprocessing, pooling, normalization, and scale rules across comparisons. Do not lower quality gates merely to obtain a number.

## Training evidence

Per-epoch logs for the current model are in `Encoder/experiment_logs/d16_e120_t0p01_s43/`. `history.json` records training/validation loss; `status.json` records completion and the best epoch; `validation.json` and `untrained_validation.json` provide validation representation assessments.

Held-out TEST results and baselines are in `Encoder/reports/result/test_results.json`, `untrained_test_results.json`, and `confounding_and_route.json`. See [RESULTS_5s_ZH.md](../Encoder/reports/RESULTS_5s_ZH.md) for the historical five-second summary, and `three_seed_summary.json` and `probe_summary.csv` for seed/pooling comparisons. The current export is the [10-second model](../Encoder/reports/RESULTS_10s_ZH.md).

Decreasing training loss does not establish downstream complexity validity. The representative model does not outperform the stronger of the two baselines on any of the four geometric proxies, so additional proxy-prediction capability from training has not been established. The training data lack absolute timestamps and real flight IDs and cannot alone validate real hourly scenes. A separate OpenSky synthetic-perturbation study is described in the [evaluation report](../evaluation/report.md); it has not validated real controller workload.

## Verification commands

From the repository root, use Python with the required dependencies installed. The last two commands also require complete local Encoder delivery files; a source-only copy is insufficient:

```bash
python -m unittest discover -s complexity/tests -v
python Encoder/verify_delivery.py
python Encoder/example.py --checkpoint Encoder/encoder/encoder.pt --input Encoder/encoder/example_input_output.npz
```

The first command covers the complexity algorithm and single/multi-scene CLI. The other two check weight hashes, frozen loading, and real-trajectory inference; they do not replace research validation on real hourly scenes. `Encoder/trajectory_encoder/checks.py` additionally requires prepared data and CUDA and is not a CPU-only delivery-verification command.
