# Evaluation

The [current report](reports/evaluation-pilot.md) presents corrected Holding geometry, trajectory quality filtering, exploratory Holding truncation, full-range Vectoring results, and aircraft-count sensitivity.

Only the current result set is maintained here. Superseded files are available in Git history. Complete dose curves, including the declining Holding segments, remain in the canonical data; truncation changes which points enter the correlation calculation, not the stored observations.

## Interpretation

- Holding peak truncation uses the same outcomes being evaluated. It is exploratory, not independent validation or evidence that the declining segment is invalid.
- Vectoring uses its full dose range. Positive correlation describes a response to synthetic trajectory deformation, not validated controller workload.
- Five injection orders per hour are within-scene repeats, not five independent scenes.
- Holding adds 48 five-second samples. Length and sum pooling remain confounded.
- Candidate radii are fixed within each scene, but the actual fitted radius interval can change with dose. Failed D estimates are excluded, not replaced by zero.
- `safe` denotes candidate maneuver speed screening only; it does not certify physical feasibility.

## Layout

| Directory | Contents |
| --- | --- |
| `code/` | Experiment runner, geometry and filtering modules, analysis, plotting, report generation, and tests |
| `results/` | Canonical full-dose data, consolidated statistics, selection records, sensitivity data, and provenance |
| `figures/` | Current figures in PNG and SVG formats and their index |
| `reports/` | Current Markdown report |

### Canonical result files

- [experiment-results.json](results/experiment-results.json): complete corrected dose curves for every QC variant. Primary Holding: `qc500.holding`; primary Vectoring: `qc500_safe.vectoring`.
- [summary.json](results/summary.json): full-range and retained-range statistics, paired comparisons, hour-level summaries, and count sensitivity.
- `results/*-point-selection.csv`: dose-level inclusion decisions and exclusion reasons for each variant.
- [aircraft-count-sensitivity.json](results/aircraft-count-sensitivity.json): count sensitivity summaries and individual subsamples; the CSV is a tabular export of those subsamples.
- [quality_audit.json](results/quality_audit.json) and [injected_geometry_audit.json](results/injected_geometry_audit.json): trajectory rejections and candidate maneuver speed diagnostics.
- [run-manifest.json](results/run-manifest.json): provenance of the saved inference run. Its source hashes describe the code at execution time, before later repository cleanup.
- [analysis-manifest.json](results/analysis-manifest.json): input hashes and source hashes for the latest regenerated analysis.

`legacy_replay` inside the aircraft-count data is the pre-QC reference used by the current sensitivity comparison, not an obsolete Holding or Vectoring result. It is retained so the current figure remains reproducible. Duplicate per-maneuver `pilot`/`summary` JSON files and duplicate CSV aliases are no longer generated.

## Regenerate statistics, figures, and report

Run from the repository root with Python, NumPy, SciPy, and Matplotlib installed:

```bash
python evaluation/code/refresh_outputs.py
```

This overwrites the current summaries, selection CSVs, figures, and Markdown report. It does not run Encoder inference and needs no raw archive, checkpoint, or GPU. The full-dose and aircraft-count JSON files are the inputs.

## Rerun from raw trajectories

Install the repository dependencies, including PyTorch. Set `ATM_DATA_ZIP` to the OpenSky archive and `ATM_ENCODER_CHECKPOINT` to the frozen checkpoint, then run:

```bash
python evaluation/code/run_evaluation.py
python evaluation/code/refresh_outputs.py
```

The checkpoint SHA256 must match the value frozen in `run_evaluation.py`. The runner preserves the same 12 hours and random seeds. Original aircraft order and Vectoring direction are generated before filtering, preserving surviving aircraft order across QC variants.

To rerun only aircraft-count sensitivity:

```bash
python evaluation/code/run_evaluation.py --counts-only
python evaluation/code/refresh_outputs.py
```

`run_holding_eval.py` and `run_vectoring_eval.py` are helper modules used by the unified runner, not separate command-line entry points. Raw trajectories, checkpoints, and inference caches are not distributed here.

## Validation

```bash
python -m unittest discover -s evaluation/code -p "test_*.py" -v
```

Tests cover natural Holding closure, speed continuity on a straight reference trajectory, raw trajectory screening, Vectoring candidate screening, shared peak selection, minimum valid repeats, and exclusion of invalid D values. Geometry tests do not load the model.
