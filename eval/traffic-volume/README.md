# Traffic Volume Evaluation

This experiment measures how the raw log–log slope of a trajectory-embedding
point cloud changes as aircraft are added within an hourly scene.

## Protocol

- 720 hourly OpenSky scenes from 30 days, containing 19,306 tracks. No
  candidate screening, quality filtering or position deduplication is applied.
- Each scene is resampled in 20 nested random orders. For each order, the
  slope is computed for every `n = 5, ..., N_s`, where `N_s` is the scene's
  total aircraft count; the value at each `n` is the median over orders.
- The raw slope uses every radius with `0 < C(r) < 1` and at least two scales.
  It has no `C(r)` bound, radius-ratio gate or `R^2` threshold. It is a raw
  estimator, not the quality-gated `D` used elsewhere.
- Radii are fixed in `radius-grid.json`; scene keys, local dates, hours and
  counts are in `encoding-summary.json`; `embeddings/` contains one saved
  16-dimensional vector per aircraft.

## Files

| File | Role |
|---|---|
| `compute_d_vs_n.py` | Computes the raw slope for every scene and every `n`; writes `results/d-vs-n-no-gate.json` |
| `radius-grid.json` | Fixed 64-radius grid used by the slope calculation |
| `encoding-summary.json` | Scene key, local date, local hour and aircraft count |
| `embeddings/` | 720 saved `.npz` files, one per hourly scene |

`results/` is generated at runtime and is not part of this folder. No figures
or optional outputs are stored here.

## Running

Use the repository environment in `../../requirements.txt`:

```bash
python compute_d_vs_n.py
```

`compute_d_vs_n.py` writes `results/d-vs-n-no-gate.json`. The saved embeddings
are the starting point: raw tracks and the encoder checkpoint are not included,
so this folder reproduces the slope curves from the saved representations, not
the encoding step.
