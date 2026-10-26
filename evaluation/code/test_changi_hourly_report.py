"""Saved-record regression checks; no inference or D estimation."""
import math
import os
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest

import report_changi_hourly as report


class HourlyReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        location = os.environ.get('CHANGI_HOURLY_INPUT')
        if not location:
            raise unittest.SkipTest('Set CHANGI_HOURLY_INPUT to the local saved-data package; it is not distributed on GitHub.')
        cls.input = Path(location)
        cls.policy = os.environ.get('CHANGI_HOURLY_POLICY', 'original')
        if cls.policy not in {'original', 'position-dedup'}:
            raise ValueError('Unknown CHANGI_HOURLY_POLICY')
        cls.rows, cls.audit = report.validate(cls.input)

    def test_saved_populations_and_failures(self):
        dedup = self.policy == 'position-dedup'
        expected_days = [('2026-09-08', (14,7,3)), ('2026-09-11', (15,8,1))] if dedup else [('2026-09-08', (11,9,4)), ('2026-09-11', (14,8,2))]
        for day, expected in expected_days:
            rows=[r for r in self.rows if r['date']==day]
            self.assertEqual(tuple(sum(report.state(r)==s for r in rows) for s in ['ok','insufficient_samples','poor_linear_fit']),expected)
        self.assertEqual(sum(r['attempted'] for r in self.rows),6600 if dedup else 6200)
        self.assertEqual(sum(r['successful'] for r in self.rows),5051 if dedup else 4613)

    def test_na_stays_in_full_hour_series(self):
        rows=sorted([r for r in self.rows if r['date']=='2026-09-11'],key=lambda x:x['hour'])
        values=[report.displayed_D(r) for r in rows]
        self.assertEqual(len(values),24)
        self.assertTrue(math.isfinite(values[9]) and math.isnan(values[10]) and math.isfinite(values[11]))
        self.assertEqual(math.isfinite(values[21]), self.policy == 'position-dedup')
        # September 8 13:00 has successful subsets but must remain NA in Scheme 1.
        row=next(r for r in self.rows if r['date']=='2026-09-08' and r['hour']==13)
        self.assertGreater(row['successful'],0)
        self.assertTrue(math.isnan(report.displayed_D(row)))

    def test_raw_audit_is_not_recovered_population(self):
        if self.policy == 'position-dedup':
            self.assertEqual(sum(x['accepted'] for x in self.audit['windows']),1697)
            self.assertTrue(all(x['accepted']==x['stage_counts_exclusive']['accepted'] for x in self.audit['windows']))
            return
        details=[x['nonadvancing_details'] for x in self.audit['windows']]
        self.assertEqual(sum(d['total'] for d in details),849)
        self.assertEqual(sum(d['other_time_flags'] for d in details),565)
        self.assertEqual(sum(d['any_backward']+d['same_time_conflicting_xy'] for d in details),0)
        self.assertEqual(sum(x['accepted'] for x in self.audit['windows']),1434)

    def test_report_uses_selected_version(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            report.report(self.rows,self.audit,Path(temp),self.policy)
            text=(Path(temp)/'report.md').read_text(encoding='utf8')
            self.assertIn('6,600' if self.policy=='position-dedup' else '6,200',text)
            self.assertIn('263 aircraft-hours' if self.policy=='position-dedup' else '849 such first rejections',text)
            if self.policy=='position-dedup':
                self.assertIn('2026-09-08 11:00: all 200 draws are the same subset',text)
                self.assertNotIn('only 10/200',text)

    def test_existing_output_is_protected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            sentinel=Path(temp)/'keep.txt';sentinel.write_text('unchanged')
            r=subprocess.run([sys.executable,str(Path(report.__file__)), '--input',str(self.input), '--output',temp],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('Output already exists',r.stderr)
            self.assertEqual(sentinel.read_text(),'unchanged')


if __name__=='__main__': unittest.main()
