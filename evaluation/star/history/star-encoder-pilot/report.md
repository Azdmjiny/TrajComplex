# Historical STAR-relative Encoder pilot (2026-10-24)

Status: inactive. English summary of the original local `vectoring-15km-star-2026-10-24/report.md`;
no new analysis or experiment. This used a separate 15-feature STAR-relative
Encoder and must not be mixed with the current 9-feature Encoder.

| Saved arm, R² >= 0.94 | Estimable curves | Positive | Median rho | Median of scene summaries |
|---|---:|---:|---:|---:|
| 5 km, 9-feature | 20/20 | 12/20 | 0.382 | 0.088 |
| 15 km, 9-feature | 15/20 | 9/15 | 0.600 | -0.086 |
| 15 km, 15-feature STAR-relative | 15/20 | 14/15 | 0.943 | 0.929 |

The September 14 scene had three eligible candidates and four doses, below
the five-valid-dose correlation rule. STAR-relative channels encode motion
relative to a reference, so these results do not establish successful assignment
to official airport STAR procedures. That was tested separately in the
[official-route pilot](../official-star-pilot/report.md).

`source/generate_population.py` constructs 15 km populations after checking
the 5 km reference; `run_eval.py` runs the original/STAR/reference-control arms;
`package_checkpoint.py` packages the fixed checkpoint; `compare.py` reads saved
results. These exact scripts retain historical local paths and are provenance,
not maintained portable entrypoints. Existing plots are in [figures/](figures).

Local saved results include the 0.94 arms, an earlier 0.95 gate, one-epoch smoke
runs and shuffled-reference controls. Those arrays and weights remain local;
no additional result files were copied into evaluation.
