# Continuous Vectoring generator implementation

Initial implementation: 2026-10-22. Numerical repair: 2026-10-23.
**The saved evaluation used the initial numerical implementation; no evaluation
or Encoder inference has been rerun with the numerical repair.** Results,
figures and `report.md` are preserved. Regression tests use deterministic
artificial inputs; they are software checks, not additional evaluation experiments.

## Numerical repair status

The numerical implementation is identified by
`direct-offset-derivatives/analytic-constraint-jacobians-v2` in future manifests.
The reference fit, three-control route family, 5 km spatial-distance target,
600-second duration, sample grid, physical thresholds, numerical budgets,
SLSQP stopping tolerance and work caps are unchanged.

Solver callbacks now evaluate the reference spline derivatives and the global
offset polynomial derivatives separately, before adding them. The offset jerk
basis is differentiated directly; it is no longer obtained by subtracting
third derivatives of nearly equal full-position curves on short intervals.
Motion constraints receive analytic Jacobians. The sampled peak-distance
constraint recomputes its nearest segment and maximizing sample each time,
and supplies that active branch's derivative. Exact ties select the first
branch deterministically; max/min switches remain nonsmooth and can still
cause a local solve to fail. Independent continuous acceptance checks remain
mandatory and unchanged. Solver failure still means rejection, not proof of
global infeasibility.

Thirty-seven related software regression checks passed. Arithmetic was also
checked at the 32 saved failed parameter vectors without optimizing them:
analytic motion Jacobians agreed with forward differences of the stable
evaluation to a maximum absolute normalized discrepancy of 1.58e-7. This does
not provide new eligibility counts or correlation results. A different
reference fit, baseline protocol, sampling cadence or training run remains
outside this repair and requires agreement before implementation.

## Scope and fixed requirements

The previous construction moved every point along its own local normal. On an
inward curve, a 5 km offset can cancel the original turning radius, slow the
synthetic path almost to zero, and create a cusp. Rejecting those paths prevented
contamination but did not provide a replacement construction.

`code/vectoring_path.py` now constructs a continuous reference and searches a
restricted family of smooth detours. It never divides by a zero tangent, copies
a neighboring heading, imputes quality metadata, shortens the target distance,
or lengthens the maneuver to obtain a pass.

| Requirement | Implementation |
| --- | --- |
| Duration / output | 600 seconds / 121 positions at 5-second intervals |
| Offset | Maximum **spatial distance to the continuous reference route** is 5,000 m, within the approved numerical budget |
| Joining | Position, horizontal velocity/heading and acceleration match the continuous reference at both maneuver endpoints |
| Unchanged data | Original baseline samples, altitude, times and samples outside the maneuver |
| Quality | Existing exact-message matching, agreeing status brackets within 10 s, positive NIC, NACp radii, update age <=15 s and update gaps <=20 s |
| Motion | Horizontal speed <=500 m/s; speed >=50% of reference speed; longitudinal acceleration <=2 m/s²; lateral acceleration <=g tan(35°); existing sampled turn-rate proxy |
| Failure | Reject the aircraft-hour if either side fails; never relax the checks |

The scalar displacement along the chord normal can exceed 5 km when that
direction is oblique to the local route. This does **not** change the approved
spatial-distance target. Distance to the same-time original point is recorded
by neither the target nor a substitute target. Paths with ambiguous nearest
reference points, backward progress, or unresolved geometry are rejected.

## 1. Continuous reference and observation provenance

Use the maneuver's actual source updates, including the interpolation support
for one existing sample before and after the maneuver. A track without those
joining samples is rejected. Fit a quintic minimum-jerk **interpolant** through
the real updates and the existing baseline grid positions. Grid positions retain
their exact linear weights on real updates; they are not independent new
observations and do not receive invented accuracy metadata.

This is a deliberately restricted special case of the approved rule that each
original observation's residual must not exceed its NACp radius, with no extra
fitting allowance. It does not denoise the original data or search the whole
space of fits within the disks. Derivatives can therefore remain unacceptable
even when another smoother, disk-consistent fit might exist. No such alternative
fit is silently tried.

For fixed interpolation constraints, minimizing the integral of squared third
derivatives gives a quintic spline. Its third and fourth derivatives vanish at
the outer support endpoints (the natural variational boundary conditions).
These are not additional flight limits or forced zero acceleration at the
maneuver endpoints. All time calculations use seconds relative to the maneuver
start, avoiding large Unix timestamps in polynomial algebra.

Propagate the NACp disks through the full linear observation-to-spline map.
Absolute derivative weights give conditional velocity/acceleration uncertainty
bounds without an independence assumption. Bernstein coefficient envelopes
enclose each continuous interval. The direction error must remain <=10° and
the lower forward velocity along the start-to-end chord must remain positive.
Finite enclosing curvature intervals are retained in diagnostics.

This replaces the active five-observation quadratic fit. The old `local_frame`
helper and its regression tests remain as historical implementation checks;
the new eligibility path does not call it. NACp category radii are still
conditional engineering disks, not deterministic measurement guarantees.
Neither interpolation nor a small residual proves the real aircraft followed
the fitted curve between observations. The construction has no general
model-bias certificate.

## 2. Restricted path search, with no local-normal squeezing

