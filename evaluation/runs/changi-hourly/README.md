# Changi hourly application case

Start with [report.md](report.md). Main output: a complete 24-hour time axis with accepted D, aircraft counts before/after whole-track QC, and explicit estimability. NA remains visible; a complete display is not a claim of 24 valid estimates.

## Publication scope

This folder contains only the report and PNG/SVG/PDF figures. The reporting code is in `evaluation/code/report_changi_hourly.py`. Embeddings, sampling assignments, complete D attempts and failure records, machine-readable QC counts, manifests and source audit records remain local. Raw observations, model weights and authentication information are also excluded. The report contains aggregate findings and hourly display tables, not downloadable underlying datasets.

## Rebuild from local evidence (no experiment)

```bash
python evaluation/code/report_changi_hourly.py --input /local/changi-saved-package --output /path/to/new-report
```

Requires NumPy and Matplotlib and the original local saved-data package. The output directory must not exist. No checkpoint, raw downloads, network access, inference, D calculation or resampling is required. The command checks all 48 full records and 6,200 saved draws against the summary. Cloning this repository alone does not supply the required inputs.

The local package must contain:

- `results/one-hour-summary.json`: the original 48 hourly records, including NA and subset summaries.
- `results/background-counts.json`: hourly counts before/after QC, mutually exclusive first-rejection counts and source-audit summaries.
- `results/DATE-1h-HH-all-attempts.json.gz`: the corresponding saved full fit and all attempted subset fits for each hour.

Set `CHANGI_HOURLY_INPUT` to this local package before running `python -m unittest discover -s evaluation/code -p "test_changi_hourly_report.py"`. Tests explicitly skip when the local data are unavailable. The data-backed checks verify saved counts, NA preservation, source audit accounting and output protection. All four passed before publication.

Superseded local report-text replacement scripts have been removed. `report_changi_hourly.py` is the sole current report builder. Original experiment execution code and historical results remain local provenance; they are not rerun to update the figures. Any regenerated `report-manifest.json` stays local; publish only the reviewed report and figures.

The existing whole-track screening policy is unchanged. The source audit's 849 repeated-timestamp rejections are aircraft-hour records, not unique aircraft over both days. Of these, 565 also have age/gap flags; the other 284 are not recovered or accepted tracks.
