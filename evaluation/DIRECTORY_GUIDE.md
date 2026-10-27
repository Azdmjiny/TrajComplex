# Evaluation directory guide

Updated 2026-10-27 after merging the remote branch and publishing the latest maneuver work. This is an inventory, not a directory reorganization. Directory names are experiment packages, not Git branches.

## Start here

- [report.md](report.md): combined current interpretation, with separate upstream hourly analyses retained.
- [holding-midpoint-response.md](holding-midpoint-response.md): current Holding midpoint R²≥0.94, archived pre-peak ranges and full-range appendix.
- [runs/vectoring-20s-repaired/report.md](runs/vectoring-20s-repaired/report.md): current Vectoring, repaired 20-second version with 26 candidates.
- [holding-paper-appendix.md](holding-paper-appendix.md): separate endpoint equal-duration control and complete ranges.
- [holding-version-comparison.md](holding-version-comparison.md): distinctions among old pilot, midpoint and endpoint experiments.
- [vectoring-study-history.md](vectoring-study-history.md): development history; old 5 km findings are labelled historical.

## Top-level directories

| Directory | Purpose | Important distinction |
|---|---|---|
| [code/](code/README.md) | Current screening/generation, inference interfaces, postprocessing, figure/report builders and software tests | Also contains some older diagnosis/preview renderers; not every script is an experiment entrypoint |
| [figures/](figures/README.md) | Shared Holding figures, older Vectoring/combined views and figure captions | Latest Vectoring figures live in its run package; older combined figures use different experiments |
| [runs/](runs/README.md) | Per-study reports, figures and execution snapshots | Historical packages include published results; new maneuver packages publish code/reports/figures only |
| [archive/](archive/) | Superseded 5 km reports, original endpoint overview, midpoint 0.98 presentation and legacy snapshots | Historical evidence; do not treat as current settings or primary findings |

## Run packages

| Package/report | Role | Contents | Subdirectories |
|---|---|---|---|
| [changi-hourly](runs/changi-hourly/report.md) | Application main | Deduplicated September 8/11 1h D/count/status; original input version in appendix-original. | `appendix-original/`, `figures/` |
| [changi-n-scaling](runs/changi-n-scaling/report.md) | Separate upstream pilot | One-scene D versus aircraft count; nested subsampling. | `figures/`, `results/`, `source/` |
| [changi-thresholds](runs/changi-thresholds/report.md) | Separate upstream sensitivity | 3h/1h alternate thresholds, assigned low-N floor; not the original 1h settings. | `figures/`, `results/`, `source/` |
| [four-scene-vectoring-evaluation](runs/four-scene-vectoring-evaluation/report.md) | Historical 5 km evaluation | Earlier four-scene full-range D results; first three scenes failed the old fit gate. | `figures/`, `results/`, `source/` |
| [four-scene-vectoring-screen](runs/four-scene-vectoring-screen/report.md) | Historical screening | Original four-scene 5 km evidence/fitting/geometry checks; 21 of 26 candidate identities. | `screening/`, `source/` |
| [holding-equal-duration](runs/holding-equal-duration/report.md) | Control experiment | Endpoint +240 s Holding versus straight continuation; paired comparisons, full range. | `figures/`, `results/`, `source/` |
| [holding-equal-duration-old-cutoff](runs/holding-equal-duration-old-cutoff/report.md) | Control postprocessing | The same archived cutoff is applied to both endpoint arms; no new trajectories. | `figures/`, `results/`, `source/` |
| [opensky-30d-no-gate](runs/opensky-30d-no-gate/report.md) | Separate upstream analysis | Thirty-day raw log–log slopes, N scaling, day/night and floor displays; not quality-gated D. | `figures/`, `results/`, `source/` |
| [segmented-15km](runs/segmented-15km/README.md) | Historical reference | Original 19-candidate 10-second quality-matching study; segmented and smooth 15 km. | `figures/`, `population/`, `results/`, `source/` |
| [strict-10s-reference](runs/strict-10s-reference/report.md) | Historical source | Twelve-scene strict-10-second midpoint evaluation; saved Holding fits and cutoffs underlie the current 0.94 presentation. | `results/` |
| [vectoring-20s-repaired](runs/vectoring-20s-repaired/report.md) | Latest Vectoring | 26 versus 25 candidates; same settings and full dose ranges; both segmented and smooth. | `figures/`, `source/` |
| [vectoring-certificate-repair](runs/vectoring-certificate-repair/report.md) | Latest numerical repair | Stable certificates, failure classification, solver feedback and screening; no correlation in this stage. | `figures/`, `source/` |
| [vectoring-existing-result-diagnosis](runs/vectoring-existing-result-diagnosis/report.md) | Historical diagnosis | Saved fitting scales, pair-count boundaries and aircraft/side steps; no new intervention. | `figures/`, `source/` |
| [vectoring-fixed-baseline-scales](runs/vectoring-fixed-baseline-scales/report.md) | Historical estimator diagnostic | Fourth scene with baseline fitting scales fixed; not a new route-generation experiment. | `figures/`, `results/`, `source/` |
| [vectoring-time-window-sensitivity](runs/vectoring-time-window-sensitivity/report.md) | Earlier sensitivity | 10/15/20-second quality matching; 19/22/25 candidates, before latest repair. | `figures/`, `source/` |

