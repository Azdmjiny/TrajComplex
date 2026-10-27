# Encoder training plan for trajectory complexity quantification

## Objective

Train a reusable self-supervised trajectory Encoder to provide fixed representations for hourly trajectory-embedding point clouds and empirical correlation-dimension estimation. The aim is stability, reproducibility, and preservation of trajectory behavior differences, not complete reproduction of the original large ATSCC model or all 224 ITSC grid configurations.

## Approach and initial configuration

Start from the smaller ATSCC variant in the supplied ITSC paper: a causal Transformer with nine-dimensional state input, four layers, hidden width 256, FFN width 512, four heads, dropout 0.35, and 20% binomial token masking; AdamW with learning rate and weight decay both 1e-5, for at most 30 epochs. Retain RDP segmentation for self-supervised positive/negative samples and the flat Soft Nearest-Neighbour Loss. Complexity labels are not used for training. The paper does not use explicit positional encoding.

- **Dimensionality hypothesis:** retain the 256-dimensional backbone and change the output projection to eight dimensions, with four- and sixteen-dimensional comparisons. Eight dimensions are a starting point, not a presumed optimum. Record this change to the ITSC configuration as a study variant.
- **Temporal pooling:** use sum pooling as the primary candidate, with mean and GeM-p2 sensitivity comparisons. ITSC reports favorable complexity-regression performance for sum pooling, but it may introduce fragment length or observation count into point-cloud distances. Examine this effect before fixing the aggregation rule.
- **Training scale:** validate the workflow on one airport/dataset before extending to target data. ITSC's batch size 64 is a reference, not a requirement. On an 8 GB GPU, benchmark batches 8–16 and mixed precision. Contrastive loss depends on within-batch negatives; gradient accumulation is not automatically equivalent to batch 64. Report effective batch 64 only if cross-microbatch negatives are implemented.
- **Data prerequisites:** confirm support for the same nine-dimensional state: ENU position, unit direction, and airport-relative polar coordinates. Check coordinate systems, normalization, missing values, and RDP threshold units. If target fields or sampling differ, define and freeze conversion rules first; do not mix preprocessing versions.

## Execution steps

1. **Data audit and splitting:** summarize counts, lengths, missingness, and RDP segment distributions. Split by date/flight groups to avoid leakage from the same flight or highly overlapping trajectories. Fit normalization on training data only.
2. **Small pilot run:** use one fixed seed for a few epochs to confirm finite loss, working backpropagation, acceptable memory and speed, checkpoint save/load, and extraction of per-time-step representations.
3. **Training and selection:** freeze the backbone and training procedure. First compare temperature τ, prioritizing 0.01 and 0.05, and RDP threshold ε, starting with a reasonable value since ITSC reports a relatively small effect. Then run 4/8/16-dimensional ablations. Select checkpoints on validation data and check stability with at least three seeds.
4. **Representation assessment:** use lightweight linear/ridge probes for trajectory geometry or operational proxies on held-out data, including within-route groups to avoid measuring route identity alone. Record variance, effective rank, pairwise-distance distributions, and length-related distance/norm bias. Complexity proxies are post-training evaluation targets and do not feed back into training.
5. **Correlation-dimension feasibility:** construct one-hour windows under the target definition, with one aircraft fragment per point. Examine aircraft count, duplicate/near-duplicate points, scale ranges, and linear regions of log C(r) versus log r. Compare slope stability across dimensions and pooling rules. Report sparse windows that cannot be estimated reliably; dimensionality reduction alone does not guarantee reliability.
6. **Freeze the delivery:** fix the Encoder, output dimension, pooling, distance definition, and preprocessing. Save weights, configuration, seeds, data versions/splits, logs, and validation metrics, and provide a reproducible embedding export interface.

## Acceptance criteria

- Training and inference complete on the target GPU; checkpoints reload and repeated inference on fixed input is consistent.
- No NaN/Inf on held-out data; representations have nonzero cross-trajectory variance and reasonable distance distributions, without evident multi-seed instability.
- At least one low-dimensional configuration preserves measurable held-out trajectory behavior information. Hourly clouds with sufficient samples exhibit inspectable scale-fitting intervals. If the latter fails, reconsider sample counts, window definitions, or estimation methods before interpreting the statistic as scene complexity.
- Compare representation quality and correlation-dimension stability across 4/8/16 dimensions before choosing the final version; eight dimensions are not a predetermined acceptance criterion.

## Main risks and decisions

- **Sample size:** hourly counts may be insufficient for stable estimates. Report counts and fit quality per window. If windows must be combined or extended, state how the research definition changes.
- **Length confounding:** sum pooling may make distances reflect observation counts rather than behavior. Compare mean/GeM and length-stratified evaluations. Fix final pooling and normalization in advance rather than switching after inspecting outcomes.
- **Dimensionality tradeoff:** lower dimension may help small-sample geometric estimation but lose behavior information. Select using both held-out behavior signals and correlation-dimension robustness.
- **Reproduction boundary:** this plan follows ITSC's training ideas and smaller backbone, but output dimension, dataset, hardware batch size, and evaluation objectives differ. Describe it as an ATSCC/ITSC-inspired Encoder for complexity quantification, not a strict reproduction.

## Configuration basis

Pages 3–4 of the ITSC paper specify the smaller architecture, optimizer, epochs, and temperature/RDP ranges; page 5 reports pooling and complexity-proxy evaluation. The correlation-dimension definition, hourly scene construction, and point-cloud estimation follow `doc/trajectory-embedding-point-cloud-complexity.md`.
