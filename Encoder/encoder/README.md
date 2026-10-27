# Current frozen model

[Encoder overview](../README.md)

| File | Purpose |
|---|---|
| `encoder.pt` | Strict-10-second, fixed-epoch-90 frozen checkpoint |
| `config.json` | Exported model/training metadata |
| `example_input_output.npz` | Reference ENU input and token/trajectory outputs |
| [ATSCC.txt](ATSCC.txt) | Retained reference-code license |

Checkpoint SHA-256: `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`.
The original Python import and `Encoder/encoder/encoder.pt` path are retained
for `eval/` and `encode_scene.py`.

The exported `config.json` describes this model. Inference and verification read
feature order, normalization and sampling parameters directly from the
`preprocess` entry in `encoder.pt`. Verification checks its preprocessor ID
against `config.json`, the checkpoint hash and the saved reference outputs.
Training provenance fields describe the original export and are not runtime
file dependencies.

Run `python Encoder/verify_delivery.py` from the repository root to verify its hash,
preprocessing and saved-example inference. Historical candidates, dataset-wide
embeddings, reports and training logs are not included in this delivery.
