# Changi Sample-Size Sensitivity

This experiment measures how the raw finite-grid correlation-integral slope changes with the number of sampled trajectories in each of the 720 September 2026 WSSS hourly scenes.

## Fixed protocol

- The bundled epoch-60 encoder produces one 16-dimensional, sum-pooled vector per trajectory with at least 30 samples at 10-second intervals.
- Each hour uses 20 deterministic random permutations and nested subsets for every integer `n = 5, ..., N`. Hours with fewer than five eligible trajectories remain in the results.
- The slope uses the fixed 64-radius grid in `config.json`, all scales with `0 < C(r) < 1`, and at least two fit scales. Pair counts use strict `distance < radius`; no fit-quality gate is applied.
- The paper figure reports the manuscript's selected bins within `n = 5–35`. A second figure preserves the complete observed range through `n = 49`.

## Reproduce

Install the repository requirements. The checked-in embedding cache reproduces the analysis and figures without external trajectory data or model inference:

```bash
python eval/traffic-volume/run_experiment.py \
  --embeddings eval/traffic-volume/embeddings.npz \
  --output eval/results/traffic-volume/reproduction
```

To run preparation, encoding, and analysis from the prepared trajectory archive, use the included checkpoint:

```bash
python eval/traffic-volume/run_experiment.py \
  --archive /path/to/WSSS_prepared_arrivals.zip \
  --checkpoint Encoder/encoder/encoder.pt \
  --output eval/results/traffic-volume/full-reproduction \
  --device auto
```

The ZIP is the input boundary for this experiment; upstream OpenSky collection, flight identification, and cleaning are not rerun. It must contain 720 hourly WSSS scenes and the archive integrity manifest. The runner checks the archive, sampling cadence, trajectory eligibility, checkpoint, expected counts, and cache hash against `config.json`. Choose a new output directory for every run.

## Outputs

The run writes the protocol and status, per-order and per-hour slope results, paired and binned summaries, validation checks, and both figures under the selected output directory. A full archive run also writes the prepared scene index and arrays, encoded cache, and its provenance summary. No separate stage commands or metadata sidecar are needed to run the experiment.
