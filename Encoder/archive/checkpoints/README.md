# Historical candidate checkpoints

[Archive index](../README.md) | [Current model](../../encoder/README.md)

Nine five-second candidates cover dimensions 4, 8 and 16 with seeds 42, 43 and 44.
The [original manifest](../reports/result/checkpoint_manifest.json) retains sizes,
hashes, selected epochs and paths relative to `archive/`.
`Encoder/verify_delivery.py` verifies every candidate. These weights support
historical comparisons and must not replace the current 10-second checkpoint.
