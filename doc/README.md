# Documentation

This directory contains interface and methodology notes. Experimental results belong to their experiment directories.

| Document | Purpose |
| --- | --- |
| [Encoder-to-complexity handoff](atscc-handoff.md) | Input contracts, model loading, scene assembly, and integration commands |
| [Point-cloud complexity method](trajectory-embedding-point-cloud-complexity.md) | Implemented estimator, quality gates, and interpretation limits |

The historical handoff filename is retained because existing documents link to it. Use the lowercase Python package name `complexity` on all platforms.

## Related documentation

- [Project overview](../README.md)
- [Encoder training protocol](../Encoder/PROTOCOL.md)
- [Encoder results](../Encoder/reports/RESULTS_ZH.md)
- [Current evaluation workflow](../evaluation/README.md)
- [Current evaluation report](../evaluation/reports/evaluation-pilot.md)

The method note describes the current implementation; it is not a recovered copy of the missing historical document. Keep experiment-specific findings in `evaluation/reports/` rather than duplicating them here.

## Repository tracking

The repository currently ignores `/doc/`, although the existing handoff file is already tracked. New documents here require an explicit `git add -f doc/<file>` until the root ignore policy is corrected. This documentation cleanup does not change that root policy.
