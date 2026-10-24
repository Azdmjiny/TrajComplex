# Separate background population and injection eligibility

Approved scope: the original 12 September scenes, strict 10-second inputs,
barometric altitude, fixed 5,000 m spatial peak, existing quality, motion and
numerical limits. This change prepares trajectories only. It does not run an
Encoder, geometric dimension, dose-response curve or correlation.

## Fixed population

The new entrypoint is `code/screen_vectoring_candidates.py`. It has no Encoder
or complexity imports and refuses an existing output directory. The historical
`run_evaluation.py` entrypoint and Holding implementation/results are unchanged;
they do not automatically consume this new population. A future authorized
10-second correlation run must consume the prepared baselines and verified
injections together, not combine these injections with a historical raw baseline.

1. Read the same source tracks with the completed 10-second run's primary
   QC500 reader. All retained aircraft-hours remain fixed scene members.
2. Tracks with fewer than 63 strict 10-second samples cannot support the
   600-second maneuver and one joining sample on each side. They stay raw
   backgrounds. This applies an existing joining requirement at the first gate;
   it does not lengthen the maneuver or introduce a new minimum.
3. All genuine observations of each length-qualified fit candidate require the
   existing exact position/NIC identity and agreeing quality brackets within
   10 seconds on each side. Background-only tracks do not need those metadata.
   Missing, unknown, conflicting or distant quality evidence rejects injection
   eligibility without filling values or discarding the background.
4. Fit each fully evidenced candidate once. Failed fitting keeps its original
   basic-QC background. Successful fitting fixes its sampled baseline before
   direction or route screening; subsequent failure never reverts that version.
5. Certify direction over the maneuver and its joining support, propagating
   every full-track observation disk that influences those derivatives. Keep
   the existing 10-degree uncertainty limit and finite curvature requirements.
6. Generate both sides with the existing chord-normal degree-eight route
   family, SLSQP and continuous acceptance checks. Both must pass. Only their
   600-second portions can replace the corresponding frozen baseline samples.

The `PreparedPopulation.dose()` API copies the same baseline membership and
replaces only verified aircraft/side assignments. Duplicate or ineligible
assignments raise an error. Height, sampling times, point counts and samples
outside the maneuver are identical to each candidate's fitted baseline.
Raw backgrounds remain unchanged at every dose. Rejection counts are unique
aircraft-hours per reason; distinct reasons can overlap. Side outcomes remain
available separately.

## Full-track constrained reference

The reference minimizes integrated squared Cartesian jerk in a natural quintic
spline space. Only genuine position-update times are knots. Third and fourth
derivatives vanish at the full-track endpoints. No artificial grid knots,
extra smoothing radius, extrapolation or tunable regularization weight is used.
Fitted values at all original updates must lie in their existing NACp disks.
The full fitted curve is resampled horizontally on the same strict 10-second
grid; the original aligned barometric vertical coordinate is retained.

The implementation uses the natural cardinal B-spline basis. Optimizing its
knot values is equivalent to optimizing coefficients in the same spline space,
since the observation-value map is invertible. Exact six-node polynomial
quadrature builds the jerk objective. Coordinates are translated to a local
origin, time to the first update, and the objective is positively rescaled for
numerical conditioning; these transformations do not change its minimizer.

Clarabel 0.11.1 uses float64, max_iter=200, and tol_gap_abs/tol_gap_rel/tol_feas
all 1e-8. Only `Solved` solutions can be accepted. `AlmostSolved` is rejected.
Every accepted solution is independently checked against the original disk
radii, with no added physical allowance, clipping or projection. Existing
0.03 m / 0.01 m/s / 0.001 m/s² representation budgets remain unchanged.

### Lexicographic uniqueness without a redundant boundary solve

The primary objective's nullspace consists of quadratic curves. First solve
the normalized residual minimization within that nullspace and the same disks.
If feasible, this is the minimum-jerk (zero jerk) lexicographic solution. If
Clarabel returns `PrimalInfeasible`, solve the full minimum-jerk problem.
An unresolved nullspace solve rejects; no tolerance is relaxed.

A positive-jerk minimum is unique in this problem. If two different minima
existed, their difference would be a nonzero vector quadratic. Their midpoint
would be strictly inside every observation disk where their values differ,
by strict convexity of the disks. A nonzero vector quadratic vanishes at at
most two distinct times. Thus a midpoint minimum could have active disks only
at those two times. KKT stationarity on constant/linear/quadratic variations
forces both active multiplier vectors to be zero (the corresponding Vandermonde
columns are independent), which would force zero jerk, a contradiction.
Slater's condition holds because the raw observation values are strictly
inside their own positive-radius disks in this cardinal spline space.

Consequently no second boundary-only solve is needed after a positive-jerk
minimum. The first implementation attempted that redundant solve and suffered
reduced-accuracy termination and tiny disk violations. Its diagnostic output
is preserved locally but superseded. The corrected formulation keeps the same
objective, constraints, solver accuracy and iteration budget. It does not search
alternative physical thresholds or experimental conditions.

## Direction uncertainty and geometry

Let W be the natural-spline observation-value map, y the raw observations,
z the fitted knot values, and epsilon the NACp radii. The derivative envelope
centered on the fit includes both `sum |W'| epsilon` and `|W'(z-y)|`; the latter
accounts for shifting away from the raw-centered reference. Acceleration uses
the corresponding second-derivative expression. Bernstein bounds enclose the
continuous intervals. All observation columns participate, including those
outside the maneuver. The fitted residual is not used as a replacement for
measurement uncertainty. No independent-error assumption is introduced.

The generator retains fixed chord-normal displacement instead of rotating each
point's local normal. Reliable positive chord-forward motion prevents the old
inward-radius cancellation mechanism. Independent continuous peak, projection,
speed and acceleration checks and sampled joining/turn checks still determine
acceptance. A solver success flag alone is insufficient.

NACp disks and spline derivative envelopes are conditional engineering models,
not simultaneous confidence regions or aircraft-specific flight certificates.
The raw background population does not receive a claim of complete precision
evidence merely because it passes basic QC. The final experiment, if later
authorized, will concern a fixed mixed-preprocessing population whose candidate
zero-dose and injected versions share exactly the same preprocessing.

## Reproduction

Install the existing NumPy/SciPy dependencies and `clarabel==0.11.1`, then run:

```powershell
python evaluation/code/screen_vectoring_candidates.py --data-zip PATH_TO_SCENE_ZIP --quality PATH_TO_RECEPTION_POINT_EVIDENCE_JSONL_GZ --output NEW_LOCAL_OUTPUT_DIRECTORY
```

The quality input is the retained receiver-endpoint audit, not interpolated
metadata. Output includes input/code hashes, versions, all per-aircraft gates,
side diagnostics, and per-scene NPZ files with the frozen baseline and accepted
left/right trajectories. Source observations, checkpoints and NPZ arrays remain
local. The small screening report and summary are separate from old evaluation
results.

References: [Clarabel settings](https://clarabel.org/stable/api_settings/),
[Clarabel problem format](https://clarabel.org/stable/python/getting_started_py/),
[existing quality policy](vectoring-threshold-decisions.md), and
[existing continuous generator](vectoring-continuous-generator.md).
