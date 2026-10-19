# Candidate checkpoints

[Encoder overview](../README.md)

Nine delivered candidates cover dimensions 4, 8, and 16 with seeds 42, 43, and 44. Filenames encode dimension, RDP epsilon, temperature, and seed. The selected inference copy is in `../encoder/encoder.pt`.

Keep the candidates for seed/dimension sensitivity and verification. Expected paths, sizes, hashes, and selected epochs are recorded in [checkpoint_manifest.json](../reports/checkpoint_manifest.json). `verify_delivery.py` checks every listed candidate. They are not disposable optimizer caches.
