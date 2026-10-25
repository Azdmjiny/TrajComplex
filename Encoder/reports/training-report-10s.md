# Completed 10-second Encoder training

The fixed epoch-90 Encoder was trained from scratch and exported successfully. The original 5-second artifacts were not replaced.

| Item | Result |
|---|---|
| Sampling | Strict 10 seconds; no off-grid endpoint |
| Trajectories | 6,877 train / 1,214 validation / 8,092 held-out test |
| Output | 16-dimensional token vectors; sum pooling |
| Epochs | 90, fixed in advance |
| First-epoch train / validation SNN loss | 4.186108 / 4.078772 |
| Final-epoch train / validation SNN loss | 4.015052 / 3.976986 |
| Training + validation loop time | 20.87 minutes |
| Checkpoint SHA-256 | `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976` |

Integrity checks passed for the original split membership, strict sampling, finite features, training-only normalization, source hashes and completed export. Reloading the model on CPU produced finite, deterministic outputs. Selecting 10-second samples through the inference API exactly matched explicit subsampling, including a trajectory with an off-grid endpoint.

Training losses describe this training objective only. They are not holding/vectoring correlations, and losses at different sampling intervals should not be treated as directly comparable performance scores. This run did not score the test set or rerun evaluation. Public input trajectories were preprocessed upstream; this run added no interpolation or missing-value filling. Runtime versions differ from the reference, as documented in README.md.

The deliverable is `encoder/encoder.pt` together with its preprocessing metadata and the local inference implementation. Future evaluation must use the new 10-second input contract and normalization, and separately validate source timing, altitude and maneuver geometry.