Let `r(t)` be the reference, `n` one fixed unit normal to its endpoint chord,
and `q(t) = r(t) + b(t) n`. For each side, `b(t)` is a nonnegative degree-eight
Bernstein polynomial. Its first and last three controls are zero, giving
zero displacement, displacement rate and displacement acceleration at both
ends. Three controls are free. Degree eight is an explicit representation
choice providing three shape controls after the six joining constraints;
it is not a physical threshold or a claim that all feasible detours have this
form. A single symmetric starting shape is scaled toward the spatial target.

The normal does not rotate at every sample. In particular,
`q'(t) · chord_axis = r'(t) · chord_axis > 0`, so this construction cannot
produce the original cancellation of velocity caused by inward local-normal
offsets. Routes that turn back relative to their chord are outside this
restricted family and reject.

Within the family, SLSQP searches for a path minimizing the integral of squared
Cartesian jerk, subject to the distance and motion constraints. There is no
weighted compromise that trades away the 5 km target or motion limits.
Six-node Gauss-Legendre quadrature integrates the squared polynomial jerk
exactly in exact arithmetic. Solver success is only a proposal: independent
checks must accept it. This local, nonlinear search does not prove a global
minimum or prove that every possible flight route is infeasible when it fails.

## 3. Independent continuous verification

- Build a reference polyline with a Bernstein convex-hull distance bound.
- Bound the maximum distance of the entire candidate curve to the continuous
  reference, including times between the 5-second samples. Subdivide until the
  lower/upper bounds fit the fixed-distance numerical budget, or reject.
- Enclose all potentially nearest reference intervals. Require a connected
  search interval, positive second derivative of squared distance, forward
  projection progress, the requested side, and an interior projection. Within
  the position budget of the reference, numerical side/endpoint ambiguity is
  allowed at the joins. Same-parameter polynomial products retain coordinate
  dependence rather than spuriously rejecting gentle curves through loose
  independent-coordinate boxes.
- Enclose speed and longitudinal/lateral acceleration over every interval.
  Subdivide inconclusive bounds; reject an observed violation or an unresolved
  check. Continuous lateral acceleration bounds also bound instantaneous turn
  rate through `turn_rate = lateral_acceleration / speed`.
- Compare generated speed with the reference speed and enforce the agreed
  absolute motion limits on the generated detour. Retain sampled
  baseline/generated motion and joining-neighbor checks as well. An original
  baseline that exceeds a motion limit is not rejected solely for that reason.
- Match endpoint position, velocity, heading and acceleration to the continuous
  reference. This is a C2 join to that reference model, not proof of continuity
  with the unobserved true flight. The output still consists of 5-second samples.

| Approved numerical budget | Value | Use |
| --- | --- | --- |
| Position | 0.03 m | Reference/grid agreement, endpoint joining, continuous 5 km target |
| Speed | 0.01 m/s | Independent spline/Bernstein evaluation and endpoint derivative agreement |
| Acceleration | 0.001 m/s² | Independent derivative evaluation and endpoint joining |
| Heading | 0.01° | Endpoint heading agreement |

These are computation budgets, not claims that ADS-B positions have centimeter
accuracy. The reference polyline uses one eighth of the position budget; peak
bound refinement uses half. Physical limits are not increased by these budgets.
Calculations use double precision and ordinary floating-point Bernstein bounds,
not outward-rounded formal interval arithmetic; they provide conservative
geometric checks within the declared numerical budgets, not a formal proof
against arbitrary floating-point error.

SLSQP uses its documented 100-iteration default. Each adaptive verifier has a
100,000-node resource cap. Exhausting either budget rejects with an explicit
reason. These are computational caps, not newly inferred flight thresholds.
The solver's absolute stopping tolerance is the smallest normalized approved
numerical budget. It is not squared. This does not weaken acceptance: independent
continuous checks still enforce the approved physical and numerical limits.
Method, controls, solver status, sampled solver-constraint margins, continuous bounds, conditional
reference metadata, runtime versions and source hashes are recorded for future
runs. Verified paths are cached only for the identical source trajectory; both
sides must pass before the candidate is eligible.

## Verification and limits

The regression suite covers fixed 5 km offsets on straight and gently curved
references, C2 joining, unchanged altitude/outside samples, epoch invariance,
uncertain direction, the 5 km-radius collapse example, between-sample
acceleration violations, false solver success, solver failure, resource-cap
rejection, exact quality matching, prepared-path reuse and duplicate rejection
counts. The existing Holding, time-axis, uncertainty and correlation-selection
tests remain in the suite.

This implementation addresses the defective construction without promising
additional real-data candidates. Missing quality evidence still rejects;
noisy or unsuitable reference fits still reject; physically implausible or
unverified detours still reject. Ground-track acceleration proxies are not an
aircraft-specific flight envelope. Actual eligibility counts and correlations
remain unknown until an authorized evaluation rerun.

## Implementation references

- [SciPy `make_interp_spline`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.make_interp_spline.html): explicit quintic interpolation and endpoint derivative conditions. The generic `natural` alias means a different boundary condition; this implementation supplies its third/fourth derivative conditions explicitly.
- [SciPy SLSQP](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html): solver success, tolerance and iteration limit are numerical properties, not independent physical verification.
- [Earlier approved quality and motion policy](vectoring-threshold-decisions.md): sources for NACp, timing and ground-motion thresholds. The historical local-normal generator/derivative clauses are superseded only for future runs by this specification.
