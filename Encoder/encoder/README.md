# Current frozen model

[Encoder overview](../README.md)

| File | Purpose |
|---|---|
| `encoder.pt` | Strict-10-second, fixed-epoch-90 frozen checkpoint |
| `config.json` | Exported model/training metadata |
| `preprocess.json` | Training normalization, `stride_s=10`, `include_endpoint=false` |
| `example_input_output.npz` | Reference ENU input and token/trajectory outputs |
| [ATSCC.txt](ATSCC.txt) | Retained reference-code license |

Checkpoint SHA-256: `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`.
The original Python import and `Encoder/encoder/encoder.pt` path are retained
for `eval/` and `encode_scene.py`.

The exported `config.json` and `preprocess.json` describe this model. Run
`python Encoder/verify_delivery.py` from the repository root to verify its hash,
preprocessing and saved-example inference. Historical candidates, dataset-wide
embeddings, reports and training logs are not included in this delivery.
