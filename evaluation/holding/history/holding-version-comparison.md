# Holding: separate the pilot, corrected midpoint experiment and terminal control

This note compares existing records. The current midpoint presentation re-screens saved fits at R² ≥ 0.94; the 0.98 presentation is historical. No new trajectories, D estimates, cutoff search or model selection were performed. The endpoint control remains separately labelled and unchanged.

## Distinct experiments and acceptance versions

| Version | Input and model | September 20 04Z N | Injection | Reported association |
|---|---|---:|---|---|
| Original midpoint pilot | 10-second archive linearly resampled to 5 seconds; older d3abfc checkpoint; geometric altitude | 67 | Midpoint racetrack, before the geometry repair | Complete response was nonmonotonic; the supplied graphic shows a selected pre-peak range |
| Corrected strict-10s midpoint reference, historical R² ≥ 0.98 | Strict 10 seconds, barometric altitude and source QC; frozen bc1e epoch-90 checkpoint | 33 | Corrected midpoint racetrack | All-scene median order rho 0.220 full / 0.845 retained; 32/33 retained curves positive |
| Current midpoint presentation, R² ≥ 0.94 | Same strict-10s population, checkpoint and saved fits | 33 | Same corrected midpoint racetrack and archived ranges | Median order rho 0.218 full / 0.884 retained; 34/35 retained curves positive |
| Terminal equal-duration control | Same strict-10s checkpoint and baseline population | 33 | Append 240 seconds at endpoint, Holding versus straight | Matched-dose all-scene medians 0.196 full / 0.661 retained for Holding; retained straight 0.598 |

The original pilot report's 16-dimensional Encoder description refers to output embedding dimension. The current settings specify 9 input features AND 16 output embedding dimensions. Comparing 16 output dimensions against 9 input features as though embedding dimension changed is incorrect. The model/checkpoint and cadence did change.

## September 20 comparison

The corrected midpoint and terminal control share N=33 and baseline D=1.3599442143. The stored midpoint-derived cutoff is 17 aircraft and is reused for both terminal arms.

| Estimate over stored range | Midpoint Holding | Endpoint Holding | Endpoint straight |
|---|---:|---:|---:|
| Median order rho, each arm's accepted doses | 0.830 | 0.518 | 0.474 |
| Median order rho, jointly accepted endpoint arm doses | Not a matched midpoint statistic | 0.477 | 0.474 |

These rows use different valid-dose sets. They are not a new matched-dose causal comparison of insertion position. The midpoint-derived cutoff also favors examining the midpoint growth region by construction. The saved control verification confirms identical baselines, but does not establish why the post-injection representations differ.

## What explains the visual difference

1. The supplied pilot figure displays only its pre-peak portion, mostly doses 0–30. The complete pilot was not universally positive. Its six panels correspond to baseline-estimable pilot scenes, not all twelve planned scenes.
2. The earlier Holding figure used the endpoint equal-duration experiment. Moving the same maneuver to a different trajectory context is a different intervention. It also uses different valid-dose subsets. The unchanged strict-10s midpoint experiment still has a strong retained-range association, so the loss of visual strength cannot simply be blamed on 10-second training or N falling to 33.
3. Subtracting a common scene baseline only shifts the vertical axis: it does not change within-scene ranks or Spearman rho, and cannot turn a decreasing response into an increasing one. Three scenes had accepted baselines at 0.98; five have accepted baselines at 0.94. The other two pre-peak scenes remain in absolute D, without invented baselines.
4. The pilot used mean-of-available-orders curves; the earlier endpoint figure uses medians; the new midpoint response figure uses means. Those summaries can look different. Neither changes the stored per-order coefficients, and availability can change with dose.
5. The pilot geometry had a second-turn heading/closure defect documented in the local repair audit. Returning to that version for appearance alone would reintroduce known invalid geometry. The corrected strict-10s midpoint evidence is the appropriate version to examine for the original midpoint research question.
6. Background population, altitude definition, source quality rules and minimum supported duration changed between pilot and strict-10s inputs. Their individual contributions have not been isolated by these saved comparisons.

## Presentation decision

A midpoint synthetic-response question and a terminal equal-duration control question should be reported separately. If midpoint response is the intended primary question, the corrected strict-10s midpoint results are available as an exploratory response study, with the terminal control reported separately and explicitly identified as a different intervention. Choosing that framing requires a substantive research-question justification, not only its larger coefficient. It cannot establish that the midpoint response is independent of sequence length; the endpoint control does not directly control the midpoint intervention.

A main figure may show only the original historical range if its title, axes and caption say so and the full curves remain accessible in the appendix. Do not choose a new favorable cutoff or silently replace endpoint values with midpoint values. Historical peak-selected ranges remain outcome-derived, not validated physical limits or independent confirmation.

## Saved evidence

- [Strict-10s midpoint report](../../histry/strict-10s-reference/report.md) and [summary](../../histry/strict-10s-reference/results/summary.json).
- [Terminal equal-duration report](../controls/holding-equal-duration/report.md).
- [Shared historical cutoff report](../controls/holding-equal-duration-old-cutoff/report.md) and [order summaries](../controls/holding-equal-duration-old-cutoff/results/repeat-summary.json).
- [Appendix H: complete terminal control evidence](../controls/holding-paper-appendix.md).

The local original-pilot and geometry-repair records remain at `deliverables/evaluation-repair-2026-10-19/original/evaluation/reports/evaluation-pilot.md` and `deliverables/evaluation-repair-2026-10-19/comparison.html`. These provenance paths are local evidence, not downloadable repository files. Current Encoder contract: `deliverables/encoder-10s/encoder/settings.json`.

## Clarified time-window scope and current presentation

The [current midpoint response figures](../main/holding-midpoint-response.md) reuse the corrected 10-second midpoint fits with the revised 0.94 acceptance gate. The source aircraft come from natural-hour files, but insertion preserves the full original trajectory tail. These results were not clipped to the absolute hour boundary after adding 240 seconds. Producing a post-injection fixed-hour result would require different trajectories and new computation, which was not performed. The prior endpoint figure remains available as the separate equal-duration study.
