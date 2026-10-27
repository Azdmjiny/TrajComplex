# Cross-Airport Complexity Evaluation

This experiment compares hourly D distributions across Singapore Changi (WSSS), Tokyo Haneda (RJTT), Hong Kong (VHHH), and Incheon (RKSI), using OpenSky trajectory data from September 2026. We examine whether typical D ranges can be shared across airports while keeping the Encoder and computation procedure fixed.

## Experimental setup

- **Trajectories:** airport-related arrivals and departures within a 100 km airport-centered region, with strict 10-second sampling and trajectory quality checks. The longest eligible segment is retained for each flight-hour.
- **Representation:** airport-centered ENU coordinates with barometric altitude, followed by the frozen epoch-90 Encoder (seed 43, 16 dimensions, sum pooling). Training feature standardization is retained; no airport-specific retraining or normalization is applied.
- **Hourly D:** one embedding per flight-hour forms each hourly point cloud. D is the log-log OLS slope of the correlation integral, using exact pairwise distances and 64 geometric radii.

The current analysis uses the **unfiltered full-scale** estimator: all radii with positive correlation counts enter the fit, without D acceptance gates or the original correlation-window selection. Trajectory quality checks remain in place. Mathematically undefined D values remain missing. This version differs from the repository's quality-gated dimension estimate.

## Shared intervals and validation

Shared central 50%, 75%, and 90% intervals correspond to Q25–Q75, Q12.5–Q87.5, and Q05–Q95. Quantiles are estimated from an airport-balanced empirical distribution, assigning equal total weight to each airport. The 75% interval was added after the initial 50% and 90% analysis.

September 1–20 is the calibration period; September 21–30 is the evaluation period, using each airport's local dates.

- **Temporal validation:** estimate a shared interval from all four calibration airports, then evaluate it separately at each airport.
- **Leave-one-airport-out validation:** estimate the interval from three calibration airports, then evaluate the omitted airport. Repeat for all four airports.

Two metrics are reported:

- **Coverage:** the percentage of computable evaluation hours inside the shared interval. The reference is the corresponding nominal 50%, 75%, or 90% coverage.
- **Width ratio:** shared interval width divided by the evaluation airport's own interval width at the same central proportion. A ratio of 1 indicates equal widths. The airport-specific evaluation interval is used only as a reference, not to adjust the shared interval.

Uncertainty is estimated using 2,000 day-block bootstrap replicates with seed 43. Calibration and evaluation dates are resampled independently, with synchronized date draws across airports and recalibration in each replicate.

## Code and execution

| File | Role |
|---|---|
| `preprocess.py` | Flight assignment, trajectory filtering, sampling, and ENU conversion |
| `run_complexity.py` | Frozen Encoder inference, hourly point clouds, and D estimation |
| `run_intervals.py` | Shared intervals, validation metrics, bootstrap intervals, and the distribution histogram |
| `config.json` | Airport references and experiment settings |
| `requirements.txt` | Python dependencies |

Run from the repository root:

```bash
python -m pip install -r eval/cross_airport/requirements.txt

python eval/cross_airport/preprocess.py \
  --hours hours.csv --flights flights.csv --output prepared

python eval/cross_airport/run_complexity.py \
  --hours prepared/prepared_hours.csv \
  --checkpoint Encoder/encoder/encoder.pt --output complexity

python eval/cross_airport/run_intervals.py \
  --input complexity/hourly_D.csv --output intervals
```

Output directories must be new. Paths are supplied through command-line arguments; additional options are listed by `--help`. Encoder source is reused from `Encoder/trajectory_encoder/`, and the checkpoint hash is recorded in `config.json`.

### Input format

- **Hourly manifest:** `airport,hour_utc,hour_utc_iso,hour_local,raw_path`. UTC times are Unix seconds; local timestamps include the UTC offset. Raw paths are absolute or relative to the manifest.
- **Raw hourly CSV/CSV.gz:** `time,icao24,lat,lon,baroaltitude,onground,lastposupdate,lastcontact,hour`. Observations use a UTC 10-second grid, coordinates in degrees, and altitude in meters.
- **Flight metadata:** `icao24,firstseen,lastseen,estdepartureairport,estarrivalairport`.
- **Interval analysis input:** `airport,hour_local,dimension`. Missing D is left empty; all expected hourly rows are retained.

Preprocessing produces a prepared-hour manifest and trajectory arrays. Complexity estimation produces hourly D and point clouds. Interval analysis produces shared bounds, validation metrics, input counts, and one four-airport histogram. The histogram displays D from 0 to 2.5 with a common bin width of 0.1; statistics use all finite D values.

## Scope

Only experiment code and configuration are included here; data, weights, and generated results are not included. Incheon is the Encoder training-source airport. Agreement in numerical ranges alone does not establish equal operational complexity or a universal high/low complexity threshold.
