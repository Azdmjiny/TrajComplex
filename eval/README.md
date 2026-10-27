# Independent Holding evaluation

A Holding runner; it does not import the legacy evaluation runner. It calls the repository's frozen Encoder and correlation-dimension estimator as model components.

Run from the repository root:

    .venv/bin/python eval/run_holding.py --output eval/results/holding-YYYY-MM-DD

The default uses eleven fixed Holding scenes from the 2026-10-27 Changi package, excluding 2026-09-12T15Z at the user's request; it runs ten replacement-sampled sequences per scene, up to thirty events per sequence, using the frozen epoch-90 checkpoint. Each event inserts 240 seconds of racetrack at the original midpoint and trims 240 seconds from the transformed track end. D uses a minimum scene sample count of 15 and R-squared >= 0.90. The cross-scene figure shows distinct colored median dose curves with a scene legend, one background IQR band pooled across all valid sequence-level Delta-D estimates, and a thick common trend equal to the median of scene medians. The primary Spearman rho is calculated from that common trend. Outputs include event/dose data, audit, figures, policy, manifest and report.
