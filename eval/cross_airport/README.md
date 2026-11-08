# Cross-Airport Arrival Evaluation

This evaluation describes the hourly $D$ distributions at Singapore Changi
(WSSS), Tokyo Haneda (RJTT), Kuala Lumpur (WMKK), and Incheon (RKSI) during
September 2026. Each airport contributes 720 local hourly scenes and uses its
own frozen epoch-60 encoder. The distributions provide airport-specific
references for interpreting $D$.

## Setup

- **Arrival scenes.** Use OpenSky arrivals within 100 km of the airport. Match
  observations uniquely to flight records, resample to a 10-second grid and
  keep the longest eligible fragment with at least 25 points per flight-hour.
  Repeated position updates are interpolated between supported positions
  in ENU, with unsupported tails trimmed. The preparation uses a 15-second
  source age limit, a 20-second update and snapshot gap limit, and speed
  limits of 500 m/s horizontally and 100 m/s vertically. Coordinates are
  airport-centered ENU metres with barometric altitude as the vertical proxy.
- **Representation.** Rebase the prepared positions to the checkpoint's ENU
  origin when available. Standardize features with the checkpoint's training
  statistics and sum-pool token vectors to one 16-dimensional embedding per
  flight-hour.
- **Hourly $D$.** Count exact Euclidean pairs at 64 geometric radii between
  the minimum positive and maximum pairwise distances. Fit the log–log slope
  over all scales with $0<C(r)<1$. Retain the slope whenever the fit is
  mathematically defined and leave undefined values missing.

## Code

`run_complexity.py` computes hourly $D$ and the airport-specific median and
central 50% and 90% intervals. From the repository root, with the root
requirements installed:

```bash
python -m eval.cross_airport.run_complexity --prepared data/prepared --checkpoints data/airport-encoders --output eval/results/cross_airport
```

Each airport directory under `--prepared` contains `prepared_hours.csv`
with `airport,hour_utc,hour_local,prepared_path`, `cleaning_rules.json`
with the ENU `origin` (`lat`, `lon`, `elevation_m`), and an `hours/`
directory. The hourly NPZ files contain `enu_m`, `offsets`, `time` (UTC Unix
seconds), and `flight_ids`. Each manifest path's basename identifies its
file in `hours/`.

The checkpoint directory contains the original Changi `epoch_60.pt` and
`RJTT_encoder_60.pt`, `WMKK_encoder_60.pt`, and `RKSI_encoder_60.pt`. The
last three can be trained with `train_encoder.py` using the corresponding
cleaned training archive (`<ICAO>_CLEANED.jsonl.gz`, `<ICAO>_INDEX.csv`, and
`manifest.json`). The training input is a 1 Hz trajectory archive in ENU
coordinates scaled by 120,000 m. Training preserves the original splits,
selects 22,386 training, 2,821 validation, and 2,730 test trajectories
proportionally by month within each split, and saves the fixed epoch-60
checkpoint. Training requires a BF16-capable CUDA GPU.

```bash
python -m eval.cross_airport.train_encoder RJTT --source data/rjtt-training --output artifacts/rjtt-encoder
```

Prepared scenes and checkpoints are external inputs. The evaluation writes
`hourly_D.csv` and `airport_summary.csv` to the chosen output directory.
