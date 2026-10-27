"""Organization regression checks. No inference, D computation or generation."""
from pathlib import Path
import tempfile
import unittest
from evaluation_layout import EVALUATION_ROOT, HISTORY_ROOT, STUDIES, study_path, relocated_path, check_output_location, configure_imports

class EvaluationLayoutTests(unittest.TestCase):
    def test_registered_packages_exist(self):
        for name,relative in STUDIES.items():
            self.assertEqual(study_path(name), EVALUATION_ROOT/relative)
            self.assertTrue(study_path(name).is_dir(),name)
        self.assertTrue(study_path('holding-equal-duration/results/summary.json').is_file())

    def test_old_manifest_paths_resolve(self):
        self.assertEqual(relocated_path('runs/vectoring-20s-repaired/report.md'),
                         study_path('vectoring-20s-repaired/report.md'))
        self.assertTrue(relocated_path('code/run_holding_eval.py').is_file())
        self.assertTrue(relocated_path('runs/changi-hourly/appendix-original/report.md').is_file())
        self.assertEqual(relocated_path('runs/strict-10s-reference/results/summary.json'),
                         HISTORY_ROOT/'strict-10s-reference/results/summary.json')
        self.assertTrue(relocated_path('archive/legacy-before-workflow-integration/inventory.json').is_file())
        self.assertTrue(relocated_path('figures/holding-vs-vectoring-comparison.png').is_file())

    def test_external_run_root_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(study_path('holding-equal-duration/results',folder),
                             Path(folder)/'holding-equal-duration/results')

    def test_output_protection_follows_moved_evidence(self):
        for path in [EVALUATION_ROOT, *[EVALUATION_ROOT/x/'main/new-run' for x in ('holding','vectoring','hourly','star','histry','report')],
                     study_path('holding-equal-duration')/'new-output']:
            with self.assertRaises(ValueError): check_output_location(path)
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(check_output_location(folder),Path(folder).resolve())

    def test_shared_import_paths_are_idempotent(self):
        import sys
        configure_imports(); before=list(sys.path); configure_imports()
        self.assertEqual(before,sys.path)
        for topic in ('holding','vectoring','hourly'):
            self.assertIn(str(EVALUATION_ROOT/topic/'code'),sys.path)

    def test_shared_reference_and_legacy_root_alias(self):
        expected=HISTORY_ROOT/'strict-10s-reference/results/run-manifest.json'
        for root in (None, HISTORY_ROOT, EVALUATION_ROOT/'runs', EVALUATION_ROOT):
            self.assertEqual(study_path('strict-10s-reference/results/run-manifest.json',root),expected)
        self.assertTrue(expected.is_file())

    def test_report_redirect_and_retired_top_level_folders(self):
        self.assertTrue((EVALUATION_ROOT/'report/report.md').is_file())
        self.assertIn('](report/report.md)',(EVALUATION_ROOT/'report.md').read_text(encoding='utf8'))
        for old in ('runs','archive','figures'):
            self.assertFalse((EVALUATION_ROOT/old).exists(),old)

if __name__=='__main__': unittest.main()
