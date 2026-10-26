# Evaluation

Start with the [current report](report.md). The active evaluation includes the
15 km segmented Vectoring run and the [Changi hourly application case](runs/changi-hourly/report.md); the previous 5 km report is archived as
[archive/report-5km-2026-10-24.md](archive/report-5km-2026-10-24.md).

## Current status

- **Changi hourly application:** complete 24h displays for September 11 and September 8, combining D, aircraft counts before/after QC, and estimability. The deduplicated main result has accepted D in 15/24 and 14/24 hours respectively; the original 14/24 and 11/24 results remain an appendix comparator. NA is retained and lines never bridge failed hours. This is an application case with explicit availability limits, not a claim of 24 reliable D values or causal weather validation. Fixed-N and weather comparisons remain descriptive supplements. See the [case report](runs/changi-hourly/report.md).
- **24h threshold review:** a centered 3h window with N>=30 and R²>=0.90 gives 21/24 and 22/24 accepted hours; the 1h N>=20 exploratory view gives 18/24 and 20/24. Remaining 3h gaps are poor fits at N=40–57, not insufficient aircraft, so they stay NA. N<15 is shown as an assigned floor, not a measured D. See the [review](runs/changi-thresholds/report.md).
- **Vectoring (active):** fixed 15 km peak, segmented trapezoid injection
  (150 s out / 300 s plateau / 150 s back, 30 s corner blend), original
  9-feature Encoder, `min_r_squared=0.94`, no STAR. Result: 13/15 positive
  curves, median rho 0.829, 3/3 estimable scenes positive. The smooth 15 km
  control is 9/15, median 0.600, 1/3 scenes positive.
- **Holding:** unchanged equal-duration terminal control. At the same archived
  cutoffs and jointly valid doses, median rho is 0.661 for Holding and 0.598
  for straight flight; six of seven comparable scene summaries have positive
  Holding-minus-Straight D differences. Conditional descriptive results, not
  validation of operational complexity.
- **STAR:** inactive. The STAR-relative Encoder and official-STAR pilot are
  archived; do not mix their numbers with this report. See
  [STAR_INACTIVE.md](STAR_INACTIVE.md).

## Navigation

| Location | Contents |
|---|---|
| [report.md](report.md) | Active maneuver results and hourly application case |
| [runs/changi-hourly](runs/changi-hourly/README.md) | 1h results, QC counts, complete 24h status figures and reproducible reporting |
| [runs/changi-thresholds](runs/changi-thresholds/report.md) | 3h primary / 1h exploratory threshold review and low-traffic floor |
| [runs/segmented-15km](runs/segmented-15km/) | Frozen population, source scripts, full diagnostics and figures |
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

The [four all-scene maneuver figures](figures/README.md) retain full dose ranges, negative correlations and unavailable results. Reproduce with `code/make_review_figures.py`; no D rerun is needed.
