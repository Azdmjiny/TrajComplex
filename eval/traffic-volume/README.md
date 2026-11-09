# Experiment IV-A: Sample-Size Sensitivity

This folder reproduces the paper's Changi arrival-scene sample-size experiment. It estimates how the raw finite-grid correlation-integral slope changes as the number of sampled trajectories, `n`, increases within each hourly scene.

## Fixed protocol

- All 720 natural local hours in September 2026 at Singapore Changi (WSSS) are retained.
- The supplied hourly archive contains one prepared fragment per flight-hour. Source fragments have at least 25 samples; the encoder eligibility rule retains fragments with at least 30 samples at 10-second intervals.
- The frozen WSSS epoch-60 encoder produces one 16-dimensional vector per eligible fragment using temporal sum pooling, with no post-pooling normalization. The exact checkpoint and preprocessing identifiers are in `config.json`.
- Each hour uses 20 deterministic random permutations. Each order contributes nested subsets for every integer `n = 5, ..., N`. A scene with `N < 5` remains in the manifest and contributes no slope estimates.
- The raw slope uses the fixed shared 64-radius grid embedded in `config.json`, all scales with `0 < C(r) < 1`, and at least two scales. Pair counts use strict `distance < radius`; zero-distance pairs remain in the denominator. No fit-quality gate is applied, and failed fits remain missing with a reason.
- At each `(hour, n)`, valid orders are summarized by their median. The paper figure then takes each scene's median over available `n` values within each bin before summarizing across hours. IQR and whiskers describe across-hour dispersion, not confidence intervals.
- Figure 4 displays the paper's post-hoc `n = 5–35` bins. The complete observed `n = 5–49` curve is also saved as a diagnostic, including the declining tail.

## Reproduce the published curves and figures

Install the repository-root dependencies:

```bash
python -m pip install -r requirements.txt
```

The validated epoch-60 embedding cache is included. This reproduces the slopes, summaries, validation, and figures without rerunning the encoder:

```bash
python eval/traffic-volume/run_experiment.py \
  --embeddings eval/traffic-volume/embeddings.npz \
  --metadata eval/traffic-volume/encoding-summary.json \
  --output eval/results/traffic-volume/e60-reproduction
```

The epoch-60 checkpoint SHA-256, preprocessing ID, source archive SHA-256, sample counts, and embedded radius-grid hash are checked against `config.json`. The embedding archive SHA-256 is checked against its encoding metadata and recorded in the run protocol and result files. The output directory must be new; a run never overwrites previous output.

## Re-encode from prepared trajectories

The prepared trajectory archive is not bundled. Obtain the exact authorized archive and pass its path together with the checkpoint included at `Encoder/encoder/encoder.pt`:

```bash
python eval/traffic-volume/run_experiment.py \
  --archive /path/to/WSSS_prepared_arrivals.zip \
  --checkpoint Encoder/encoder/encoder.pt \
  --output eval/results/traffic-volume/e60-full-reproduction \
  --device auto
```

`--device auto` uses CUDA when available and CPU otherwise. Use `--device cpu` or `--device cuda` to select explicitly.

The supplied archive is already prepared: the upstream OpenSky collection, flight identification, and cleaning/interpolation steps are not rerun by this folder. `prepare_scenes.py` verifies the archive's internal hashes, hour coverage, trajectory schema, sampling cadence, arrival labels, and paper counts, then applies the 30-point encoder eligibility rule. This is the documented input boundary for the current reproduction package.

## Run from saved embeddings

When epoch-60 embeddings have already been generated, the slope, summary, validation, and figure stages can be reproduced without rerunning the encoder:

```bash
python eval/traffic-volume/run_experiment.py \
  --embeddings /path/to/e60_embeddings.npz \
  --metadata /path/to/e60_encoding-summary.json \
  --output eval/results/traffic-volume/e60-from-embeddings
```

To use another independently generated cache, its metadata must identify the exact epoch-60 checkpoint, source archive, pooling rule, preprocessor, and 720 hourly scenes. The bundled `embeddings.npz` and `encoding-summary.json` are the canonical cache for this paper version.

## Individual stages

Preparation, encoding, and computation can be run separately to inspect intermediate files. Figure generation remains part of `run_experiment.py`:

```bash
python eval/traffic-volume/prepare_scenes.py \
  --archive /path/to/WSSS_prepared_arrivals.zip \
  --output eval/results/traffic-volume/prepared

python eval/traffic-volume/encode_scenes.py \
  --prepared eval/results/traffic-volume/prepared \
  --checkpoint /path/to/epoch_60.pt \
  --output eval/results/traffic-volume/encoded

python eval/traffic-volume/compute_results.py \
  --embeddings eval/results/traffic-volume/encoded/embeddings.npz \
  --metadata eval/results/traffic-volume/encoded/encoding-summary.json \
  --output eval/results/traffic-volume/results
```

## Outputs

- `prepared/scene-index.json` and `prepared/scenes/*.npz`: verified per-hour ENU tracks, timestamps, IDs, and lengths.
- `encoded/embeddings.npz` and `encoded/encoding-summary.json`: one 16-D vector per selected trajectory, plus checkpoint and provenance metadata.
- `results/d-vs-n-no-gate.json`: every hour's curve and valid-order count at each `n`.
- `results/sequence_results.csv.gz`: each permutation-level fit, including undefined-fit reasons and diagnostics.
- `results/summary.json` and `results/binned-summary.json`: exact-`n`, paired, and paper-bin summaries with contributing-hour counts.
- `figures/figure4_sample_size_binned.pdf` and `figures/figure_sample_size_full_range.pdf`, with PNG copies for inspection.
- `protocol.json` and `validation.json`: input hashes, software/run details, expected-count checks, and validation status.
