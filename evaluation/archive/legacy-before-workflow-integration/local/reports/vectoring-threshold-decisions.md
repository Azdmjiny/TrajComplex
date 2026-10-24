# Approved vectoring policy — 2026-10-22

**Historical run policy.** The saved results used the clauses below. Future
runs use the [continuous generator specification](vectoring-continuous-generator.md),
which replaces the cosine/local-normal construction and five-point derivative
fit. Quality metadata and physical screening limits remain unchanged. No
evaluation with the new generator has been run.

The user approved the following conditional engineering policy and a rerun of
the existing evaluation. No new control, dose sweep, scene replacement, offset
amplitude adjustment, or Monte Carlo experiment is included.

- Keep the existing 10-minute cosine displacement and fixed 5,000 m peak.
- Reject missing metadata, nonadvancing update times, repeated horizontal
  coordinates, source position ages above 15 s, and source/update gaps above 20 s.
- Require exact aircraft/update-time/coordinate correspondence to the received
  position message (including verified receiver timestamps where necessary).
- Require positive NIC/HCR, positive agreeing airborne version/NACp/SIL on both
  sides of each source update, no conflicting exact-time status, and each status
  endpoint within 10 s. Never fill unknown or distant quality values.
- The 10 s association ceiling is a declared engineering choice informed by the
  change-reporting deadline, not a guaranteed metadata lifetime or reception
  completeness. Equal endpoints cannot exclude unobserved changes.
- Use NACp category boundaries as conditional engineering perturbation radii.
  NACp 8/9/10/11 corresponds to 92.6/30/10/3 m. These are not deterministic
  accuracy guarantees or simultaneous 95% trajectory confidence regions.
- Estimate derivatives with a local quadratic fitted to five original source
  observations using their position-update times. Shift the five-point window
  within checked support at boundaries; do not extrapolate or invent samples.
  Source positions are never replaced by fitted positions.
- Propagate the position disks through the linear derivative weights using
  triangle inequalities, without assuming independent errors. For velocity v,
  acceleration a and disk-induced derivative radii ev/ea, bound the curvature
  numerator by v×a +/- (|v|ea + |a|ev + ev*ea) and the positive denominator by
  (|v| +/- ev)^3. Evaluate all endpoint ratios for an enclosing interval.
- Reject if |v|<=ev or arcsin(ev/|v|)>10 degrees. Reject if residuals exceed
  sum_j |(I-H)_ij| epsilon_j (plus 1e-6 m for numerical roundoff). This is a
  necessary consistency check for the local quadratic model, not a proof the
  true path is quadratic. Curvature bounds remain conditional on that model;
  unresolved between-sample motion and model bias are not certified.
- Require |d| max(|kappa_lower|,|kappa_upper|)<1 for both offset directions.
  At the 5 km peak the magnitude boundary is 0.0002 m^-1. This is a conservative
  geometric gate for variable offsets, not a physical flight envelope.
- Preserve at least half the original segment speed; require horizontal speed
  <=500 m/s. Screen absolute longitudinal acceleration <=2 m/s² separately
  from lateral acceleration <=g*tan(35 degrees) and the associated turn rate.
  These are ground-track proxies. Undefined directions reject.

## Inputs and reproducibility

Set `ATM_QUALITY_MATCHES` to the local `point-matches.json` audit input alongside
`ATM_DATA_ZIP` and `ATM_ENCODER_CHECKPOINT`. The run hashes the metadata input and
checks every used source row against the matched snapshot. The original model
checkpoint hash is enforced. Metadata values are never estimated from geometry.

All candidates remain in baseline point clouds unless rejected by the original
raw-track QC. Vectoring-ineligible aircraft receive no intervention. Counts of
rejection reasons are deduplicated by aircraft-hour, with possible overlap
between different reasons. Gates are sequential; absence of a later failure
does not imply a later check passed.

## Sources

- [OpenSky message schema](https://openskynetwork.github.io/opensky-api/trino.html).
- [FAA AC 20-165B](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_20-165B.pdf), section 3.3.3.6 and Table A-1: accuracy categories, not absolute per-point bounds.
- [Official CFR, 91.227(c)(2)](https://www.govinfo.gov/content/pkg/CFR-2025-title14-vol2/pdf/CFR-2025-title14-vol2-part91-subpartC.pdf): NACp-change reporting deadline, not a metadata validity guarantee.
- [JCGM 100:2008](https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf), section 5.2: input dependence matters.
- [Farouki and Neff (1990)](https://research.ibm.com/publications/analytic-properties-of-plane-offset-curves): constant-offset singularity boundary.
- [BADA 3.5, sections 5.2–5.3](https://www.eurocontrol.int/sites/default/files/library/017_BADA_3_5_User_Manual.pdf): acceleration and nominal bank guidance; ground-speed substitution is an explicit approximation.
