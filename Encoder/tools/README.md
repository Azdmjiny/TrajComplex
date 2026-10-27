# Encoder tools

[Encoder overview](../README.md)

Use `example.py` and `verify_delivery.py` in the parent directory for frozen-model
inference and verification. These additional tools are for development and
historical training workflows.

| Tool | Purpose |
|---|---|
| `run_offline.py` | Offline launch of probe/check/benchmark/pipeline/finalize stages |
| `complete_local.py` | Historical training, export, diagnostics and reporting chain |
| `posthoc_diagnostics.py` | Diagnostics requiring prepared arrays and local training outputs |
| `make_report.py` | Regenerate the historical five-second report from local run outputs |
| `package_delivery.py` | List/package sources and experiment evidence |
| `package_text.py` | List/export publishable text sources and records |
| `offline_guard/` | Network guard used by the two launchers |

From the repository root, these commands inspect tools without starting training:

```bash
python Encoder/tools/complete_local.py --help
python Encoder/tools/run_offline.py --help
python Encoder/tools/package_delivery.py --list
python Encoder/tools/package_text.py --list --final
```

Tools locate the Encoder root from their file location, not the working directory.
Generated training state still uses local `Encoder/prepared/`, `runs/`, `reports/`
and `checkpoints/`; these are ignored by Git. They do not fall back to the immutable
archive as if archived records were a freshly completed local run. Packaging keeps
repository-relative `Encoder/...` paths, and creating a ZIP retains the original
requirement for a local `reports/completion_status.json` with `state=complete`.
Both the ZIP and text inventories include `Encoder/THIRD_PARTY_LICENSE_ATSCC.md`
and the merged source references in `Encoder/README.md`. The short `CITATION.md`
redirect preserves existing links without changing the repository-root README.

## Historical training limitation

The existing pipeline uses multi-candidate validation selection, including a
three-seed representative rule. The checked-in configuration describes a single
seed and a fixed 90-epoch 10-second model. These are different protocols; simply
running the old pipeline is not a verified reproduction of the current export.
The root [config.json](../config.json) and core training code are retained unchanged.
Training requires original data, prepared arrays and suitable CUDA hardware.
No training, report recomputation or checkpoint replacement is needed for this
directory organization or normal frozen-model inference.
