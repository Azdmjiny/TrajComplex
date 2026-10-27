# Current evaluation code

## Vectoring certificate repair (2026-10-27)

`vectoring_path.py` now delegates continuous motion and projection verification
to `vectoring_certification.py`. Derivative polynomials survive subdivision;
same-parameter Bernstein products tighten the projection convexity enclosure;
both reference and query intervals can be refined. Witnessed branch conflicts,
motion violations, unresolved numerical precision and exhausted work budgets
have separate rejection reasons. Peak, motion and projection witnesses feed
back to the existing route family under the shared 100-iteration solver budget.
All physical acceptance limits and reference-geometry guards remain unchanged.

This update was screened against the saved four-scene populations without any
Encoder or D calls. The 20-second quality-matching arm gained `3c6709` (25 → 26);
the 15-second arm remains 22 and the 10-second arm remains 19. All previously
accepted routes remain accepted and their saved output coordinates reproduce
exactly. This is a local screening result, not an updated correlation result;
published evaluation results remain unchanged. Derived screening data stay local.

Run the numerical regressions with
`python -m unittest discover -s evaluation/code -p "test_vectoring*.py"`, or run
`test_vectoring_path` and `test_vectoring_certification` directly with
`evaluation/code` on `PYTHONPATH`. The legacy path tests explicitly select their
5 km fixture; this does not change the production default or run configuration.

## Changi hourly application report

```bash
python evaluation/code/report_changi_hourly.py --input /local/changi-dedup-evaluation --preprocessing position-dedup --output /local/new-hourly-report
python -m unittest discover -s evaluation/code -p "test_changi_hourly_report.py"
```

The report builder requires `--input` pointing to the local saved-data package, which is not uploaded to GitHub. It verifies 48 hours and all 6,600 stored draws (6,200 with the original appendix input and `--preprocessing original`), then writes a report and four PNG/SVG/PDF figure sets into a **new** directory. It never imports the Encoder or D estimator and never resamples. Main figures show D, before/after-QC counts and estimability for all 24 hours; NA breaks lines. Fixed-N and weather plots are supplements. No 3h report, source-track recovery, changed thresholds or positive-result selection is performed. Dependencies: NumPy and Matplotlib. Set `CHANGI_HOURLY_INPUT` to that local package and `CHANGI_HOURLY_POLICY=position-dedup` before running the saved-record tests; they explicitly skip when it is unavailable.

This replaces the local report-text replacement and separate audit plotting scripts with one portable entrypoint. To update the public package, review and replace only its report and figures. Keep derived data, execution source snapshots, hashes and report manifests local. See the [case documentation](../runs/changi-hourly/README.md).

These entrypoints replace the former implicit five-second, all-experiments runner. They use explicit inputs and new output directories. None runs by default, changes a threshold, chooses scenes by correlation, or overwrites the published `evaluation/runs/` data. Checkpoint weights and raw/source trajectories remain local.

## Dependencies and checkpoint

Use the repository's NumPy/SciPy/PyTorch/Matplotlib dependencies and install `evaluation/requirements-screening.txt` for Clarabel when screening. Original library versions are recorded in published run manifests; floating-point reproducibility across versions/devices is not assumed.

Inference requires the frozen strict-10-second epoch-90 checkpoint, SHA-256 `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`. The runner checks both file identity and preprocessing cadence. It never silently uses the older checkpoint shipped elsewhere in the repository. Encoder training is not part of these commands.

## Approved four-scene Vectoring workflow

Screen exactly the published four-scene/26-candidate scope from existing local source records and exact quality matches:

```bash
python evaluation/code/screen_approved_scenes.py --source-tracks /local/source-tracks --quality /local/point-evidence.jsonl.gz --output /local/new-screen
```

This uses the same full-track fit, local direction certificate, continuous reference and reject-only checks. The active 2026-10-25 configuration is a **15 km segmented** target (`SEGMENTED=True` in `vectoring_population.py`): 150 s straight out, 300 s plateau, 150 s straight back, 30 s corner blend. The segmented arm is schematic and skips the deformed-kinematics rejection; the smooth `generate()` path remains available by setting `SEGMENTED=False`. Basic-QC backgrounds stay separate from injection eligibility; a failed route does not revert its fitted baseline. Missing evidence is never filled. `screen_vectoring_candidates.py` remains the explicit original-twelve-scene ZIP screening utility; it does not run correlation.

