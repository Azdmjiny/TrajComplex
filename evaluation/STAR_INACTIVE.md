# STAR work is inactive

The STAR-relative Encoder (`Encoder/trajectory_encoder/star.py`, 15 input
features) and the official-STAR pilot are **not used** by the active
evaluation. The active Encoder is the original 9-feature fixed-epoch-90
checkpoint.

The STAR reports are archived outside this repository and are not part of this
publication. They are not entrypoints and must not be represented as current
evidence.

Do not mix the STAR numbers with `report.md`. If the STAR line is resumed,
restore it as a separate run with its own manifest and do not overwrite the
active 15 km segmented results.
