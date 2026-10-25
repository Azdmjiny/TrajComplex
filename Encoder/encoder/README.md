# Selected Encoder export

[Encoder overview](../README.md)

- `encoder.pt`: the frozen strict-10-second, epoch-90 checkpoint used by the
  evaluation workflow. SHA-256
  `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`.
- `config.json` and `preprocess.json`: exported 10-second training and
  preprocessing metadata. `preprocess.json` has `stride_s=10` and
  `include_endpoint=false`.
- `example_input_output.npz`: reference 10-second input and output for
  inference verification.
- `embeddings-5s-old.npz`: the previous whole-dataset pooled export. It belongs
  to the older five-second checkpoint and is retained only as provenance; it
  is **not** the output of the current `encoder.pt`.

Checkpoint provenance: [export_verification.json](../reports/result/export_verification.json),
[selection_10s.json](../reports/result/selection_10s.json) and
[training-report-10s.md](../reports/training-report-10s.md). The selected
export matches the checkpoint required by `evaluation/code/evaluation_runtime.py`
(SHA-256 `bc1e0d74…`, preprocessor `52fabdb8…`).
