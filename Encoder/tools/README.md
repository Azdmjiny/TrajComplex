# Encoder tools

[Encoder overview](../README.md)

These tools package the current frozen model and inference implementation.

| Tool | Purpose |
|---|---|
| `package_delivery.py` | List files or create a standalone inference ZIP |
| `package_text.py` | List/export text sources and model metadata as JSON |

From the repository root:

```bash
python Encoder/tools/package_delivery.py --list
python Encoder/tools/package_delivery.py
python Encoder/tools/package_text.py --list
python Encoder/tools/package_text.py
```

The default ZIP is `Encoder/encoder_delivery.zip`. Use `--output PATH` to choose
a different destination; its parent directory must exist. Existing ZIP files
are not overwritten. Tools locate sources from their own file location, so they
also work from `Encoder/` using `python tools/package_delivery.py`.

The ZIP contains `Encoder/` inference sources, tools, model files and the repository
`requirements.txt`, with repository-relative paths. Extract it, install the
requirements, then run `python Encoder/verify_delivery.py` to check the model.
Both inventories include `Encoder/encoder/ATSCC.txt` and the source references
in `Encoder/README.md`. Text export excludes the binary checkpoint and example.
Packaging does not require training state, experiment logs or reports.
