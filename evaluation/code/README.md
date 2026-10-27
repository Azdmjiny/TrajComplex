# Shared evaluation code

Topic code has moved to [Holding](../holding/code/README.md),
[Vectoring](../vectoring/code/README.md), and [hourly](../hourly/code/README.md).

| Files | Role |
|---|---|
| `evaluation_layout.py` | Topic imports, named study paths, historical-path lookup, output protection |
| `evaluation_runtime.py`, `run_evaluation.py` | Explicit workflow dispatch and frozen 10 s checkpoint checks |
| `position_timeline.py`, `trajectory_quality.py` | Shared source-time alignment and baseline QC |
| `truncation.py`, `run_analysis.py`, `postprocess_results.py` | Saved-record statistics and identical-cutoff postprocessing |
| `build_report.py`, `refresh_outputs.py`, `make_figures.py` | Historical endpoint/5 km summary export, not the latest authored primary report |
| `make_review_figures.py` | Earlier endpoint/19-candidate cross-study presentation |
| `test_*.py` | Cross-study software and saved-record regression checks |
| `check_layout.py` | Read-only organization, navigation, syntax and immutable-evidence checks |

Examples from the repository root (use `--help` before a new run):

```bash
python evaluation/code/run_evaluation.py --help
python evaluation/holding/code/plot_holding_primary.py --help
python evaluation/hourly/code/report_changi_hourly.py --help
python evaluation/code/check_layout.py
```

The frozen strict-10s checkpoint SHA-256 is
`bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`.
Keep checkpoints and local saved-data inputs outside the repository. Numerical
screening also needs `../requirements-screening.txt`. No dependency version or
scientific threshold changed during organization.

Historical `source/` snapshots retain their exact bytes and original workspace
paths. The former `check_consistency.py` is archived under
`../histry/legacy-audit-source/`: it targets an old report layout and is not a
current whole-repository audit. Existing historical audit JSON is also a snapshot.


Shared code remains in this directory; no import-root move is required. The
mixed strict-10s source now resolves to `../histry/strict-10s-reference/` through
`evaluation_layout.study_path`. The combined report is in `../report/report.md`.
Old `runs/` paths in immutable manifests resolve through the historical map.