Evaluate the frozen, already accepted baseline/left/right arrays:

```bash
python evaluation/code/run_evaluation.py vectoring --screening /local/new-screen --checkpoint /local/encoder-10s.pt --output /local/new-vectoring
```

The driver retains all four scenes, original seeds, both-side acceptance, all integer doses and the unchanged estimator. The published segmented 15 km run has 19 candidates (two 15 km-infeasible candidates are omitted); a different population is reported explicitly rather than silently changing the experiment. It does not generate or refit a trajectory during inference.

## Holding equal-duration workflow

```bash
python evaluation/code/run_evaluation.py holding-control --data-zip /local/scene-inputs.zip --checkpoint /local/encoder-10s.pt --output /local/new-holding
```

The original twelve scenes and QC500 rule are retained. Both arms append exactly 240 seconds / 24 points at the endpoint, using the same speed and heading. The original observed points remain unchanged. Undefined direction or missing local speed support rejects the pair rather than inventing a fallback. The historical midpoint racetrack helper remains for reference/regression compatibility; it is not the control's insertion method.

## Saved-result diagnostics

These commands read published results by default and write separately; they do not call the Encoder or create trajectories:

```bash
python evaluation/code/run_evaluation.py holding-common-cutoff --output /local/new-common-cutoff
python evaluation/code/run_evaluation.py vectoring-fixed-scales --output /local/new-fixed-scales
```

`holding-common-cutoff` imports the exact archived midpoint-Holding cutoffs for both saved terminal arms, including unavailable cutoffs. It never finds a new peak. Use `--control` and `--reference` to identify explicit alternative saved copies of the same inputs.

`vectoring-fixed-scales` uses only the fourth scene's saved embeddings and original assignments. Every baseline-selected scale must pass the existing pair-count and C(r) gates. An invalid scale rejects D rather than being dropped. It is a diagnostic, not a replacement for the primary D estimator. `--input` selects an explicit saved four-scene result directory.

## Reports and figures

```bash
python evaluation/code/refresh_outputs.py --output /local/new-summary
```

This exports a concise Markdown summary and PNG/SVG overview from saved statistics. It does not recompute D or alter the authored combined report. `build_report.py`, `make_figures.py`, and `run_analysis.py` use this explicit-output interface when invoked directly; `run_analysis.summarize` remains the shared statistics API used by inference. Detailed historical execution scripts are preserved under each published package's `source/` for provenance, not as the current entrypoints.

## Cadence and verification

Active input readers and the full-track population workflow use a strict 10-second Encoder grid. The route optimizer still uses internal five-second collocation plus spline breaks and continuous checks; those numerical locations are not extra input observations. Legacy five-second helper fixtures remain supported by `run_vectoring_eval.py`/`vectoring_path.py`; the active population driver explicitly passes `sample_s=10` for route output and kinematic checks.

Software checks (no new observational experiment):

```bash
python -m unittest discover -s evaluation/code -p "test_*.py"
```

Checks cover fixed-scale rejection and exact saved diagnostic replay, terminal pairing and closure, output protection, checkpoint rejection, timing, uncertainty, peak feedback, direction certification and fixed background membership. Existing published results are never regenerated by this test command.

## Integrated saved-record postprocessing

Both inference entrypoints now finish by writing their postprocessed summaries and a per-run `report.md`. Holding produces `summary.json`, `paired-dose-records.json` and `repeat-summary.json`. Vectoring produces `summary.json`, `point-selection.json` and `scene-summary.json`. This stage reads existing D records; it never re-estimates D, changes gates or fills missing values.

To summarize an existing complete run without inference, use a new destination:

```bash
python evaluation/code/postprocess_results.py holding --input /local/completed-holding --output /local/holding-summary
python evaluation/code/postprocess_results.py vectoring --input /local/completed-vectoring --output /local/vectoring-summary
```

Standalone postprocessing copies the existing dose records, assignments, policy and execution manifest into the new destination; Vectoring also copies its saved embeddings for fixed-scale diagnostics. Those inputs remain byte-identical, with original execution provenance intact. A separate `postprocessing-manifest.json` records the source hashes, current aggregation code and copied inputs. The new destination can be passed directly to the corresponding saved-result diagnostic. Inference-produced runs already include the summaries. Published `runs/` and existing outputs are protected.

