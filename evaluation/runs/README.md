# Published evaluation results

These folders separate distinct experiments and diagnostics; they are not alternate copies of one preferred outcome. Full dose ranges and rejected estimates are retained. The [combined report](../report.md) is the current interpretation.

| Folder | Role |
|---|---|
| [changi-hourly](changi-hourly/report.md) | **Application case:** deduplicated main result, original appendix; complete 24h D/count/status displays and fixed-N/weather supplements |
| [changi-thresholds](changi-thresholds/report.md) | Threshold review: 3h rolling primary display, 1h N>=20 exploratory, low-traffic floor and explicit remaining gaps |
| [changi-n-scaling](changi-n-scaling/report.md) | One-scene D-versus-aircraft-count pilot: 5 to 56 aircraft, 100 nested orders |
| [segmented-15km](segmented-15km/README.md) | **Active:** 15 km segmented Vectoring, R²≥0.94, no STAR; smooth 15 km control |
| [strict-10s-reference](strict-10s-reference/report.md) | Historical twelve-scene midpoint results and exact shared-cutoff source |
| [four-scene-vectoring-screen](four-scene-vectoring-screen/report.md) | Background/candidate screening: 21 accepted candidates out of 26 |
| [four-scene-vectoring-evaluation](four-scene-vectoring-evaluation/report.md) | Full-range evaluation of the four frozen scenes |
| [vectoring-existing-result-diagnosis](vectoring-existing-result-diagnosis/report.md) | Stored-fit residuals, pair-count boundaries and observed injection steps |
| [holding-equal-duration](holding-equal-duration/report.md) | Paired +240-second terminal Holding versus straight continuation |
| [holding-equal-duration-old-cutoff](holding-equal-duration-old-cutoff/report.md) | Same archived cutoff applied to both saved arms |
| [vectoring-fixed-baseline-scales](vectoring-fixed-baseline-scales/report.md) | Fourth-scene-only diagnostic with all baseline fitting scales retained |

## Included and excluded material

Included: Markdown reports, PNG/SVG figures, full machine-readable D attempts, rejection reasons, summaries, assignment policies, saved embeddings, screening audit records, execution manifests and verification records. Statistics and embedding files are copied byte-for-byte. A publication note is added to stage reports to distinguish historical statements from current conclusions.

**Hourly-case exception:** `changi-hourly/` publishes only its Markdown report/documentation and PNG/SVG/PDF figures. Embeddings, draw assignments, individual D attempts, machine-readable summaries, QC evidence and manifests for that case remain local. The reporting code requires an explicit local `--input` package. This restriction does not remove previously published data for other studies.

Excluded: raw OpenSky downloads, source trajectory arrays, fitted trajectory caches, authentication/session material, dependency folders, and model weights. Those stay local. Some stage reports describe local-only arrays; their names are not a claim that they are included here.

`source/` contains the original local execution/analysis scripts as provenance snapshots. Their paths refer to the original workspace and external dependencies; they are not portable entrypoints in this folder. The current portable entrypoints and saved-record postprocessing are documented in [code/README.md](../code/README.md). These snapshots are not those entrypoints. Raw data and weights are still required for inference; this is not a self-contained training/trajectory-generation environment. Manifests retain original execution paths and source hashes as historical evidence.

All new inference used the frozen strict-10-second epoch-90 Encoder, SHA-256 `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`, sum pooling and the recorded training normalization. The repository's other checkpoints must not be assumed to match it. Derived embeddings suffice to inspect the saved D calculations without that checkpoint.

The original `publication-manifest.json` and `publication-checks.json` describe the earlier publication snapshot, not later additions. The hourly case's verification records and manifests remain local with its derived data. Local paths in earlier manifests are execution metadata, not downloadable resources or credentials.
