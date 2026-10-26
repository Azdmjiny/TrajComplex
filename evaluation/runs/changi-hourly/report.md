# Changi: a 24-hour real-traffic application case

**Position-deduplicated main result.** Both dates, all 24 clock hours, and all three schemes are retained. This presentation reads saved results only; no Encoder call, D estimate, new sampling or threshold change is made.

The complete display combines accepted D, aircraft counts before/after QC, and estimability. It demonstrates hourly application and explicit limits; it does not claim 24 valid estimates. NA is never zero or interpolated, and lines do not bridge failed hours.

## Coverage

| Date (UTC+08) | Valid D | Insufficient N | Poor fit | Valid subsets / attempts | Hours with 200/200 |
|---|---:|---:|---:|---:|---:|
| 2026-09-08 | 14/24 | 7 | 3 | 2496/3400 | 1 |
| 2026-09-11 | 15/24 | 8 | 1 | 2555/3200 | 3 |

## Why this is the main result

Only repeated horizontal observations with exactly the same position-update timestamp and latitude/longitude are collapsed. All altitude snapshots, age checks and gap checks remain. Backward timestamps, conflicting equal-time coordinates and unsupported intervals still reject the track. There is no new gap filling, extrapolation or relaxed gate; the existing bounded 10-second resampling is unchanged.

The saved validation recovered 263 aircraft-hours (136 on September 8, 127 on September 11). All 1,434 original accepted trajectory arrays and embeddings were verified bitwise unchanged. Of 849 former repeated-timestamp first rejections, 565 still fail the distinct-position gap rule and 21 fail the minimum grid length. Aircraft-hours are not unique aircraft over two days.

The frozen grid is reused exactly. Larger aircraft pools change both the point cloud and eligible regression scales. Identical seed/draw numbers do not imply matched aircraft subsets between versions. The change is justified by observation handling, not by choosing a more positive result. Fixed-N stability does not uniformly improve.

## Main figures

The area is within 100 km of Changi and includes overflights and traffic from other airports. Before-QC counts are distinct ICAO identifiers with basic airborne fields, not a complete count of Changi arrivals/departures.

![2026-09-11: accepted D, aircraft and status](figures/2026-09-11-24h-D-count-status.png)

![2026-09-08: accepted D, aircraft and status](figures/2026-09-08-24h-D-count-status.png)

## Frozen method

- Strict 10-second barometric input, one full-window sequence per aircraft, frozen epoch-90 9-feature Encoder, training normalization and sum pooling. Checkpoint SHA-256: `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`.
- N>=30, >=8 fitting scales, >=10 pairs, C(r) in [0.02,0.3], radius ratio>=2, R²>=0.94. These saved gates differ from the historical Holding control, which used R²>=0.98.
- Exactly the original 64-radius log grid, from 0.21153999267980197 to 377.183110301039. Originally constructed from within-window positive distances across the 24 September 11 populations, including low-N hours. It is not rebuilt after deduplication. Eligible regression scales can still differ across populations.
- N=30, B=200; uniform sampling without replacement within a draw. The saved package contains 6,600 draws across 33 eligible hours. Failed draws are never replaced.

## Unavailable estimates and screening

There are 15 insufficient-N and 4 poor-fit hours. NA means unavailable under these rules, not zero complexity. A poor linear fit does not establish that physical traffic has no geometric dimension.

| First screening outcome (aircraft-hours) | September 8 | September 11 |
|---|---:|---:|
| accepted | 859 | 838 |
| fewer_than_16_source_records | 130 | 119 |
| fewer_than_30_grid_points | 82 | 102 |
| position_update_gap_over_20_s | 337 | 342 |
| repeated_raw_horizontal_position | 1 | 0 |
| source_record_gap_over_20_s | 321 | 489 |

## Scheme 2: fixed-N supplement

Partial-success medians are conditional on accepted subsets, shown hollow without a range or joined median curve. A central 95% subsampling range is shown only when all 200 draws pass and more than one distinct subset is present. It is not a bootstrap confidence interval. The same aircraft subset on every draw is not evidence of robustness to aircraft composition.

- 2026-09-08 11:00: all 200 draws are the same subset (N=30).

![Fixed-N and weather supplement](figures/fixed-N-weather-1h.png)

## Scheme 3: independently selected weather comparison

September 11 is the thunderstorm day; September 8 is the clearer-weather comparator. WSSS TS/VCTS observations identify September 11 clock bins 13–17; shading is not an exact continuous storm boundary. Mixed signs are retained. No causal weather effect, wind-shear detection, or general positive association is established.

| Hour | Event minus control full D | Event minus control subset median | Valid control / event draws |
|---|---:|---:|---|
| 13:00 | NA | -0.088 | 5/200 ; 200/200 |
| 14:00 | -0.252 | -0.247 | 198/200 ; 192/200 |
| 15:00 | 0.319 | 0.284 | 180/200 ; 200/200 |
| 16:00 | 0.529 | 0.578 | 189/200 ; 195/200 |
| 17:00 | 0.518 | 0.489 | 176/200 ; 183/200 |

