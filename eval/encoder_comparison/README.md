# Changi Encoder Comparison

This experiment examines whether the separation of reference low- and high-$D$
scenes at Changi persists across encoder settings. The reference is the
original 16-dimensional, 60-epoch encoder trained on pooled March–May 2025
data.

## Comparison setup

- **Embedding dimension.** Train 8- and 32-dimensional variants for 60
  epochs using the same pooled data and original splits as the reference.
- **Training month.** Train a 16-dimensional, 60-epoch encoder for each of
  March, April, and May 2025. Each month uses the same number of trajectories
  per split (4,522 training, 566 validation, and 521 test), selected
  deterministically from the original splits.
The dimension and month variants encode the same 720 September 2026 Changi
arrival scenes as the reference. Each model uses its saved training
standardization, sum pooling, and the same ungated hourly $D$ estimator as the
[cross-airport evaluation](../cross_airport/). Among scenes with finite
$D$ for all six encoders, the reference's lower and upper quartiles define
the low and high groups. The comparison scores are percentile ranks within
these same scenes. AUC measures agreement with the reference groups.

The pooled reference was trained in a different software environment from
the five new variants. The month variants are matched to one another in sample
size and differ from the pooled reference in both training period and sample
size.

## $D$ estimator configuration

All six encoders are scored with the ungated estimator `raw_dimension` in
[`eval/_hourly.py`](../_hourly.py), identical to the
[cross-airport configuration](../cross_airport/README.md#d-estimator-configuration).

| Setting | Value |
|---|---|
| Trajectory eligibility | Prepared fragments with at least 25 points at 10 s; no additional 30-point check at encoding |
| Embedding | 8-, 16- or 32-D (per encoder), temporal sum pooling, no post-pooling normalization |
| Distance and pairs | Euclidean; all unordered pairs, including zero-distance pairs; strict `distance < r` |
| Radius grid | 64 geometric radii from the scene's minimum positive to maximum pairwise distance, computed separately for each encoder and scene |
| Fit scales | Every radius with $0 < C(r) < 1$ |
| Fit | Ordinary least squares on $\log C(r)$ versus $\log r$; slope is $D$ |
| Minimum requirements | At least 2 embeddings, a positive distance range, and at least 2 fit scales |
| Quality gates | None: no minimum scene size, no $C(r)$ bounds, no $R^2$ threshold |
| Common scenes | Hours with finite $D$ for all six encoders |
| Reference groups | Reference ($d=16$, pooled) $D \le Q_{25}$ is low, $D \ge Q_{75}$ is high |
| Score | Percentile rank `rank / (n + 1)` within common scenes; AUC from the Mann–Whitney $U$ statistic |

## Code

`train.py` trains the five variants from the cleaned 1 Hz Changi training
archive. It keeps the original splits, samples every ten seconds, and derives
normalization from each variant's training split. Training requires a
BF16-capable CUDA GPU.

`evaluate.py` scores the prepared Changi scenes with the reference and
variants, then writes the common-scene groups, AUCs and a violin plot. Run from
the repository root with the root requirements installed.

```bash
python -m eval.encoder_comparison.train --source data/WSSS_CLEANED.jsonl.gz --baseline Encoder/encoder/encoder.pt --output artifacts/changi-variants
python -m eval.encoder_comparison.evaluate --prepared data/prepared/WSSS --baseline Encoder/encoder/encoder.pt --variants artifacts/changi-variants --output eval/results/encoder_comparison
```

The prepared input has the same format as the Changi directory in the
cross-airport evaluation. Training archives, prepared scenes, and generated
checkpoints and outputs are supplied or written separately.
