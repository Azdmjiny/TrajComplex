# Historical official STAR pilot (2026-10-24)

Status: inactive. English summary of the original local `changi-official-star-2026-10-24/report.md`;
all numbers are saved findings, not a new experiment.

The pilot encoded six WSSS RWY20 RNAV STARs from the CAAS AIM-SG AIP:
ARAMA 1B, ASUNA 1B, KARTO 1B, OBDOS 1B, REPOV 1B and ELALO 1B.
Waypoint sequences were represented by polylines, not complete fly-by geometry.

Among 39 arrival tracks, 16 (41%) were within 2 km of their nearest STAR and
20 (51%) within 5 km. The 21 injection candidates were 8.8–29.2 km from the
nearest STAR, median 17.2 km; only one was within 10 km.

| Reference with the same 15-feature Encoder, 15 km target and R² >= 0.94 | Estimable curves | Positive | Median rho | Scene median |
|---|---:|---:|---:|---:|
| Baseline self-reference | 15/20 | 14/15 | 0.943 | 0.929 |
| Official within 10 km, otherwise fallback | 15/20 | 14/15 | 0.929 | 0.929 |
| Forced official reference | 10/20 | 7/10 | 0.457 | -0.117 |

The fallback arm largely reused baseline references and was not an adequate
test of official route coverage. With forced assignment, September 19 became
unestimable and September 27 changed from median +0.943 to -0.829.

The saved report attributes limitations to polyline turn geometry, incomplete
runway/transition coverage, and unknown actual flight-plan/clearance assignment.
These results do not support replacing current references with the nearest
official STAR. They do not establish that the concept of STAR-relative encoding
is inherently invalid.

`source/official_routes.py` contains the six encoded routes; `coverage.py`
checks proximity; `compare.py` compares saved D results. Original plots are in
[figures/](figures). Execution paths are preserved as historical provenance;
private coverage/results and checkpoints remain local.
