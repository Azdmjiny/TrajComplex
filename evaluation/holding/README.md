# Holding

| Location | Role |
|---|---|
| [main/](main/README.md) | Current corrected 10-second midpoint, R² >= 0.94; complete-range appendix included |
| [controls/](controls/README.md) | Separate endpoint +240 s Holding versus +240 s straight flight |
| [history/](history/README.md) | Previous R² >= 0.98 presentation and version comparison |
| [code/](code/README.md) | Holding generation, control postprocessing and figure builders |

The mixed [strict-10s source](../histry/strict-10s-reference/report.md) stays shared:
it contains both maneuver families and supplies the saved midpoint fits and
archived cutoffs. Main and control insertion locations/gates differ; do not
merge their coefficients.
