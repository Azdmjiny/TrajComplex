# Paper figure set

Curated figures for the paper. All values come from stored
`evaluation/runs/segmented-15km` and `evaluation/runs/holding-equal-duration`
results; no encoder calls or new D estimates were made to produce this set.
The two non-copied figures are reproducible with
`evaluation/figures/make_combined_figure.py` and
`evaluation/runs/segmented-15km/source/make_paper_figures.py`.

## Main figures

| File | Suggested use | Caption |
|---|---|---|
| [holding-vs-vectoring-comparison.png](holding-vs-vectoring-comparison.png) / [.pdf](holding-vs-vectoring-comparison.pdf) | Main overview (left Holding, right Vectoring) | Top row puts every estimable scene/curve in one panel: Holding has 8/12 scenes with a jointly valid paired comparison (7/8 positive, median paired ΔD +0.034); Vectoring has all 15 curves from 3 estimable scenes (13/15 positive, median rho 0.829). Bottom row shows a representative case for each side: Holding 09-04 and Vectoring 09-15. |
| [segmented-positive-dose-response.png](segmented-positive-dose-response.png) / [.pdf](segmented-positive-dose-response.pdf) | Detailed positive result | Segmented 15 km vectoring produces a positive dose–D association at the scene level in all three estimable scenes. Thin grey lines are the five injection orders; the thick orange line is their median. Panel D summarizes all 15 curves: 13/15 positive, median rho 0.829, versus 9/15 and 0.600 for the smooth 15 km control. |
| [injection-geometry-smooth-vs-segmented.png](injection-geometry-smooth-vs-segmented.png) | Methods | Smooth S-curve and segmented trapezoid at the same 15 km peak. The segmented track holds 15 km for 300 s with 150 s straight ramps and a 30 s corner blend. It is a schematic stimulus, not a C2-certified maneuver. |
| [d-association-smooth-vs-segmented.png](d-association-smooth-vs-segmented.png) | Shape comparison | Smooth vs segmented association: the all-curve median, scene-level medians, and one representative dose response. |

## Control / supplement

| File | Suggested use | Caption |
|---|---|---|
| [holding-shared-cutoff-curves.png](holding-shared-cutoff-curves.png) | Holding control | Equal-duration terminal control at the same archived Holding cutoffs. Both arms increase D with dose; Holding is above straight in most comparable scenes, but the effect is smaller and mixed across scenes. |
| [holding-paired-differences.png](holding-paired-differences.png) | Supplement | Per-scene paired Holding-minus-Straight D differences at the same aircraft dose. Positive means Holding has the higher D. Five scenes have no accepted paired comparison and are marked as such. |

## Notes

- The positive result is specific to the segmented 15 km stimulus. The smooth
  15 km control is 9/15 positive, median 0.600; do not present the segmented
  number as a property of vectoring in general.
- `2026-09-14` has only four valid doses and is not estimable; it is omitted
  from the positive panels and noted in the figure.
- Two negative segmented curves are retained in panel D of the detailed
  positive figure (09-19 order 4 and 09-27 order 3).
- Holding is a control/supplement, not a second positive result. Four of the
  twelve Holding scenes have no accepted paired comparison.
