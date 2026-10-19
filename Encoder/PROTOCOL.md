# Encoder experiment protocol (fixed before training)

The objective is to deliver the self-supervised trajectory Encoder specified in PLAN.md. The experiment directory was created afresh; no old scripts, caches, logs, or weights were read. Raw TSV files were read-only. A separate `.venv` used the existing PyTorch/CUDA installation through system-site-packages without modifying the original environment.

## Data

The local Hugging Face ATFMTraj RKSIa dataset contains 8091 official TRAIN trajectories and 8092 TEST trajectories. A geometry-signature-grouped 15% validation split of TRAIN gives train/validation/test counts of 6877/1214/8092. Cross-split checks use exact full-coordinate hashes and 32-point shape signatures on a 50-metre grid. Signatures are only a partial duplicate screen and cannot establish the absence of other near-duplicates. Dates and flight IDs are unavailable, so real flight/date-level separation cannot be verified; these fields are not fabricated.

Trajectories contain relative coordinates sampled every second. After restoring `r_max=120000m`, take every fifth point and retain the endpoint. This reduces redundancy and accommodates an 8 GB GPU; source trajectories are not cropped. Fingerprints record files, sample indices, and preprocessing parameters. NaN is allowed only as trailing padding. Means/stds for the nine features are fitted only on training tokens. Direction uses forward differences with the final value repeated, so features contain information from the next sample; the Transformer is causal conditional on these features.

## Model and loss

The model uses a 9→256 input projection, L2 normalization, four causal Transformer layers, a 256→D output projection, and per-token L2 normalization. It has four heads, FFN width 512, dropout .35, no explicit positional encoding, and no additional final LayerNorm. D=4/8/16. Bias-free attention projections, sqrt(model_dim) scaling, and normalization/residual order follow the pinned ATSCC commit.

The actual binomial input-mask probability is .2. Masked non-padding tokens remain supervised, matching ATSCC's supervision indices. Attention for a fully masked prefix returns zero and cannot read future tokens. Positives are other tokens in the same RDP segment of the same trajectory; negatives are tokens from other segments or trajectories. Self-pairs and padding are excluded. Singleton segments cannot supply anchors but can supply negatives. Local segment IDs from different trajectories are never merged. The flat loss is `logsumexp(negative/τ)-logsumexp(positive/τ)`, with no hierarchical term or complexity labels. Mathematical exclusion is not implemented by multiplying logits by zero while leaving them inside the exponential.

RDP is computed in three-dimensional metre coordinates. Epsilon=120/1200m corresponds to .001/.01 in the original normalized units; temperatures are .01/.05. First complete a 2×2 screening at D=8 and seed42, each for at most 30 epochs. Then use selected hyperparameters for D=4/8/16 and seeds42/43/44, reusing the completed D8 seed42 run. This gives 12 independent full training runs. The bounded grid implements the budgeted plan and does not claim to exhaust the paper's epsilon/temperature settings.

AdamW uses lr=1e-5 and weight_decay=1e-5, gradient clipping at 1, and bf16 mixed precision. Select the actual batch after benchmarking B8/B16 throughput and memory for the longest trajectories. Do not present gradient accumulation as batch64. If memory permits, two independent experiments can run on one GPU with separate models and optimizers.

Runtime note: after epoch 1, automatic approval review terminated the original PowerShell process because of a Visual Studio/Application Insights telemetry connection. Training code was checked for network calls. `run_offline.py` and `offline_guard/sitecustomize.py` were added to block Python DNS/outbound connections and opt out of telemetry only in experiment subprocesses, without changing the global environment. After verifying DNS/connection blocking, local CUDA, and 70 seconds of process survival, training resumed from saved model, optimizer, and random states. The actual run used a process tree without PowerShell. Parameters and data were unchanged. Later runs can use `python run_offline.py pipeline` or `python run_offline.py finalize` under the same restrictions.

Parallel-resource fallback: during the first two-worker run, one worker stopped progressing for over five minutes after epoch20 while the other completed 30 epochs. Only the experiment process tree was stopped; checkpoints were retained and training resumed with actual concurrency reduced to one. Models, seeds, batch, data, loss, and selection rules were unchanged. `benchmark.json` retains the initial measurements and fallback; `runtime_events.json` records the events.

## Selection and evaluation

Within each run, select the checkpoint with the lowest validation flat-SNN loss on fixed validation batches; do not compare loss values directly across temperatures. Select epsilon/temperature using validation ridge-probe R² for four targets: total path length, accumulated turn, sinuosity, and duration. Average global and within-STAR macro scores equally across all eight values. Choose ridge alpha per target on validation data only; fit feature and target scalers on training data only.

Select dimension by the three-seed mean of that validation score, breaking exact ties in favor of the lower dimension. Sum is the predeclared main pooling rule; mean and the paper's signed GeM-p2 are sensitivity analyses, without additional pooled L2 normalization. Select the representative seed by its median validation score within the chosen dimension, not by the best test score. Final TEST evaluation occurs only after all choices are written to selection.json.

Retain a randomly initialized Encoder baseline. Report per-dimension variance, effective rank, pairwise distances, norm/length correlation, length stratification, and within-STAR probes. Geometric targets are computable representation probes, not human complexity ground truth, holding annotations, or real hourly-scene validation. Absolute timestamps are unavailable, so correlation-dimension/hourly-point-cloud validation was not performed in this delivery; its completion status applies only to the Encoder.

This is an ATSCC/ITSC-inspired Encoder adapted to the current data and plan, not a strict reproduction on the original paper's dataset. Implementation differences, failures, and measured results are retained with the delivery.
