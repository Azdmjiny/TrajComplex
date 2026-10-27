# Shared historical runs

Subject-specific packages have moved to `holding/`, `vectoring/`, and `hourly/`.
Use the [directory guide](../../report/DIRECTORY_GUIDE.md) and [path map](../organization-map.json).

`strict-10s-reference/` stays here because its saved experiment contains both
Holding and Vectoring. It supplies the midpoint fits and cutoffs for the latest
Holding presentation and the earlier paired control.

`publication-manifest.json` and `publication-checks.json` are original historical
publication snapshots. Their paths/hashes refer to that version; the relocation
map resolves moved paths without altering their recorded history.
