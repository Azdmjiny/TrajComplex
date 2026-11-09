# Trajectory encoder

The frozen encoder maps each eligible aircraft trajectory to a 16-dimensional vector. It accepts local ENU coordinates in metres sampled every 10 seconds, with at least 30 points, and uses temporal sum pooling.

## Use

Install the repository requirements and run commands from the repository root:

```bash
python Encoder/example.py
python Encoder/verify_delivery.py
```

For an array already loaded as `enu_m` with shape `(T, 3)`:

```python
from Encoder.trajectory_encoder.inference import FrozenEncoder

encoder = FrozenEncoder("Encoder/encoder/encoder.pt", pooling="sum", device="cpu")
result = encoder.encode(enu_m)
embedding = result["embedding"]  # (16,)
tokens = result["tokens"]        # (T, 16)
```

Coordinates, timestamps, flight identity, quality filtering, and scene construction must be prepared upstream. The inference API does not resample or convert coordinates. Normalization statistics and preprocessing settings are loaded from the checkpoint.

## Model bundle

| Setting | Value |
|---|---|
| Training source | WSSS arrivals, March–May 2025 |
| Selected checkpoint epoch | 60 |
| Dimensions and pooling | 16, sum |
| Sampling interval | 10 seconds; endpoint excluded |
| Checkpoint SHA-256 | `c0d98e6cde14baf99d28b7d336c282eb245f1ce485c248c32a58fd9ccf5358e5` |
| Preprocessor ID | `cee1251c8b373994d009bcda89ee14811623849e762f858b0abe0bb7fbd5b8a5` |

The files under [`encoder/`](encoder/README.md) contain the checkpoint, its configuration, a known-input/known-output example, and the retained ATSCC license.

The encoder is a representation component. Its output alone does not establish intervention validity, operational complexity, or controller workload.

## Source

The implementation adapts the [ATSCC reference code](https://github.com/petchthwr/ATSCC/tree/789ccd72b7496b52e03df7d8599d8c9e6659bdb9). The applicable license text is included at [`encoder/ATSCC.txt`](encoder/ATSCC.txt).
