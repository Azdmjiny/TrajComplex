# Current evaluation code

These entrypoints replace the former implicit five-second, all-experiments runner. They use explicit inputs and new output directories. None runs by default, changes a threshold, chooses scenes by correlation, or overwrites the published `evaluation/runs/` data. Checkpoint weights and raw/source trajectories remain local.

## Dependencies and checkpoint

Use the repository's NumPy/SciPy/PyTorch/Matplotlib dependencies and install `evaluation/requirements-screening.txt` for Clarabel when screening. Original library versions are recorded in published run manifests; floating-point reproducibility across versions/devices is not assumed.

Inference requires the frozen strict-10-second epoch-90 checkpoint, SHA-256 `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`. The runner checks both file identity and preprocessing cadence. It never silently uses the older checkpoint shipped elsewhere in the repository. Encoder training is not part of these commands.

## Approved four-scene Vectoring workflow

Screen exactly the published four-scene/26-candidate scope from existing local source records and exact quality matches:

```bash
python evaluation/code/screen_approved_scenes.py --source-tracks /local/source-tracks --quality /local/point-evidence.jsonl.gz --output /local/new-screen
```

This uses the same full-track fit, local direction certificate, continuous peak feedback, 5 km target and reject-only checks. Basic-QC backgrounds stay separate from injection eligibility; a failed route does not revert its fitted baseline. Missing evidence is never filled. `screen_vectoring_candidates.py` remains the explicit original-twelve-scene ZIP screening utility; it does not run correlation.

Evaluate the frozen, already accepted baseline/left/right arrays:

```bash
python evaluation/code/run_evaluation.py vectoring --screening /local/new-screen --checkpoint /local/encoder-10s.pt --output /local/new-vectoring
```

The driver retains all four scenes, original seeds, both-side acceptance, all integer doses and the unchanged estimator. It expects the approved 21 accepted candidates; a different population stops rather than silently changing the experiment. It does not generate or refit a trajectory during inference.

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
