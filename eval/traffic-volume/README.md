# Changi Sample-Size Sensitivity

This experiment measures how the raw finite-grid correlation-integral slope changes with the number of sampled trajectories in each of the 720 September 2026 WSSS hourly scenes.

## Fixed protocol

- The bundled epoch-60 encoder produces one 16-dimensional, sum-pooled vector per trajectory with at least 30 samples at 10-second intervals.
- Each hour uses 20 deterministic random permutations and nested subsets for every integer `n = 5, ..., N`. Hours with fewer than five eligible trajectories remain in the results.
- The fixed protocol is embedded in `prepare_encode.py`. The slope uses its 64-radius grid, all scales with `0 < C(r) < 1`, and at least two fit scales. Pair counts use strict `distance < radius`; no fit-quality gate is applied.
- The paper figure reports the manuscript's selected bins within `n = 5–35`. A second figure preserves the complete observed range through `n = 49`.

## $D$ estimator configuration

This experiment uses the ungated slope `raw_slope` in
[`run_experiment.py`](run_experiment.py), not the gated defaults of the
`complexity` package. The values below are fixed in the protocol embedded in
[`prepare_encode.py`](prepare_encode.py) and are checked on every run.

| Setting | Value |
|---|---|
| Trajectory eligibility | Source fragments with at least 25 points; fragments with at least 30 points at 10 s are encoded |
| Embedding | 16-D, temporal sum pooling, no post-pooling normalization |
| Distance and pairs | Euclidean; all unordered pairs, including zero-distance pairs; strict `distance < r` |
| Radius grid | One fixed grid of 64 geometric radii, 0.2115 to 377.18 (ratio ≈ 1.126), shared by every hour and subset size; its SHA-256 is stored in the protocol |
| Fit scales | Every radius with $0 < C(r) < 1$ |
| Fit | Ordinary least squares on $\log C(r)$ versus $\log r$; slope is $D$ |
| Minimum requirements | At least 2 embeddings and at least 2 fit scales |
| Quality gates | None: no $C(r)$ bounds and no $R^2$ threshold ($R^2$ is reported only) |
| Subsets | For each hour, 20 random orders (seed `20261026` + chronological hour index); nested prefixes of size `n = 5, ..., N` |

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

The ZIP is the input boundary for this experiment; upstream OpenSky collection, flight identification, and cleaning are not rerun. It must contain 720 hourly WSSS scenes and the archive integrity manifest. The runner checks the archive, sampling cadence, trajectory eligibility, checkpoint, expected counts, and cache hash against the embedded experiment protocol. Choose a new output directory for every run.

## Outputs

The run writes the protocol and status, per-order and per-hour slope results, paired and binned summaries, validation checks, and both figures under the selected output directory. A full archive run also writes the prepared scene index and arrays, encoded cache, and its provenance summary. No separate stage commands or metadata sidecar are needed to run the experiment.
