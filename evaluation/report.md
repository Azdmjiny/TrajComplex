# Evaluation — 15 km segmented Vectoring, R²≥0.94, no STAR

Updated: 2026-10-25. This is the active evaluation report. The previous
5 km / R²≥0.98 / smooth-generator report is archived as
[report-5km-2026-10-24](archive/report-5km-2026-10-24.md).

**Scope:** four scene-hours, 157 background tracks, 19 injectable candidates.
The injection is a schematic, piecewise-straight vectoring stimulus at a fixed
15 km peak over 600 s. The Encoder is the original 9-feature, fixed-epoch-90
10-second checkpoint. No STAR/reference-relative features are used.

## Active code

| File | Role |
|---|---|
| [code/vectoring_path.py](code/vectoring_path.py) | `PEAK=15000`; `generate_segmented()` builds the trapezoid offset; `generate()` remains the smooth control |
| [code/vectoring_population.py](code/vectoring_population.py) | `SEGMENTED=True`; 10-second population uses the segmented generator and skips the deformed-kinematics rejection |
| [code/run_vectoring_eval.py](code/run_vectoring_eval.py) | `MAX_OFFSET=15000`; legacy five-second helpers remain for regression use |
| [code/run_evaluation.py](code/run_evaluation.py) | explicit workflow entrypoint; no implicit run |
| [../complexity/calculator.py](../complexity/calculator.py) | `min_r_squared=0.94` |

The STAR work is set aside: `Encoder/trajectory_encoder/star.py` and the
15-feature checkpoint remain in the repository but are **not** used by this
evaluation. Do not mix the STAR pilot numbers with this report; see
[STAR_INACTIVE.md](STAR_INACTIVE.md).

## Injection shape

The lateral offset is a trapezoid in the chord-normal direction:

- 0–150 s: straight diagonal out;
- 150–450 s: straight plateau at 15 km;
- 450–600 s: straight diagonal back;
- each of the three corners is rounded by a 30 s moving average so the sampled
  track has no numerical spike, while the long legs stay visibly straight.

![Smooth 15 km vs segmented 15 km](runs/segmented-15km/figures/vectoring-shape-smooth-vs-segmented.png)

The segmented arm is a **schematic stimulus**, not a C2-certified path. It does
not claim the smooth generator’s 2 m s⁻² longitudinal / 35° bank certificate.
The smooth 15 km arm remains the physically screened control.

## Results

Same 19 candidates, same 600 s window, same 15 km peak, same 9-feature Encoder,
R²≥0.94:

| Injection | Estimable curves | Positive | Median rho | Scene-level median | Positive scenes |
|---|---:|---:|---:|---:|---:|
| Smooth 15 km (control) | 15/20 | 9/15 | 0.600 | −0.086 | 1/3 |
| **Segmented 15 km** | **15/20** | **13/15** | **0.829** | **0.714** | **3/3** |

Per-scene median rho:

| Scene | Smooth 15 km | Segmented 15 km |
|---|---:|---:|
| 2026-09-15 15:00 | 0.929 | 0.964 |
| 2026-09-19 15:00 | −0.486 | 0.714 |
| 2026-09-27 13:00 | −0.086 | 0.600 |

`2026-09-14 14:00` has only three injectable candidates (four doses), below the
five-valid-dose requirement; it is not estimable under either shape.

Two negative curves are retained, not removed:

- `2026-09-19` order 4: −0.943;
- `2026-09-27` order 3: −0.086.

![Smooth vs segmented D association](runs/segmented-15km/figures/smooth-vs-segmented.png)

Interpretation: a smooth S-curve spends little time at large offset and is easy
for sum pooling to average out. The segmented track holds a 15 km offset for
300 s and has visible corners, which changes the local direction/curvature and
the pooled representation much more. The result is consistent with the visual
intuition that segmented vectoring is easier to see than a smooth curve.

## Historical arms (not the active result)

- **5 km smooth, R²≥0.98:** [archived report](archive/report-5km-2026-10-24.md).
  95/125 dose records failed only because R² was 0.948–0.950; three of four
  scenes had no accepted D.
- **5 km smooth at R²≥0.94:** 20/20 curves, 12/20 positive, median 0.382.
  Lowering the gate restores estimability but does not create a positive
  association.
- **15 km smooth at R²≥0.94:** [smooth-control summary](runs/segmented-15km/results/smooth-control/summary.json),
  15/20 curves, 9/15 positive, median 0.600; this is the active control.
- **STAR-relative Encoder / official STAR pilot:** inactive. The STAR baseline
  reference gave 15/20 curves, 14/15 positive, median 0.943, but that is not an
  independent reference; the official STAR pilot covered only 41% of arrivals
  within 2 km and degraded when forced (7/10 positive, median 0.457). See
  `deliverables/changi-official-star-2026-10-24/report.md` if the STAR line is
  resumed.

## Holding (unchanged)

The equal-duration terminal control remains as previously reported; this
update does not rerun or reinterpret it. At the same archived cutoffs and
jointly valid doses, median Spearman rho is 0.661 for Holding and 0.598 for
straight flight; six of seven comparable scene summaries have positive
Holding-minus-Straight D differences. These remain conditional descriptive
results, not complete validation of operational complexity. Evidence:
[runs/holding-equal-duration](runs/holding-equal-duration/).

## Reproduce the active four-scene run

The frozen population, source scripts and full diagnostics are in
[runs/segmented-15km](runs/segmented-15km/).

```powershell
$env:PYTHONPATH = (Resolve-Path 'deliverables/evaluation-python-deps')

python deliverables/vectoring-15km-segmented-2026-10-25/generate_population.py

python deliverables/vectoring-15km-star-2026-10-24/run_eval.py `
  --label old-15km-segmented-r094 `
  --checkpoint deliverables/encoder-10s/encoder/encoder.pt `
  --reference none `
  --population deliverables/vectoring-15km-segmented-2026-10-25/population-15km-segmented `
  --min-r2 0.94

python deliverables/vectoring-15km-segmented-2026-10-25/compare.py
```

The explicit production entrypoint remains:

```powershell
$env:ATM_DATA_ZIP = '<local scene archive>'
$env:ATM_QUALITY_MATCHES = '<local point-matches.json>'
$env:ATM_ENCODER_CHECKPOINT = 'Encoder/encoder.pt'
python evaluation/code/run_evaluation.py --help
```

## Limitations

1. **Segmented injection is schematic.** The smooth control is the only arm
   with the original motion certificate. Do not describe the segmented track as
   a flyable procedure.
2. **15 km is a stress-test amplitude**, not a claim about routine vectoring.
3. **No STAR.** This report intentionally omits the STAR/reference-relative
   Encoder; the STAR experiment is archived separately.
4. **D is descriptive.** Five orders are within-scene repeats, not five
   independent scenes; no confirmatory p-values.
5. **Scene 14 is candidate-limited**, not gate-limited; three candidates cannot
   produce five valid doses.

## File map

- Run package: [runs/segmented-15km](runs/segmented-15km/)
- Population: [runs/segmented-15km/population](runs/segmented-15km/population/)
- Segmented diagnostics: [runs/segmented-15km/results/segmented](runs/segmented-15km/results/segmented/)
- Smooth control: [runs/segmented-15km/results/smooth-control](runs/segmented-15km/results/smooth-control/)
- Shape generator: [code/vectoring_path.py](code/vectoring_path.py)
- Active population switch: [code/vectoring_population.py](code/vectoring_population.py)
