# Encoder checkpoint files

| File | Purpose |
|---|---|
| `encoder.pt` | Frozen WSSS trajectory encoder, selected at epoch 60 |
| `config.json` | Model settings, preprocessing identity, and checkpoint provenance |
| `example_input_output.npz` | ENU trajectory and its expected pooled vector for delivery verification |
| `ATSCC.txt` | License for the retained reference-code components |

Checkpoint SHA-256: `c0d98e6cde14baf99d28b7d336c282eb245f1ce485c248c32a58fd9ccf5358e5`.

Run `python Encoder/verify_delivery.py` from the repository root to check the checkpoint hash, preprocessing ID, frozen inference mode, and saved example output.
