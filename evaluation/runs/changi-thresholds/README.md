# Changi 24h threshold review

This run tests whether the 24-hour display can be made more complete without
silently treating unavailable estimates as zero.

- **Primary 24h display:** centered 3-hour window, unique aircraft, N>=30,
  R²>=0.90.
- **Exploratory 1h display:** N>=20, R²>=0.90.
- **Low-traffic:** 1h N=15–19 is shown as a low-confidence point when
  available; N<15 gets an assigned floor, not a measured D.
- **Maneuver primary results are unchanged:** the 15 km segmented and Holding
  studies keep their original N/R² gates. This review is an application layer.

The 3-hour window does not reach 24/24: 09-08 has three and 09-11 has two
poor-fit hours. Those are retained as gaps; no value is interpolated. The 1h
lower gate reaches 18/24 and 20/24; the remaining low-N hours are the reason
the assigned floor exists.

## Files

- [report.md](report.md) — interpretation and limitations.
- [results/summary.json](results/summary.json) — coverage and floor.
- [results/coverage.csv](results/coverage.csv) — N/R² variants.
- [results/threshold-review.json](results/threshold-review.json) — per-hour
  full D, fixed-N diagnostics and 1h variants.
- [figures/changi-24h-threshold-comparison.png](figures/changi-24h-threshold-comparison.png)
  (also PDF/SVG).
- `source/` — provenance scripts. They expect the local frozen embedding
  package and are not portable entrypoints.

No Encoder calls, raw downloads, trajectory generation or threshold changes
were made to the published maneuver results. D was recomputed from the frozen
deduplicated hourly embeddings only.
