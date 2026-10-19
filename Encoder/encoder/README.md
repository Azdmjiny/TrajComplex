# Selected Encoder export

[Encoder overview](../README.md)

- `encoder.pt`: selected frozen checkpoint, loaded by `FrozenEncoder`.
- `config.json` and `preprocess.json`: exported configuration and preprocessing metadata.
- `example_input_output.npz`: reference input and output for inference verification.
- `embeddings.npz`: whole-dataset pooled representations, not an hourly scene archive.

These delivered files are tracked. Do not remove them as local training caches. Checkpoint provenance is in [export_verification.json](../reports/export_verification.json); the byte-level distinction from the evaluation checkpoint is documented in the [overview](../README.md).
