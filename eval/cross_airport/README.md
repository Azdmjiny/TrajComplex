# Cross-airport D interval evaluation

This experiment asks whether hourly embedding-space complexity values share a typical numerical range across airports. It compares Changi (WSSS), Haneda (RJTT), Hong Kong (VHHH), and Incheon (RKSI), but accepts other airports and dates through configuration and input files. It does not train or fine-tune the Encoder.

## Method

1. Assign airborne observations to airport-related flights using departure/arrival metadata and flight time windows. Exclude unknown or ambiguous assignments. Within each flight-hour, retain the longest eligible contiguous segment (earliest segment on ties).
2. Filter observations within a 100 km airport circle. Apply position freshness, physical plausibility, and strict UTC-anchored 10-second sampling rules. Convert positions to airport-centered ENU. Horizontal coordinates use position-update timestamps; altitude uses snapshot timestamps. Barometric altitude produces an ENU proxy, not a verified ellipsoidal height.
3. Apply the repository's frozen 16-dimensional, sum-pooled Encoder using checkpoint feature standardization. Each flight-hour contributes one vector; each hour is one point cloud. Do not normalize separately by airport.
4. Estimate D using all exact Euclidean pair distances for i<j, 64 geometric radii between the minimum and maximum positive pair distances, strict distance<radius counts, and log-log ordinary least squares over all radii with positive correlation counts.
5. Estimate shared central 50%, 75%, and 90% intervals using an airport-balanced inverse empirical CDF. Each airport has equal total weight regardless of its number of computable hours. Central c% uses quantiles (1-c/100)/2 and (1+c/100)/2.
6. Temporal validation: calibrate on all airports before the local-date cutoff, freeze the interval, and evaluate on each airport after the cutoff. Leave-one-airport-out (LOAO): calibrate on the other airports before the cutoff and evaluate the omitted airport after it. Recalibrate for each fold.

The example cutoff is September 21, 2026: September 1-20 for calibration and September 21-30 for evaluation. Full-month histogram summaries do not enter calibration. The original study tested 50% and 90% first; 75% was subsequently added as an exploratory analysis.

## Important estimator distinction

This is the **UNFILTERED_FULL_SCALE_EXPLORATORY** version used by the final cross-airport interval experiment. It removes D acceptance gates on cloud size, distinct points, temporal coverage, pair counts, fit R-squared, slope sign, and upper dimension, and removes the original correlation-window selection. Trajectory preprocessing QC is retained. This full-scale descriptive slope is not interchangeable with the repository's quality-gated scale-selected dimension estimate.

Only mathematical undefinedness is retained: nonfinite inputs, fewer than two points, no varying positive distance range, or fewer than two log-defined radii. Undefined D remains missing, not zero. Zero-distance pairs remain in the correlation denominator. A mathematically defined zero slope is retained.

## Environment

From the repository root, install dependencies into your own environment:

```bash
python -m pip install -r eval/cross_airport/requirements.txt
```

