# Changi 24-hour threshold review

**Question:** can the 24h application display be made more complete without
pretending that a low-traffic hour has a measured D?

**Short answer:** yes for most hours, but not all. A 3-hour centered window
removes the N bottleneck; lowering the 1h gate recovers most of the remaining
hours. A small number of hours still fail the log–log fit, and those remain
gaps.

## Coverage

| Rule | 2026-09-08 | 2026-09-11 |
|---|---:|---:|
| 1h, N>=30, R²>=0.94 (published) | 14/24 | 15/24 |
| 1h, N>=20, R²>=0.90 | 18/24 | 20/24 |
| 1h, N>=15, R²>=0.90 | 18/24 | 21/24 |
| 3h, N>=30, R²>=0.94 | 20/24 | 21/24 |
| **3h, N>=30, R²>=0.90 (primary display)** | **21/24** | **22/24** |

The 3-hour window is built from the union of the center hour and its two
neighbors. When the same aircraft appears in more than one hour, the center
hour embedding is used; otherwise the nearest available hour is used. This
keeps one embedding per aircraft and avoids counting the same aircraft twice.

![24h threshold comparison](figures/changi-24h-threshold-comparison.png)

## What the figure shows

- Blue: 3h rolling D, N>=30, R²>=0.90.
- Orange dashed: 1h D, N>=20, R²>=0.90.
- Grey bands: 3h window has no accepted fit.
- Open orange circles: 1h N=15–19, accepted only at the lower gate; they are
  low-confidence, not part of the main 1h curve.
- Triangles: assigned floor for 1h N<15 (floor = 0.7633, the minimum accepted
  1h D in this review). They are not measured D.

## Remaining gaps

- 2026-09-08 3h: hours 01, 02 and 03 fail `poor_linear_fit`; their N is
  57/45/42, so this is a fit limitation, not an insufficient-aircraft problem.
- 2026-09-11 3h: hours 00 and 01 fail `poor_linear_fit`; N is 40/51.
- 2026-09-08 1h: hours 00–04 and 13 have no accepted N>=20 estimate.
- 2026-09-11 1h: hours 00, 02, 03 and 04 have no accepted N>=20 estimate.

The remaining 3h gaps are **not** filled by the low-traffic floor: at N>=40 a
floor would misrepresent a poor fit as low complexity.

## Interpretation

The original 14/24 and 15/24 counts were dominated by `insufficient_samples`;
R² was not the main cause. A 3-hour window fixes most of the sample-size
problem while keeping N>=30. The 1h lower gate is a useful exploratory view,
but it is not a substitute for the 3h primary display. The two curves agree on
the broad day-night pattern; local peaks differ, which is expected because the
3h curve is smoothed and the 1h curve uses fewer aircraft.

No 24/24 curve is claimed. The correct statement is: **21/24 and 22/24 hours
have a 3h estimate; the remaining hours are poor fits and stay NA.**

## Limitations

- 3h pooling mixes adjacent hours; each point is a centered window, not a
  strict hourly estimate.
- The 1h N>=20 curve is exploratory; its uncertainty is larger than the 3h
  curve, especially at N=20–25.
- The assigned floor is a visualization convention, not a measurement. It
  should never be pooled with measured D or described as zero complexity.
- The fixed-N=30 3h subset is not used as a main estimate: 30-point subsets
  often fail the fit gate, so a fixed-N median would be based on a selected
  minority of draws.
- No encoder calls were made for this review; all D values use the frozen
  deduplicated embeddings and the original 64-radius grid.
