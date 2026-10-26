# Current paper figures

All four current maneuver figures use existing saved results only. The renderer is [make_review_figures.py](../code/make_review_figures.py). PNG previews, SVG and vector PDF versions share the same basename. No scenes, negative curves or unavailable correlations are removed.

| Figure | PNG | Vector PDF | Meaning |
|---|---|---|---|
| Holding dose response | [Preview](holding-all-scenes-dose.png) | [PDF](holding-all-scenes-dose.pdf) | All 12 scenes, both +240-second arms; full range, common historical cutoffs and failed-fit markers |
| Holding paired difference | [Preview](holding-all-scenes-paired-difference.png) | [PDF](holding-all-scenes-paired-difference.pdf) | Same scene/order/dose, both fits valid; positive means Holding has higher D |
| Vectoring dose response | [Preview](vectoring-all-scenes-dose.png) | [PDF](vectoring-all-scenes-dose.pdf) | All 4 scenes × 2 shapes, every order, common D axis; includes scene with too few doses for rho |
| Vectoring correlations | [Preview](vectoring-all-scenes-correlations.png) | [PDF](vectoring-all-scenes-correlations.pdf) | Every order, negative coefficients and explicit NA; display order = saved replicate + 1 |

## Captions and interpretation

Holding uses its original R²≥0.98; current Vectoring uses its original R²≥0.94. The figures do not harmonize these different studies. Thin dose curves represent dependent injection orders, thick curves medians of available orders. They are not confidence intervals. NA breaks curves; bottom crosses are status markers, not D. Holding correlations use common accepted doses in both arms, whereas plotted arm medians use each arm's available estimates. These are different summaries and must not be equated.

Holding cutoffs are shared between arms and were inherited from historical midpoint results; the full tail is shown, and no new peak is chosen. Paired differences require two accepted fits but not an accepted zero-dose baseline. The segmented 15 km Vectoring result is a schematic stimulus, without the smooth control's motion certificate. All 115 D estimates in each current Vectoring arm pass; one scene has only 4 dose levels, so its correlations are unavailable.

The [main report](../report.md) contains the full captions, numerical summaries and limits.

## Hourly application

Use the [deduplicated 24h main figures](../runs/changi-hourly/report.md) with D, before/after-QC counts and status. The [original figures](../runs/changi-hourly/appendix-original/report.md) are the appendix comparator. Neither version has 24 accepted D values. The original-versus-deduplicated comparison retains all hours and all three schemes.

## Historical views retained

`holding-shared-cutoff-curves.png`, `holding-paired-differences.png`, `segmented-positive-dose-response.png/.pdf` and `d-association-smooth-vs-segmented.png` remain earlier views of the same saved maneuver results. They are not the new preferred complete-scene figures. The old compact positive Vectoring panel omitted the non-estimable-correlation scene from its dose panels; the new figures include it explicitly. The [geometry illustration](injection-geometry-smooth-vs-segmented.png) remains a methods illustration.

Reproduce locally, without running an experiment:

```bash
python evaluation/code/make_review_figures.py --output /new/local/figure-package
```

The render manifest stays local. Source data and saved statistics are not changed.

## Concurrent compact overview retained

The teammate's [Holding-versus-Vectoring small multiples](holding-vs-vectoring-comparison.png) ([PDF](holding-vs-vectoring-comparison.pdf)) and [renderer](make_combined_figure.py) are retained without modification. Left: Holding scenes September 1, 4 and 10, with order points, mean Holding D and mean straight D. Right: the three correlation-estimable Vectoring scenes, with order points and mean D. This compact view includes a subset of scenes; use the new all-scene figures for complete coverage and explicit NA. Do not interchange its mean curves with the new median curves.