Use a PyTorch build suitable for your CPU/CUDA environment. CPU is the default. Encoder/model source is reused from `Encoder/trajectory_encoder/`; it is not duplicated here. Obtain the frozen checkpoint separately (the repository's `Encoder/encoder/encoder.pt`, if available). The example checkpoint SHA256 is recorded in `config.json`; the loader checks it and the epoch-90, seed-43, 16D, sum-pooling contract. Supply another compatible checkpoint and its hash only as an explicitly different experiment.

## Input contracts

You provide your own data. No data, weights, point clouds, numerical results, or generated figures are included.

### Raw trajectory entry point

Prepare an hourly manifest CSV with columns:

| Column | Meaning |
|---|---|
| airport | Code matching a key in config.json |
| hour_utc | Integer Unix seconds at the start of the hour |
| hour_utc_iso | Unique filesystem-safe UTC hour key, e.g. 2026-09-01T00Z |
| hour_local | ISO timestamp with explicit offset, e.g. 2026-09-01T08:00:00+08:00 |
| raw_path | CSV or CSV.gz path, absolute or relative to this manifest |

Include every expected hour, including empty hours. Each raw file must contain `time,icao24,lat,lon,baroaltitude,onground,lastposupdate,lastcontact,hour`. Times are Unix seconds; latitude/longitude are degrees and altitude is meters. `hour` equals the manifest hour; `time` is inside the hour and on a UTC 10-second grid. `onground` must explicitly be false for airborne observations. For another altitude field, change `altitude` in config and supply that column. Conflicting duplicate aircraft/timestamp rows are excluded rather than arbitrarily repaired.

Provide one flight metadata CSV with `icao24,firstseen,lastseen,estdepartureairport,estarrivalairport`. The first/last timestamps are Unix seconds and inclusion is inclusive. Use observations already sampled on the required grid; this runner does not turn arbitrary irregular raw telemetry into the original study's snapshot contract. OpenSky is one possible source, not a requirement. No downloader or authentication logic is included.

```bash
python eval/cross_airport/preprocess.py --hours /path/hours.csv --flights /path/flights.csv --output /path/prepared
python eval/cross_airport/run_complexity.py --hours /path/prepared/prepared_hours.csv --checkpoint /path/encoder.pt --output /path/complexity
python eval/cross_airport/run_intervals.py --input /path/complexity/hourly_D.csv --output /path/intervals
```

All output directories must be new. Inputs are read-only. Run each command with `--help` for options; use `--config /path/config.json` to supply your own settings and `--repo-root /path/TrajComplex` if needed.

### Prepared trajectory entry point

You may skip preprocessing by supplying a manifest with `airport,hour_utc,hour_local,prepared_path`. Each NPZ contains `enu_m` (total points,3), `time` (total points), `offsets` (trajectories+1), and unique `flight_ids` (trajectories). Every segment has at least 30 points, finite ENU coordinates, and uniform 10-second sampling. Empty hours use empty arrays and offsets=[0]. Relative prepared paths are resolved against the manifest directory.

### Hourly D entry point

You may skip Encoder inference and provide a CSV with `airport,hour_local,dimension`. Include missing D rows as empty values and retain all expected hours. Timestamps need explicit UTC offsets. The set of airport codes must equal the configured airports. Use a consistent D definition across all airports; mixing gated and full-scale estimates invalidates the comparison. Changing airports, dates, sampling, checkpoint, or fitting rules defines a new experiment rather than reproducing the original numbers.

## Metrics

For shared interval [L,U] and n computable evaluation hours:

- **Coverage (%)** = 100 * number of evaluation D values satisfying L <= D <= U / n. Compare against the corresponding nominal 50%, 75%, or 90%, not against 100%. Overcoverage may reflect an overly broad interval.
- **Width ratio** = (U-L) / (the evaluation airport's own upper quantile - lower quantile), at the same central proportion. The denominator uses evaluation data solely as a reference and never modifies the calibrated interval. A ratio of 1 means equal widths; 1.4 means the shared interval is 40% wider. Similar width does not imply similar location.

Missing D values are excluded from metric denominators and counted in input support. A zero airport-specific width gives an undefined ratio. Lower-tail and upper-tail miss percentages are also recorded. No 80% coverage or 1.5 width-ratio success cutoff is imposed.

The default 2,000 day-block bootstrap replicates use seed 43. Calibration and evaluation dates are resampled independently, with synchronized local-date draws across airports; intervals are recalibrated within each replicate. Pointwise percentile 95% intervals and successful replicate counts are reported for coverage and width ratio. Use `--bootstrap-repeats 0` for point estimates only. Calendar coverage should be checked when adapting to incomplete datasets; the runner reports supplied/finite hours, not a claim of complete source coverage.

## Generated outputs (not committed)

- Preprocessing: prepared hourly NPZs, prepared_hours.csv, and an audit.
- Complexity: hourly_D.csv, hourly point clouds/correlation curves, and the computation config.
- Intervals: shared_intervals.csv, validation_metrics.csv, input_support.csv, analysis_config.json, and **one histogram.png**.

The histogram uses full-period distributions, common axes and 0.1-wide bins, with a 0-2.5 displayed D range. Shared calibration 50%/90% intervals are shaded; full-period airport-specific endpoints are dashed/dotted. All finite values, including those outside the displayed range, enter statistics. The 75% analysis is numerical; no extra coverage or width-ratio figures are generated.

## Interpretation limits

Incheon is the Encoder training-source airport, not an unseen-airport test. Training-period overlap must be assessed separately. Similar numerical ranges do not establish that identical D values imply identical operational complexity, and do not establish universal high/low thresholds. A wide interval can transfer despite differences in the core distributions. Evaluate coverage and width together and validate new choices on additional periods. The repository supplies method code, not a guarantee of identical values for different datasets or hardware.
