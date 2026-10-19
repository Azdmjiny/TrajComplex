# Encoder training results

Encoder training specified in PLAN.md and the representation assessments supported by the available data are complete. Validation selected the main model: **16 dimensions, sum pooling, seed 43**. Frozen weights are in `encoder/encoder.pt`, corresponding to `d16_e120_t0p01_s43`. The nine best-validation checkpoints for three dimensions and three seeds are in `checkpoints/`.

## Completed work

- Hyperparameter screening: eight dimensions, seed42, ε=120/1200m × τ=.01/.05; four independent 30-epoch runs.
- Dimension/stability comparison: selected ε=120.0m and τ=0.01; 4/8/16 dimensions with three seeds each, nine 30-epoch runs. One screening run is reused, giving 12 independent models and 360 epochs in total.
- Batch size 16 and bf16 mixed precision. Two processes initially ran in parallel; after one stopped progressing, training resumed serially from checkpoints without gradient accumulation. Final TEST evaluation followed validation-based checkpoint selection.
- Train/validation/test: 6877/1214/8092 full trajectories, sampled every five seconds with the endpoint retained. The original environment and raw data were not modified.

## Independent test of the representative checkpoint

| Geometric proxy | TEST R² | Within-STAR TEST macro R² | Random initialization within-STAR R² | Length baseline within-STAR R² |
|---|---:|---:|---:|---:|
| path_m | 0.5906 | 0.6568 | 0.9461 | 0.8008 |
| curvature_rad | 0.2914 | 0.2836 | 0.4722 | 0.3519 |
| sinuosity | 0.5797 | 0.6435 | 0.9430 | 0.7938 |
| duration_s | 0.4533 | 0.5787 | 0.9942 | 0.9999 |

The selected model does not exceed the stronger of the two baselines on any of the four proxies. These tests therefore do not establish additional geometric-proxy prediction capability from self-supervised training.

All probes are fitted on training data, with ridge alpha selected on validation data. Within-STAR macro averaging reduces the influence of route discrimination alone. Three-seed results and mean/GeM sensitivity are in `three_seed_summary.json` and `probe_summary.csv`. These targets are geometric proxies, not complexity ground truth. The randomly initialized baseline measures changes due to training; signals already predictable at initialization must not all be attributed to self-supervised training.

## Representation diagnostics

The representative model has TEST effective rank 9.8180 / 16, with 0 low-variance dimensions at threshold 1e-8. The correlation between sum-vector norm and sample length is 0.6472. Effective rank below output dimension suggests information may be concentrated in fewer directions. Per-dimension variance, distance distributions, and length-stratified probes are saved in `test_results.json`; nonzero vectors alone do not establish the absence of representation degradation. Interpret sum/length confounding alongside mean/GeM and length-stratified results.

## Delivery and limitations

Weights, preprocessing, configuration, raw-file SHA256 values, per-trajectory split assignments, seeds, epoch logs, validation-selection records, test results, randomly initialized baselines, the callable frozen interface, and a real example have been saved. `export_verification.json` checks loading, freezing, and feature-reconstruction consistency; `checkpoint_manifest.json` records hashes for nine checkpoints.

The data lack absolute timestamps and real flight IDs, so real flight/date-level separation and stable hourly point-cloud/correlation-dimension ranges have not been validated. This delivery is a trained ATSCC/ITSC-inspired Encoder, not a complete hourly complexity system or a strict reproduction of the original paper. A PowerShell telemetry interruption is recorded in PROTOCOL.md; training subsequently resumed from checkpoints in a process with outbound networking disabled.
