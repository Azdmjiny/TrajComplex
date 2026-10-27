# Evaluation figure index

The current Holding midpoint figures and latest Vectoring comparison have different run provenance. Plotting itself uses saved results only. The midpoint response figures use [plot_holding_primary.py](../code/plot_holding_primary.py). The earlier endpoint historical-range figure uses [plot_holding_historical_ranges.py](../code/plot_holding_historical_ranges.py); endpoint/Vectoring complete-scene figures use [make_review_figures.py](../code/make_review_figures.py). PNG previews, SVG and vector PDF versions share the same basename. No scenes, negative curves or unavailable correlations are removed.

| Figure | PNG | Vector PDF | Meaning |
|---|---|---|---|
| Endpoint Holding historical range | [Preview](holding-historical-range-main.png) | [PDF](holding-historical-range-main.pdf) | All 7 archived-cutoff ranges only, 33 coefficients including negatives; full tails and control in Appendix H |
| Endpoint Holding full-range appendix | [Preview](../archive/holding-all-scenes-dose-2026-10-26.png) | [PDF](../archive/holding-all-scenes-dose-2026-10-26.pdf) | All 12 scenes, both +240-second arms; full range, common historical cutoffs and failed-fit markers |
| Endpoint Holding paired-difference appendix | [Preview](holding-all-scenes-paired-difference.png) | [PDF](holding-all-scenes-paired-difference.pdf) | Same scene/order/dose, both fits valid; positive means Holding has higher D |
| Historical 10-second Vectoring dose response | [Preview](vectoring-all-scenes-dose.png) | [PDF](vectoring-all-scenes-dose.pdf) | All 4 scenes × 2 shapes, every order, common D axis; includes scene with too few doses for rho |
| Historical 10-second Vectoring correlations | [Preview](vectoring-all-scenes-correlations.png) | [PDF](vectoring-all-scenes-correlations.pdf) | Every order, negative coefficients and explicit NA; display order = saved replicate + 1 |

## Endpoint control and Vectoring captions

The endpoint Holding control uses its original R²≥0.98; current Vectoring uses R²≥0.94. The midpoint Holding main presentation below now uses R²≥0.94. The figures do not harmonize these different studies. Thin dose curves represent dependent injection orders, thick curves medians of available orders. They are not confidence intervals. NA breaks curves; bottom crosses are status markers, not D. Holding correlations use common accepted doses in both arms, whereas plotted arm medians use each arm's available estimates. These are different summaries and must not be equated.

Holding cutoffs are shared between arms and were inherited from historical midpoint results; the full tail is retained in Appendix H, and no new peak is chosen. Paired differences require two accepted fits but not an accepted zero-dose baseline. The segmented 15 km Vectoring result is a schematic stimulus, without the smooth control's motion certificate. All 115 D estimates in each historical 10-second Vectoring arm pass; one scene has only 4 dose levels, so its correlations are unavailable.

The [main report](../report.md) contains the full captions, numerical summaries and limits.

## Raw 30-day no-gate

The [raw 30-day run](../runs/opensky-30d-no-gate/report.md) has its own figure
set: boxplot, hexbin, band/sample curves, 24h raw views, the N<15 floor view,
and the day/night Plan A/C comparison. These are **raw slopes**, not
quality-gated D; do not mix them with the maneuver figures above.

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

The teammate's [Holding-versus-Vectoring small multiples](holding-vs-vectoring-comparison.png) ([PDF](holding-vs-vectoring-comparison.pdf)) and [renderer](make_combined_figure.py) are retained, with jittered order points and thin order lines. Left: Holding scenes September 1, 4 and 10, with order points, mean Holding D and mean straight D. Right: the three correlation-estimable Vectoring scenes, with jittered order points, order lines and mean D. This compact view includes a subset of scenes; use the new all-scene figures for complete coverage and explicit NA. Do not interchange its mean curves with the new median curves.

This is an earlier endpoint-control/19-candidate Vectoring view, not the latest midpoint/26-candidate comparison.