Weather sources: [WSSS archive provider](https://mesonet.agron.iastate.edu/request/download.phtml?network=SG__ASOS) and [Meteorological Service Singapore retrospective](https://www.weather.gov.sg/more-showers-expected-in-the-coming-fortnight/). Absence of a code does not prove absence of adverse weather.

![D versus accepted aircraft](figures/D-vs-N-1h.png)

## All 48 hourly records

| Date | Hour | Before QC | Accepted | D | Status | Valid / attempted draws | Conditional median |
|---|---:|---:|---:|---:|---|---:|---:|
| 2026-09-08 | 00 | 46 | 25 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-08 | 01 | 34 | 15 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-08 | 02 | 38 | 19 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-08 | 03 | 27 | 13 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-08 | 04 | 32 | 14 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-08 | 05 | 45 | 22 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-08 | 06 | 53 | 34 | 1.318 | ok | 199/200 | 1.266 |
| 2026-09-08 | 07 | 56 | 35 | NA | poor_linear_fit | 31/200 | 1.013 |
| 2026-09-08 | 08 | 61 | 37 | 1.015 | ok | 128/200 | 1.001 |
| 2026-09-08 | 09 | 77 | 37 | NA | poor_linear_fit | 31/200 | 1.093 |
| 2026-09-08 | 10 | 88 | 44 | 1.080 | ok | 155/200 | 1.106 |
| 2026-09-08 | 11 | 77 | 30 | 1.232 | ok | 200/200 | 1.232 |
| 2026-09-08 | 12 | 87 | 47 | 1.236 | ok | 198/200 | 1.231 |
| 2026-09-08 | 13 | 92 | 42 | NA | poor_linear_fit | 5/200 | 1.744 |
| 2026-09-08 | 14 | 109 | 47 | 1.424 | ok | 198/200 | 1.402 |
| 2026-09-08 | 15 | 95 | 46 | 1.215 | ok | 180/200 | 1.289 |
| 2026-09-08 | 16 | 113 | 56 | 1.067 | ok | 189/200 | 1.064 |
| 2026-09-08 | 17 | 93 | 44 | 1.119 | ok | 176/200 | 1.136 |
| 2026-09-08 | 18 | 97 | 41 | 1.161 | ok | 191/200 | 1.175 |
| 2026-09-08 | 19 | 90 | 53 | 1.276 | ok | 180/200 | 1.277 |
| 2026-09-08 | 20 | 102 | 56 | 1.151 | ok | 152/200 | 1.195 |
| 2026-09-08 | 21 | 94 | 45 | 1.128 | ok | 168/200 | 1.112 |
| 2026-09-08 | 22 | 68 | 35 | 0.830 | ok | 115/200 | 0.836 |
| 2026-09-08 | 23 | 56 | 22 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-11 | 00 | 45 | 22 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-11 | 01 | 38 | 20 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-11 | 02 | 39 | 12 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-11 | 03 | 29 | 18 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-11 | 04 | 33 | 16 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-11 | 05 | 40 | 22 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-11 | 06 | 53 | 24 | NA | insufficient_samples | 0/0 | NA |
| 2026-09-11 | 07 | 68 | 40 | 1.303 | ok | 144/200 | 1.532 |
| 2026-09-11 | 08 | 86 | 48 | 1.116 | ok | 191/200 | 1.106 |
| 2026-09-11 | 09 | 80 | 43 | 1.136 | ok | 171/200 | 1.183 |
| 2026-09-11 | 10 | 86 | 37 | NA | poor_linear_fit | 7/200 | 0.977 |
| 2026-09-11 | 11 | 86 | 42 | 1.061 | ok | 130/200 | 1.071 |
| 2026-09-11 | 12 | 92 | 38 | 1.850 | ok | 199/200 | 1.834 |
| 2026-09-11 | 13 | 101 | 47 | 1.678 | ok | 200/200 | 1.656 |
| 2026-09-11 | 14 | 112 | 38 | 1.172 | ok | 192/200 | 1.155 |
| 2026-09-11 | 15 | 112 | 36 | 1.534 | ok | 200/200 | 1.573 |
| 2026-09-11 | 16 | 105 | 38 | 1.596 | ok | 195/200 | 1.642 |
| 2026-09-11 | 17 | 112 | 36 | 1.637 | ok | 183/200 | 1.626 |
| 2026-09-11 | 18 | 114 | 46 | 1.112 | ok | 188/200 | 1.117 |
| 2026-09-11 | 19 | 107 | 49 | 1.333 | ok | 129/200 | 1.457 |
| 2026-09-11 | 20 | 102 | 45 | 1.164 | ok | 200/200 | 1.177 |
| 2026-09-11 | 21 | 97 | 50 | 0.943 | ok | 68/200 | 0.991 |
| 2026-09-11 | 22 | 88 | 44 | 1.003 | ok | 158/200 | 0.974 |
| 2026-09-11 | 23 | 65 | 27 | NA | insufficient_samples | 0/0 | NA |

## What the paper can claim

This is an auditable real-traffic application with explicit estimator availability. It does not prove a complete reliable day/night D curve, independence from traffic count, causal storm sensitivity or general operational-complexity validity. Fixed N controls count, not composition, duration or observation availability. The two days differ in weekday; subsets are dependent, and aircraft may recur across hours. September 11 sequences reach 357 samples versus 298 in the prepared training data; no new length gate was applied.

Rebuild with `python evaluation/code/report_changi_hourly.py --input LOCAL_SAVED_PACKAGE --preprocessing position-dedup --output NEW_DIRECTORY`. Full saved attempts, embeddings, draw assignments, QC evidence and manifests remain local. Only code, reviewed reports and figures are publication artifacts.

## Preserved original and version comparison

The [original report and figures](appendix-original/report.md) are the appendix comparator. The [full old-versus-new comparison](comparison-with-original.md) retains all 48 hours and the changes in fixed-N and weather results. The deduplicated version is the main result for all three schemes; favorable outputs are not mixed between versions.