Within older packages, `results/` holds already published statistics/embeddings and manifests; `population/` and `screening/` hold the published candidate/evidence records available in that package; `source/` contains exact execution snapshots, often with local paths; `figures/` contains presentation artifacts. A report may reference local-only arrays that were never uploaded. `changi-hourly/appendix-original/` is the original-data comparator, with its own report and figures.

## Code groups

| Group | Main files | Use |
|---|---|---|
| Shared execution | `run_evaluation.py`, `evaluation_runtime.py` | Explicit-input workflow dispatch and paths |
| Holding generation/control | `run_holding_eval.py`, `evaluate_holding_control.py`, `analyze_common_cutoff.py` | Holding intervention, equal-duration control and common-cutoff analysis |
| Holding current presentation | `audit_holding_r2_sensitivity.py`, `plot_holding_primary.py` | Re-screen saved fits at 0.94 and produce current figures |
| Holding historical/diagnostic views | `plot_holding_midpoint_response.py`, `plot_holding_historical_ranges.py`, `plot_holding_six_scene_preview.py`, `diagnose_holding_mean_composition.py`, `make_holding_main.py` | Earlier gates, selected previews, mean-composition diagnosis and endpoint eight-scene view |
| Vectoring evidence/reference | `vectoring_inputs.py`, `position_timeline.py`, `trajectory_quality.py`, `vectoring_uncertainty.py`, `vectoring_reference.py` | Input timing, basic QC, quality evidence and reference fitting/certification |
| Vectoring generation/screening | `vectoring_path.py`, `vectoring_certification.py`, `vectoring_population.py`, `screen_vectoring_candidates.py`, `screen_approved_scenes.py` | Routes, continuous checks, solver feedback and population/candidate separation |
| Vectoring evaluation/diagnosis | `run_vectoring_eval.py`, `evaluate_saved_vectoring.py`, `diagnose_fixed_scales.py`, `audit_vectoring_missing_quality.py` | Evaluation helpers, scale diagnostics and cached evidence audit |
| Reporting/postprocessing | `postprocess_results.py`, `run_analysis.py`, `build_report.py`, `make_figures.py`, `refresh_outputs.py`, `make_review_figures.py` | Saved-result processing; some builders target historical report layouts |
| Hourly reporting | `report_changi_hourly.py`, `hourly_report_text.py` | Deduplicated main result and original appendix from private saved records |
| Validation | `test_*.py`, `check_consistency.py` | Regression tests; the older consistency checker targets the historical publication snapshot, not every later report layout |

The Encoder and D estimator implementation live outside this folder. No model weights or newly generated derived arrays are added in this publication.

## Archive and administrative files

- `archive/holding-midpoint-r098/`: the previous midpoint report and its three figure sets at R²≥0.98.
- `archive/legacy-before-workflow-integration/committed/` and `local/`: distinct older result/code/report snapshots; the archive README and inventories explain provenance.
- `archive/report-5km-2026-10-24.md` and `README-5km-2026-10-24.md`: superseded root documentation.
- `archive/holding-all-scenes-dose-2026-10-26.*`: the older complete endpoint-control overview, moved by the existing upstream update.
- `STAR_INACTIVE.md`: why STAR-related material is not active.
- `requirements-screening.txt`, `.gitattributes`: dependency/formatting configuration.
- `maintenance-checks.json`, `runs/publication-manifest.json`, `runs/publication-checks.json`: historical audit snapshots, not a live claim about all later additions.

