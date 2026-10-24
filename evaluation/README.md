# Evaluation

Start with the [current combined report](report.md). The latest results and their complete evidence are organized by study in [runs/](runs/README.md).

## Current status

- **Holding:** the equal-duration terminal control is complete. Both arms add 240 seconds / 24 strict-10-second samples. At the same archived cutoffs and jointly valid doses, median Spearman rho is 0.661 for Holding and 0.598 for straight flight. Six of seven comparable scene summaries have positive Holding-minus-Straight D differences. These are conditional descriptive results, not complete validation of operational complexity or elimination of duration confounding.
- **Vectoring:** fixed 5 km, unchanged reject-only checks; 21 candidates passed both sides across four scenes. Three scenes have no accepted D. The fourth has mixed correlation signs. Fixing baseline fitting scales changes one full six-dose curve from +0.771 to −0.319, showing scale-selection sensitivity. No stable strong positive relationship has been established.
- Rejected D values stay unavailable. Complete dose curves, all scenes, negative correlations, and the historical cutoff source are retained. Orders are within-scene repeats, not independent scenes.

## Navigation

| Location | Contents |
|---|---|
| [report.md](report.md) | Current conclusions and comparison tables |
| [runs/README.md](runs/README.md) | Links to every new result package and publication/reproduction limits |
| [code/README.md](code/README.md) | Current explicit-input screening, inference, diagnostic and report commands; fixed 10-second policy |
| `results/`, `figures/`, `reports/` | Earlier evaluation files and implementation records; use run-specific manifests to identify their methods |

The latest strict-10-second outputs are in `runs/`; older root-level `results/` and `figures/` must not be mistaken for them. The original twelve-scene strict-10-second results used by the control are included under `runs/strict-10s-reference/`.

No raw data, model weights or authentication caches are added by this publication. Original local artifacts remain available. Reports are in English; figures are supplied as PNG and SVG.

## Current code entrypoints

The old implicit all-experiments runner is replaced. Use `python evaluation/code/run_evaluation.py --help` and the [code guide](code/README.md). Vectoring consumes frozen accepted pairs; Holding uses the approved terminal equal-duration pair. Both require an explicit local 10-second checkpoint with the recorded SHA-256. Raw sources and weights are not downloaded or substituted automatically.

Common-cutoff and fixed-scale diagnostics are explicit subcommands. `refresh_outputs.py --output NEW_DIRECTORY` exports saved-statistics summaries without overwriting this report or published results. The underlying fitted-reference, direction certificate, continuous peak feedback, QC and physical/numerical thresholds are unchanged. Historical source snapshots in `runs/*/source/` remain execution provenance, not current entrypoints.

Software verification: 78 regression tests passed, including exact saved fixed-scale replay. No observational evaluation or training was rerun for the code replacement.
