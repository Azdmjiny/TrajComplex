# Encoder evidence and reports

[Encoder overview](../README.md)

Start with [RESULTS_ZH.md](RESULTS_ZH.md) for the scientific summary. The files below preserve different stages of the experiment, not successive copies of one result.

| Group | Main files |
| --- | --- |
| Data and preprocessing | `data_audit.json`, `quality_summary.json`, `preprocess.json`, `split_manifest.csv` |
| Selection protocol | `frozen_protocol.json`, `screening_selection.json`, `selection.json` |
| Held-out comparisons | `test_results.json`, `untrained_test_results.json`, `three_seed_summary.json`, `probe_summary.csv` |
| Confounding diagnostics | `confounding_and_route.json` |
| Checkpoint/export checks | `checkpoint_manifest.json`, `export_verification.json`, `candidate_loading_check.json` |
| Runtime and implementation | `benchmark.json`, `implementation_checks.json`, `runtime_events.json` |
| Provenance and delivery | `additional_provenance.json`, `public_data_verification.json`, `delivery_archive.json` |
| Figures | `training_curves.png`, `dimension_pooling.png`, `baseline_comparison.png` |

Historical manifests describe their original runs or archives; a recorded archive may not exist in a fresh checkout. `make_report.py` also needs local `runs/` histories, so saved reports alone are not all its inputs. Reading these reports requires no retraining. Model-selection evidence should remain separate from downstream [evaluation](../../evaluation/README.md).
