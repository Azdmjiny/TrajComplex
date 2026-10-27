# Trajectory Injection Evaluation

This directory evaluates how Holding and Vectoring injections change the embedding-space dimension `D` produced by the frozen Encoder. Both runners read Changi 10-second trajectory data and use the frozen Encoder and dimension estimator.

## Run

From the repository root:

```bash
.venv/bin/python eval/trajectory_injection/run_holding.py
.venv/bin/python eval/trajectory_injection/run_vectoring.py
.venv/bin/python -m unittest eval/trajectory_injection/test_holding.py
```

Results are written by default to a dated directory under `eval/results/`. Use `--output <directory>` to choose another path; the target directory must not already exist.

## Experiments

- `run_holding.py`: inserts a 240-second closed racetrack at the trajectory midpoint and trims 240 seconds from the end, preserving the total trajectory length.
- `run_vectoring.py`: replaces a 600-second window with a laterally offset segment while preserving the sample count. If an aircraft is selected more than once, each event uses a different window. The paths are not certified for aircraft-motion feasibility; the data also lack NIC/NACp, so positional uncertainty cannot be certified.
- `test_holding.py`: checks Holding injection length, repeated insertions, and tail trimming.

Both experiments use the uninjected scene as the baseline and recompute `D` by event dose. Outputs include dose-level results, summaries, audits, plots, and run configuration. `Delta D` is the change from the same-scene baseline; Spearman rho describes the monotonic association between dose and summarized `Delta D`.
