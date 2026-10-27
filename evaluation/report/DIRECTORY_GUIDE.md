# Evaluation directory guide

## Current layout

```text
evaluation/
  holding/       code / main / controls / history
  vectoring/     code / main / controls / history
  hourly/        code / main / controls / history
  star/          inactive pilots; code / main / controls / history
  code/          shared QC, time alignment, statistics and workflow tools
  histry/        mixed historical evidence and provenance
  report/
    report.md    combined current report
    figures/     existing cross-study comparison images
    DIRECTORY_GUIDE.md
    DATA_PACKAGE.md
  README.md
  report.md      compatibility link only
```

`histry` is the requested folder spelling. Subject-specific history remains with
its subject; only mixed/shared history is consolidated here.

## Subject folders

| Folder | Main | Controls | History |
|---|---|---|---|
| [Holding](../holding/README.md) | Corrected 10 s midpoint, R² >= 0.94 | Endpoint equal-duration Holding/straight and common-cutoff postprocessing | Previous 0.98 presentation and version comparison |
| [Vectoring](../vectoring/README.md) | Repaired 20 s quality matching, 26 candidates | Earlier 10/15/20 s sensitivity; paired smooth control stays beside its segmented arm | Earlier 19-candidate 15 km and 5 km studies |
| [Hourly](../hourly/README.md) | Deduplicated September 8/11 1h D/count/status | Original-input appendix and separate threshold review | N scaling and raw no-gate analysis |
| [STAR](../star/README.md) | None active | None active | STAR Encoder and official-route pilots |

Each subject's code README identifies maintained commands and historical scripts.
Reports and figures stay beside their experimental version; they are not copied
again merely because the combined report links to them.

## Shared material

| Location | Purpose |
|---|---|
| [code/](../code/README.md) | Shared time-axis/QC/statistics, dispatcher, cross-study reporting and tests |
| [histry/strict-10s-reference](../histry/strict-10s-reference/report.md) | Original saved Holding/Vectoring fits; still read by current Holding postprocessing and the paired control |
| [histry/legacy-before-workflow-integration](../histry/legacy-before-workflow-integration/README.md) | Exact mixed committed/local historical snapshots |
| [histry/combined-reports](../histry/combined-reports/README.md) | Superseded joint reports and indexes |
| [histry/publication-records](../histry/publication-records/README.md) | Earlier publication manifests/checks |
| [histry/legacy-audit-source](../histry/legacy-audit-source/) | Original checker for the old report layout |
| [histry/cross-study-figure-source](../histry/cross-study-figure-source/) | Frozen source for the earlier combined image |
| [Combined report](report.md) | Current findings and explicit limitations |
| [Report figures](figures/README.md) | Existing cross-study comparison images |

## Why the strict-10s package is retained

It is a laboratory notebook, about 2.7 MB, rather than duplicate output to discard.
The main QC500 Holding section has 12 scenes, five orders per scene and 1,980
saved dose records. Current R² >= 0.94 plotting reuses those original fit records;
the equal-duration common-cutoff analysis reuses their historical cutoff values.
Holding and Vectoring occupy separate sections in the same JSON container.
Their data and correlations are not pooled. The latest Vectoring main result
is a separate package.

## Path compatibility and preservation

The [path map](../histry/organization-map.json) composes both organization steps.
Maintained code resolves the mixed source through
`study_path('strict-10s-reference')`; an explicit external old-style run root is
still supported. Frozen JSON and source snapshots retain original execution paths.

The shared code folder has not moved. The old flat `runs/`, `archive/` and
`figures/` directories are retired. The old root `report.md` contains a short
redirect so manuscript/external links continue to work without editing paper/doc.
Git attributes preserve scientific evidence bytes at their new locations.

No experiment, scientific threshold or figure changed. Raw local data,
checkpoints, recent private result packages and the four subject folders were
not otherwise relocated. Existing negatives, failures and full ranges remain.

Structural checks (no experiment execution):

```bash
python evaluation/code/check_layout.py
python -m unittest discover -s evaluation/code -p "test_evaluation_layout.py"
```

[DATA_PACKAGE.md](DATA_PACKAGE.md) describes the original October 26 handoff;
packaging/deleting a later ZIP did not modify these source data.
