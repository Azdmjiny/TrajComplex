# Evaluation

Start with the [current report](report.md). The active evaluation includes the
[repaired 20-second Vectoring comparison](runs/vectoring-20s-repaired/report.md) and the [Changi hourly application case](runs/changi-hourly/report.md); the previous 5 km report is archived as
[archive/report-5km-2026-10-24.md](archive/report-5km-2026-10-24.md).

## Current status

- **Changi hourly application:** complete 24h displays for September 11 and September 8, combining D, aircraft counts before/after QC, and estimability. The deduplicated main result has accepted D in 15/24 and 14/24 hours respectively; the original 14/24 and 11/24 results remain an appendix comparator. NA is retained and lines never bridge failed hours. This is an application case with explicit availability limits, not a claim of 24 reliable D values or causal weather validation. Fixed-N and weather comparisons remain descriptive supplements. See the [case report](runs/changi-hourly/report.md).
- **Vectoring (latest):** repaired 20-second quality matching, 26 candidates,
  the same 157 backgrounds, 15 km target and R²≥0.94. Segmented: 14/20 positive,
  5 negative and 1 zero, median rho 0.887; smooth: 12/20 positive and 8 negative,
  median 0.625. These aggregate values are unchanged from the prior 25-candidate
  version; September 15 improves slightly. All four scenes and full doses are
  retained. See [the before/after report](runs/vectoring-20s-repaired/report.md).
- **Holding response:** corrected 10-second midpoint results, now with primary R² >= 0.94 and unchanged archived pre-peak ranges: 34/35 positive order coefficients, median rho 0.884. Five baseline-valid scenes support delta-D panels (24/25 positive; median 0.866). The prior 0.98 presentation is archived. These are outcome-selected exploratory ranges. Complete injected tails are retained, not clipped to the source hour. The separate endpoint duration control remains unchanged (matched retained medians 0.661 Holding, 0.598 straight). See the [midpoint report](holding-midpoint-response.md).
- **STAR:** inactive. The STAR-relative Encoder and official-STAR pilot are
  archived; do not mix their numbers with this report. See
  [STAR_INACTIVE.md](STAR_INACTIVE.md).

## Navigation

| Location | Contents |
|---|---|
| [report.md](report.md) | Active maneuver results and hourly application case |
| [runs/changi-hourly](runs/changi-hourly/README.md) | 1h results, QC counts, complete 24h status figures and reproducible reporting |
| [runs/vectoring-20s-repaired](runs/vectoring-20s-repaired/report.md) | Latest Vectoring, 26 versus 25 candidates; reports/figures/source only |
| [runs/vectoring-certificate-repair](runs/vectoring-certificate-repair/report.md) | Numerical certificate repair and screening, no correlation run |
| [runs/vectoring-time-window-sensitivity](runs/vectoring-time-window-sensitivity/report.md) | Earlier 10/15/20-second comparison, before the certificate repair |
| [runs/segmented-15km](runs/segmented-15km/) | Historical 10-second quality-matching reference, 19 candidates |
| [runs/README.md](runs/README.md) | Index of every result package |
| [code/README.md](code/README.md) | Explicit-input screening, inference and diagnostic commands |
| [archive](archive/) | Superseded reports and legacy snapshots |
| [vectoring-study-history.md](vectoring-study-history.md) | Experiment and screening history |

## Active code

- `code/report_changi_hourly.py` — the sole current hourly report builder; saved records only, no inference, D estimation or new draws. Use `--input LOCAL_SAVED_PACKAGE --preprocessing position-dedup --output NEW_DIRECTORY` for the main result (or `--preprocessing original` for the appendix). Its derived input data remain local.
- `code/vectoring_path.py` — `PEAK=15000`; `generate_segmented()` (segmented)
  and `generate()` (smooth control).
- `code/vectoring_population.py` — `SEGMENTED=True`; 10-second population uses
  the segmented generator and skips the deformed-kinematics rejection.
- `code/run_vectoring_eval.py` — `MAX_OFFSET=15000`; legacy five-second
  helpers remain for regression tests.
- `code/run_evaluation.py` — explicit workflow entrypoint, no implicit run.
- `../complexity/calculator.py` — `min_r_squared=0.94`.

The segmented arm is a schematic stimulus and does not carry the smooth
generator’s C2 / 2 m s⁻² / 35° motion certificate. No raw data, model weights
or authentication caches are added by this publication.

## Current presentation update

The [figure index](figures/README.md) separates current midpoint Holding, latest repaired Vectoring and older endpoint/10-second views. All retained scopes, negative correlations and unavailable results are disclosed. Latest Vectoring execution/reporting snapshots are in its run package; `code/make_review_figures.py` reproduces the earlier endpoint/10-second presentation.

## Holding paper layout

The earlier endpoint presentation uses the [historical-range figure](figures/holding-historical-range-main.png) with [Appendix H](holding-paper-appendix.md). The main panels retain the original cutoff ranges and negative order coefficients; full-range tails are shown in Appendix H. Equal-duration control results are disclosed in the main report and detailed in the appendix. This presentation introduces no experiment or new cutoff.

## Corrected midpoint Holding presentation (2026-10-27)

The [midpoint response report](holding-midpoint-response.md) presents saved 10-second midpoint results: five baseline-valid delta panels, seven archived pre-peak ranges with correlations, and all 12 full-range scenes. The primary fit gate is R² >= 0.94; archived 0.98 fits are re-screened without changing slopes or finding new peaks. Reproduce with `code/plot_holding_primary.py --output NEW_DIRECTORY`. Source-hour selection retains complete injected tails; it does not enforce a post-injection hour boundary. The [endpoint control appendix](holding-paper-appendix.md) remains separate. No experiments were rerun.
