# Shared history (histry)

The directory name `histry` follows the requested layout. These records span
multiple experiments, so they are kept together rather than split by subject.

| Folder | Contents and role |
|---|---|
| [strict-10s-reference](strict-10s-reference/report.md) | Twelve-scene historical Holding/Vectoring saved results; still required by the current midpoint Holding renderer and common-cutoff control |
| [legacy-before-workflow-integration](legacy-before-workflow-integration/README.md) | Original committed/local mixed snapshots and their exact-byte inventory |
| [combined-reports](combined-reports/README.md) | Superseded combined 5 km report and former directory indexes |
| [publication-records](publication-records/README.md) | Historical publication manifests and checks; not live claims about current results |
| [legacy-audit-source](legacy-audit-source/) | Frozen checker for the old report layout |
| [cross-study-figure-source](cross-study-figure-source/) | Frozen source for the older combined figure now in report/figures |
| [organization-map.json](organization-map.json) | Composed old-to-current path map and preserved-evidence hashes |

## Why strict-10s-reference is important

Think of this package as a saved laboratory notebook. `strict-10s` means a
strict 10-second Encoder/input cadence. One JSON container stores Holding and
Vectoring in separate fields; their trajectories and correlation curves were
not pooled into a single experiment.

The QC500 Holding section contains 12 source hours, five injection orders per
hour (60 curves), and 1,980 dose records. Each record retains its fit result,
acceptance/failure status and relevant fit-quality diagnostics. Other QC
variants and historical Vectoring records remain as provenance, including
failed or baseline-only cases.

The current R² >= 0.94 midpoint report reads these original saved fits; it does
not generate a new slope for each recovered point. The original source run's
R² gate remains 0.98 in its manifest. The paired endpoint-control analysis reads
its fixed historical cutoffs from `summary.json` and checks the selection audit.
Deleting this package would break those postprocessing paths and remove the
basis for tracing current Holding claims. The latest 26-candidate Vectoring
result is in [vectoring/main](../vectoring/main/README.md), not this old package.

Moving this notebook is safe because maintained code resolves it through
`study_path('strict-10s-reference')`. Its JSON, CSV, historical source and hashes
are unchanged. Exact snapshots retain original execution paths; the map resolves
those paths without rewriting the historical evidence.
