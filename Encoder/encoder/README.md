# Current frozen model

[Encoder overview](../README.md)

| File | Purpose |
|---|---|
| `encoder.pt` | Strict-10-second, fixed-epoch-90 frozen checkpoint |
| `config.json` | Exported model/training metadata |
| `preprocess.json` | Training normalization, `stride_s=10`, `include_endpoint=false` |
| `example_input_output.npz` | Reference ENU input and token/trajectory outputs |

Checkpoint SHA-256: `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`.
The original Python import and `Encoder/encoder/encoder.pt` path are retained
for `eval/` and `encode_scene.py`.

Evidence: [export verification](../archive/reports/result/export_verification.json),
[selection](../archive/reports/result/selection_10s.json), and
[training report](../archive/reports/training-report-10s.md).
The old dataset-wide embeddings are preserved in
[archive/encoder/](../archive/encoder/); they are not outputs of this checkpoint
and are not an hourly scene archive.