## Organization issues to review before a later cleanup

1. Shared figures and per-run figures coexist; combined figures can use different gates, insertion locations or matching windows.
2. Primary Holding reports are at the root, while current Vectoring reports are under `runs/`.
3. Current entrypoints and diagnostic/preview scripts coexist in `code/`; execution snapshots also live in `runs/*/source/` and sometimes `figures/`.
4. The root report collects several independent hourly designs, including alternate thresholds and raw slopes. Their settings must remain separate from quality-gated maneuver results.
5. Earlier immutable audit manifests/checkers refer to old snapshots and can appear stale if mistaken for current whole-repository checks.

No folders are moved or deleted to address these issues in this update.

## Source files by run

### changi-hourly

Report entry: [report.md](runs/changi-hourly/report.md).

Execution/analysis snapshots: No run-local Python source; see `evaluation/code/`.

### changi-n-scaling

Report entry: [report.md](runs/changi-n-scaling/report.md).

Execution/analysis snapshots: `source/make_figure.py`, `source/run_d_vs_n.py`

### changi-thresholds

Report entry: [report.md](runs/changi-thresholds/report.md).

Execution/analysis snapshots: `source/make_figures.py`, `source/run_thresholds.py`

### four-scene-vectoring-evaluation

Report entry: [report.md](runs/four-scene-vectoring-evaluation/report.md).

Execution/analysis snapshots: `source/report_and_verify.py`, `source/run.py`

### four-scene-vectoring-screen

Report entry: [report.md](runs/four-scene-vectoring-screen/report.md).

Execution/analysis snapshots: `source/run_screen.py`, `source/verify_and_report.py`

### holding-equal-duration

Report entry: [report.md](runs/holding-equal-duration/report.md).

Execution/analysis snapshots: `source/report_and_verify.py`, `source/run.py`

### holding-equal-duration-old-cutoff

Report entry: [report.md](runs/holding-equal-duration-old-cutoff/report.md).

Execution/analysis snapshots: `source/analyze.py`

### opensky-30d-no-gate

Report entry: [report.md](runs/opensky-30d-no-gate/report.md).

Execution/analysis snapshots: `source/compute_d_vs_n.py`, `source/daynight/analyze2.py`, `source/daynight/make_boxplot.py`, `source/daynight/make_figures.py`, `source/encode_all.py`, `source/make_figures.py`, `source/make_truncated_24h.py`

### segmented-15km

Report entry: [README.md](runs/segmented-15km/README.md).

Execution/analysis snapshots: `source/compare.py`, `source/generate_population.py`, `source/make_paper_figures.py`, `source/run_eval.py`

### strict-10s-reference

Report entry: [report.md](runs/strict-10s-reference/report.md).

Execution/analysis snapshots: No run-local Python source; see `evaluation/code/`.

### vectoring-20s-repaired

Report entry: [report.md](runs/vectoring-20s-repaired/report.md).

Execution/analysis snapshots: `source/report_results.py`, `source/run_evaluation.py`, `source/verify_results.py`

### vectoring-certificate-repair

Report entry: [report.md](runs/vectoring-certificate-repair/report.md).

Execution/analysis snapshots: `source/report_screening.py`, `source/screen_saved.py`

### vectoring-existing-result-diagnosis

Report entry: [report.md](runs/vectoring-existing-result-diagnosis/report.md).

Execution/analysis snapshots: `source/analyze.py`

### vectoring-fixed-baseline-scales

Report entry: [report.md](runs/vectoring-fixed-baseline-scales/report.md).

Execution/analysis snapshots: `source/analyze.py`

### vectoring-time-window-sensitivity

Report entry: [report.md](runs/vectoring-time-window-sensitivity/report.md).

Execution/analysis snapshots: `source/report_results.py`, `source/run_evaluation.py`, `source/screen_routes.py`
