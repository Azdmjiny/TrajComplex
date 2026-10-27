# Vectoring code

| Modules | Responsibility |
|---|---|
| `vectoring_inputs.py`, `vectoring_uncertainty.py` | Source records and quality evidence |
| `vectoring_reference.py` | Continuous reference fit and direction reliability |
| `vectoring_path.py`, `vectoring_certification.py` | Route construction, continuous checks and witness feedback |
| `vectoring_population.py` | Separate background and injectable population; paired baselines |
| `screen_vectoring_candidates.py`, `screen_approved_scenes.py` | Explicit original-scope screening interfaces |
| `run_vectoring_eval.py`, `evaluate_saved_vectoring.py` | Geometry helpers and frozen-population evaluation |
| `diagnose_fixed_scales.py`, `audit_vectoring_missing_quality.py` | Saved-record diagnostics |
| `test_*.py` | Numerical and geometry regressions |

The general `screen_approved_scenes.py` interface targets the earlier exact
26-identity evidence set; it does not silently rebuild the latest 20-second
population. The latest run's actual execution snapshots are in
[main/vectoring-20s-repaired/source](../main/vectoring-20s-repaired/source), with
their original private workspace paths preserved. New runs need explicitly
supplied local source/evidence/checkpoint packages.

```bash
python evaluation/vectoring/code/screen_approved_scenes.py --help
python evaluation/code/run_evaluation.py vectoring --help
python -m unittest discover -s evaluation/vectoring/code -p "test_vectoring_certification.py"
```

No physical threshold, optimizer parameter or estimator gate changed during
organization. Shared source-time/QC code remains in `../../code/`.
