# Evaluation code

These scripts reproduce the pilot analysis in the sibling `results/`, `figures/`, and `reports/` folders. They require the repository source, the local OpenSky archive, and the trained encoder checkpoint. The raw data and checkpoint are intentionally not stored in this repository.

## Inputs

In PowerShell, set these environment variables before running the analysis:

- `ATM_DATA_ZIP`: path to `OpenSky_Changi_2026-09.zip`.
- `ATM_ENCODER_CHECKPOINT`: path to the trained `encoder.pt` checkpoint.

Example (replace the paths with your local locations):

```powershell
$env:ATM_DATA_ZIP = 'D:\data\OpenSky_Changi_2026-09.zip'
$env:ATM_ENCODER_CHECKPOINT = 'D:\models\encoder.pt'
```

Run commands from the repository root. Install dependencies from the repository `requirements.txt`; the evaluation scripts also use SciPy and Pillow.

## Reproduction order

1. `python evaluation/synthetic-trajectory-complexity/code/audit_opensky.py` to regenerate the full-month eligibility audit. The checked-in audit JSON can be reused when only rerunning later stages.
2. `python evaluation/synthetic-trajectory-complexity/code/run_holding_eval.py`
3. `python evaluation/synthetic-trajectory-complexity/code/summarize_holding_eval.py`
4. `python evaluation/synthetic-trajectory-complexity/code/run_vectoring_eval.py`
5. `python evaluation/synthetic-trajectory-complexity/code/summarize_vectoring.py`
6. `python evaluation/synthetic-trajectory-complexity/code/aircraft_count_sensitivity.py`
7. `python evaluation/synthetic-trajectory-complexity/code/count_plot_report.py`
8. `python evaluation/synthetic-trajectory-complexity/code/update_report.py` and `python evaluation/synthetic-trajectory-complexity/code/patch_report.py` add provenance and the data-audit note to the report.

`run_vectoring_eval.py` uses the holding run’s selected hourly scenes and requires its JSON output. The analysis scripts keep the previously used experiment settings; path handling was changed so inputs are supplied locally and outputs go into this evaluation folder. These pilot results are synthetic sensitivity checks, not validation against real operational complexity labels.
