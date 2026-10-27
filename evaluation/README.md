# Evaluation

Start with the [combined report](report/report.md) and [directory guide](report/DIRECTORY_GUIDE.md).
The folder organization follows the experiment subject; names are not Git branches.

| Subject | Latest primary result | Controls | History |
|---|---|---|---|
| [Holding](holding/README.md) | [10 s midpoint, R² >= 0.94](holding/main/holding-midpoint-response.md) | [Endpoint equal-duration comparison](holding/controls/holding-paper-appendix.md) | [Previous presentations](holding/history/README.md) |
| [Vectoring](vectoring/README.md) | [Repaired 20 s quality matching, 26 candidates](vectoring/main/vectoring-20s-repaired/report.md) | [10/15/20 s sensitivity](vectoring/controls/README.md) | [Earlier 5 km and 19-candidate studies](vectoring/history/README.md) |
| [24h application](hourly/README.md) | [Deduplicated 1h September 8/11 cases](hourly/main/changi-hourly/report.md) | [Original-data appendix and separate threshold study](hourly/controls/README.md) | [N scaling and raw 30-day analysis](hourly/history/README.md) |
| [STAR](star/README.md) | No active primary result | No active control | [STAR Encoder and official-route pilots](star/history/README.md) |

Each subject has `code/`, `main/`, `controls/`, and `history/` entry directories.
Within a study package, `report.md` explains the result, `figures/` contains
plots, and `source/` preserves exact historical execution scripts. Existing
published `results/`, `population/`, and `screening/` files are retained.
Newer private arrays, raw data, checkpoints and credentials remain outside this
publication checkout.

## Interpretation

- Holding: 34/35 positive coefficients, median 0.884 **within unchanged,
  outcome-selected archived pre-peak ranges**; full ranges and failures remain
  in the main report appendix. The equal-duration control is a different
  endpoint experiment and does not remove the midpoint length confound.
- Vectoring: all four scenes and full dose ranges remain. Segmented: 14/20
  positive, 5 negative, 1 zero, median 0.887. Smooth: 12/20 positive, 8 negative,
  median 0.625. Segmented is schematic and has no smooth-motion certificate.
- Hourly: the main 1h displays retain every hour, including NA; accepted D in
  14/24 hours on September 8 and 15/24 on September 11. The threshold and
  no-gate studies use different designs and are not substitutions for this main result.
- STAR is inactive. Its historical 15-feature Encoder results are not combined
  with the current 9-feature maneuver results.

## Shared code, history and report

- [code/](code/README.md): shared time alignment, QC, statistics, workflow dispatch
  and cross-study tools. The existing shared code location is unchanged.
- [histry/](histry/README.md): mixed historical records, the still-required strict-10s
  notebook, earlier combined reports, historical audit records and frozen source.
- [report/](report/README.md): combined report, directory/data-package notes and
  `figures/` for the existing cross-study images.

The [organization map](histry/organization-map.json) preserves original-to-current
paths and evidence hashes. Current code uses `code/evaluation_layout.py`; exact
execution snapshots retain their original paths. The old root `report.md` is
only a link redirect, preserving already published manuscript links.

This organization changes locations, paths and navigation only. No scientific
threshold, correlation, trajectory, embedding or figure was recalculated.
