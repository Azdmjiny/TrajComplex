# Segmented 15 km Vectoring run (2026-10-25)

> Archived/separate study. See the subject README for the current main result; the settings and results below belong to this package.

Active four-scene evaluation:

- 600 s window, fixed 15 km peak;
- trapezoid lateral offset: 150 s straight out, 300 s plateau, 150 s straight
  back, 30 s corner blend;
- original 9-feature, fixed-epoch-90 Encoder (no STAR reference);
- D fit gate `min_r_squared=0.94`.

## Result

| Injection | Estimable curves | Positive | Median rho | Scene-level median |
|---|---:|---:|---:|---:|
| Smooth 15 km control | 15/20 | 9/15 | 0.600 | −0.086 |
| **Segmented 15 km** | **15/20** | **13/15** | **0.829** | **0.714** |

`2026-09-14` has only three injectable candidates (four doses) and is not
estimable under either shape. Two negative curves are retained:
`2026-09-19` order 4 (−0.943) and `2026-09-27` order 3 (−0.086).

## Files

- `population/` — per-scene baseline and segmented left/right arrays, records
  and generation summary.
- `results/segmented/` — full diagnostics, embeddings and summary.
- `results/smooth-control/` — smooth 15 km control diagnostics.
- `figures/` — shape and D-association figures.
- `source/` — exact generators/runners used for the run. They expect the
  workspace paths documented in the main report; they are provenance, not the
  current production entrypoint. `source/make_paper_figures.py` rebuilds the
  positive dose-response figure from the stored JSON only.

## Method note

The segmented stimulus is schematic: it does not carry the smooth generator’s
C2 / 2 m s⁻² / 35° motion certificate. `vectoring_population.py` uses the
segmented generator when `SEGMENTED=True` and skips the deformed-kinematics
rejection in that mode.
