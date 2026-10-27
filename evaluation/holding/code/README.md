# Holding code

Current figure builder: `plot_holding_primary.py --output NEW_DIRECTORY` reads
saved midpoint fits and applies the user-selected R² >= 0.94 gate. It does not
rerun inference or fit D. `audit_holding_r2_sensitivity.py` supplies the saved-fit
screen. `run_holding_eval.py` contains midpoint and endpoint geometry helpers;
`evaluate_holding_control.py` is the explicit equal-duration runner;
`analyze_common_cutoff.py` applies the identical archived cutoff to both arms.

Historical/diagnostic renderers: `plot_holding_midpoint_response.py` (0.98 and
shared plotting helpers), `plot_holding_historical_ranges.py` (endpoint ranges),
`plot_holding_six_scene_preview.py` (selected preview), and
`diagnose_holding_mean_composition.py` (membership of the dose mean).
They are not interchangeable primary results.

Run from the repository root, for example:

```bash
python evaluation/holding/code/plot_holding_primary.py --help
python evaluation/code/run_evaluation.py holding-control --help
```

Shared paths and imports are handled by `../../code/evaluation_layout.py`.
