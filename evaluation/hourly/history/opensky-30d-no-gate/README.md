# OpenSky 30-day raw-scene analysis (no quality gate)

> Archived/separate study. See the subject README for the current main result; the settings and results below belong to this package.

This run answers the “no gate” request directly: all 720 hourly raw scenes,
all 19,306 encodable trajectories, no candidate/QC/dedup screening.

- D is reported as a **raw log–log slope**, not a quality-gated D.
- All radii with `0 < C(r) < 1` are used; at least two scales are required.
- No C(r) bounds, radius-ratio gate or R² threshold.
- 20 nested random orders per scene; every N from 5 to the scene total.
- The Encoder still requires at least 30 input points; all 19,306 tracks met it.

## Main results

- 720 hourly scenes; 718 have at least 5 aircraft.
- 16,426 hourly-N median raw slopes.
- Median raw slope: 1.127 at N=5, 1.333 at N=20, 1.398 at N=30,
  1.458 at N=40, 1.437 at N=50.
- No negative raw slopes were observed.

The curve rises at low N and flattens after about 30 aircraft. This is not
evidence that adding aircraft causes higher complexity; the low-N rise is
dominated by small-sample geometry and the absence of quality gates.

## Figures

| File | Content |
|---|---|
| `figures/A-boxplot-no-gate.png` | Boxplots by aircraft-count bin; all 720 scenes |
| `figures/B-hexbin-no-gate.png` | Hexbin density; colour is the number of hourly-N estimates |
| `figures/C-band-curves-no-gate.png` | Median and 10–90% band; 09-11 sample curves |
| `figures/24h-no-gate-09-08-09-11.png` | 24h full-scene raw slopes for 09-08 and 09-11 |
| `figures/24h-threshold15-truncated.png` | 24h display with N<15 assigned floor 0.813 |
| `figures/A-daynight-bands.png` | Day/night raw slopes, no truncation |
| `figures/A-daynight-boxplot.png` | Day/night boxplots by N bin |
| `figures/C-tobit-predictions.png` | Tobit-like day/night model (supplementary) |

## Files

- `results/d-vs-n-no-gate.json` — per-hour raw curves.
- `results/summary.json` — aggregate medians.
- `results/encoding-summary.json` — 720 scene counts; no raw tracks.
- `results/daynight-model.json` — coefficients, bootstrap CIs, sensitivity.
- `results/truncation-threshold15.json` — affected hours and floor.
- `source/` — provenance scripts. They expect the local embedding package and
  are not portable entrypoints.

Raw embeddings, source trajectories, model weights and private inputs are not
published.