## Earlier endpoint historical-range figure and Appendix H

The [endpoint historical-range figure](holding-historical-range-main.png) shows only the archived ranges; full tails are preserved in Appendix H. No cutoff is changed. The [complete appendix](../holding-paper-appendix.md) retains all 12 planned scenes, full-range outcomes and the equal-duration control. All seven historical cutoffs are included, rather than selecting the most positive scenes. Panel H contains 30 positive and 3 negative coefficients, with 2 other planned orders explicitly unavailable. Historical cutoffs are outcome-derived, so this is a range-conditional exploratory result, not an independent validation of an operating limit. Straight control median rho 0.598 is disclosed in the main figure and report.

```bash
python evaluation/code/plot_holding_historical_ranges.py --output /new/local/holding-main-figure
```

Use `--show-full-tail` to reproduce the earlier grey-tail view. Publish reviewed PNG/PDF/SVG only; keep the renderer's manifest local. The renderer checks stored cutoff membership, paired-dose counts, saved coefficient aggregates and unchanged source hashes without calculating new D values. Per-panel y-axes are explicitly labelled, and the median curve is not used to calculate the reported coefficients.

## Corrected 10-second midpoint response: primary R² ≥ 0.94

- [Main absolute-D dose response](holding-midpoint-prepeak-all-scenes.png) ([PDF](holding-midpoint-prepeak-all-scenes.pdf)): all seven archived pre-peak ranges, 34/35 positive order coefficients, median 0.884. One negative is retained. Labelled panel-specific D scales.
- [Baseline-relative companion](holding-midpoint-prepeak-delta.png) ([PDF](holding-midpoint-prepeak-delta.pdf)): all five accepted-baseline scenes, 24/25 positive coefficients, median 0.866; common ΔD scale.
- [Complete-range appendix](holding-midpoint-full-range-appendix.png) ([PDF](holding-midpoint-full-range-appendix.pdf)): all 12 planned scenes, including unavailable estimates; common D scale. Full-range median rho 0.218, 28/40 positive.

All are hour-selected, complete-tail midpoint injections, not post-injection hour-clipped traffic. Archived endpoints are outcome-selected and unchanged; the 0.94 gate is a declared post-analysis revision. Colored points show accepted estimates, bottom crosses unavailable estimates, and dark lines unsmoothed available-order means. Correlations are per-order, not correlations of the mean. The [complete caption](../holding-midpoint-response.md) includes the distinct endpoint duration control and dependent-repeat caveat. SVG versions accompany all three figures. The previous [0.98 report and figures](../archive/holding-midpoint-r098/holding-midpoint-response.md) remain archived.

```bash
python evaluation/code/plot_holding_primary.py --output /new/local/holding-primary
```

Only reviewed figures and reports are publication artifacts; screening records and manifests remain local.

## Latest repaired 20-second Vectoring

- [Full-range before/after curves](../runs/vectoring-20s-repaired/figures/vectoring-full-range-before-after.png) ([PDF](../runs/vectoring-20s-repaired/figures/vectoring-full-range-before-after.pdf)): all four scenes, both shapes, 25 → 26 candidates; means and individual orders; no truncation.
- [Every order correlation](../runs/vectoring-20s-repaired/figures/vectoring-order-correlations-before-after.png) ([PDF](../runs/vectoring-20s-repaired/figures/vectoring-order-correlations-before-after.pdf)): 20 coefficients per shape, including all negative and zero values. The earlier 19-candidate figures above are not this run.

Full caption, complete ledger and limitations: [latest report](../runs/vectoring-20s-repaired/report.md). New derived data remain local.

## Concurrent endpoint-control display

The [eight-scene endpoint figure](holding-main-8-scenes.png) ([PDF](holding-main-8-scenes.pdf)) is retained from the remote branch. Its renderer is [make_holding_main.py](../code/make_holding_main.py). It shows the separate R²≥0.98 endpoint experiment, not primary midpoint Holding. The former twelve-scene dose view remains in [the archive](../archive/holding-all-scenes-dose-2026-10-26.pdf).
