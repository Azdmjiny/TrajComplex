# D versus aircraft count: one-scene pilot

This is a one-scene feasibility test, not a general volume experiment.

- Scene: `2026-09-08-1h-20` (2026-09-08 20:00 UTC+08), N=56.
- Design: 100 nested random orders; start at 5 aircraft and add one at a
  time to the full scene.
- D uses the frozen 64-radius grid and the frozen embeddings.
- Low-N exploratory gate: `min_samples=n`, `min_fit_points=4`,
  `R²>=0.90`.
- Standard-gate reference: `min_fit_points=8`, `R²>=0.94`, plotted only for
  N>=20.

At N=5–10 no fit is possible on the fixed radius grid. N=11–14 is based on
1–8 valid orders out of 100 and is not a reliable median; open markers and the
valid-fraction panel make this explicit. From N=20 the valid rate is 73/100,
and from N=30 it is 98–100/100.

## Files

- [report.md](report.md) — result and interpretation.
- [results/d_vs_n.json](results/d_vs_n.json) — per-N median, 10–90% range,
  valid counts, standard-gate median and rejection reasons.
- [figures/d-vs-n-2026-09-08-1h-20.png](figures/d-vs-n-2026-09-08-1h-20.png)
  (also PDF).
- `source/` — provenance scripts; they expect the local frozen embedding
  package and are not portable entrypoints.

No Encoder calls or new trajectories were generated. D was recomputed from the
frozen hourly embeddings.
