"""The current summary reads saved evidence and does not relabel diagnostics."""
import tempfile,unittest
from pathlib import Path
from evaluation_runtime import RUNS
from build_report import build_report

class ReportProvenanceTests(unittest.TestCase):
    def test_current_counts_and_mixed_signs_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder);data=build_report(RUNS,output)
            text=(output/'report.md').read_text()
            self.assertIn('+0.661',text);self.assertIn('+0.598',text);self.assertIn('-0.319',text)
            self.assertIn('Unavailable',text);self.assertIn('outcome-selected',text)
            self.assertEqual(data['fixed']['fixed_valid_records'],26)

if __name__=='__main__':unittest.main()