`refresh_outputs.py --runs ROOT --output NEW_DIRECTORY` expects the package layout listed in `runs/README.md`, not a single inference run. It exports a combined overview. The authored `evaluation/report.md` retains its detailed interpretation and is checked against the saved packages; it is not overwritten by this command. Historical snapshots in `archive/` are not runtime inputs. Internal five-second optimizer collocation and legacy helpers do not change the strict ten-second Encoder input cadence.


Historical integration audit (saved-record summaries and the older publication snapshot; this checker is not synchronized with the current presentation):

```bash
python evaluation/code/check_consistency.py
python -m unittest discover -s evaluation/code -p "test_postprocessing.py"
```

`check_consistency.py` still expects the older publication hashes and 5 km report tables, so it does not certify the current 15 km / midpoint 0.94 presentation. Current midpoint numerical assertions and source hashes are checked by `plot_holding_primary.py`; its local render manifest records those checks. Do not refresh old evidence hashes merely to make the historical check pass.

The targeted integration tests do not call the Encoder or D estimator. The broader historical test suite includes saved-embedding D replay and is a separate software check.


## Current paper presentation (saved results only)

```bash
python evaluation/code/report_changi_hourly.py --input /local/changi-dedup-evaluation --preprocessing position-dedup --output /new/local/hourly-report
python evaluation/code/make_review_figures.py --output /new/local/maneuver-figures
```

The hourly builder delegates version-aware text to `hourly_report_text.py`. It reads 6,600 saved draws for the deduplicated main result, or 6,200 for the original appendix with `--preprocessing original`. The frozen 1,697/1,434 aircraft-hour population must match the selected version. It does not change screening or rerun inference. The maneuver renderer includes all 12 Holding and 4 Vectoring scenes, negative correlations and unavailable states, with source hashes checked after rendering. Only code, reviewed reports and figures may be published; generated manifests and hourly evidence remain local. Historical compact figure scripts are provenance, not the preferred all-scene renderer.

## Holding historical-range paper layout

`python evaluation/code/plot_holding_historical_ranges.py --output /new/local/holding-main-figure` reads only saved Holding results and historical cutoffs. It renders all seven cutoff-available scenes plus every estimable order coefficient, including negative values and explicit unavailable orders. The default main figure shows only the original cutoff range; later doses remain in Appendix H. `--show-full-tail` reproduces the earlier grey-tail view. NA breaks lines and the straight-control aggregate is disclosed. It verifies source hashes and writes a local-only render manifest; it does not change any result or rerun estimation. See [Appendix H](../holding-paper-appendix.md) for all twelve scenes and controls.

## Historical midpoint response renderer (R² ≥ 0.98)

`plot_holding_midpoint_response.py --output <new-directory>` reads the immutable strict-10s-reference QC500 results. It reuses saved cutoffs, verifies saved means and valid counts, renders delta/all-range/full-range companion figures, and checks source hashes. No inference, D estimation, new sample or cutoff selection is performed. Only figures and Markdown should be copied to the publication tree; the render manifest stays local.


## Current midpoint Holding primary renderer (R² ≥ 0.94)

`plot_holding_primary.py --output <new-directory>` replays final fit-quality screening through `audit_holding_r2_sensitivity.py`, then produces the seven-scene absolute-D main figure, five-scene ΔD companion, twelve-scene full-range appendix, and the current report. The final gate is explicitly 0.94; all other gates, fit slopes, orders and archived endpoints remain unchanged. The shared screening helper retains historical sensitivity naming internally; the user-selected primary status is defined by the new report and render manifest. No inference or new D fit occurs. Outputs are checked against recomputed per-order coefficient summaries and original source hashes. Publish only reviewed figures and Markdown; keep derived JSON and screening records local. The older midpoint renderer reproduces the archived 0.98 presentation and must not overwrite the current primary figures.

## Latest repaired 20-second correlation comparison

The [run package](../runs/vectoring-20s-repaired/README.md) contains execution,
reporting and verification snapshots for the completed 26-versus-25 comparison.
These require the private local frozen inputs described there. The numerical
implementation is `vectoring_path.py` plus `vectoring_certification.py`; the
latest correlation result is separate from the 19-candidate historical package.
New population arrays, embeddings, assignments, fit records and manifests are
not included in this publication.
