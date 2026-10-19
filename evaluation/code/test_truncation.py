import unittest
from truncation import choose_cutoff,curve_correlation

def trials(values):
    return [dict(dose_curve=[dict(holding_aircraft=k,dimension=v,status='ok' if v is not None else 'unestimable') for k,v in enumerate(row)]) for row in values]

class TruncationTests(unittest.TestCase):
    def test_peak_shared_and_earliest(self):
        ts=trials([[1,2,4,4,2]]*5)
        self.assertEqual(choose_cutoff(ts)['cutoff'],2)
    def test_single_rep_outlier_not_peak(self):
        ts=trials([[1,2,3,100],[1,2,3,None],[1,2,3,None],[1,2,3,None],[1,2,3,None]])
        self.assertEqual(choose_cutoff(ts)['cutoff'],2)
    def test_missing_no_peak(self):
        self.assertIsNone(choose_cutoff(trials([[None]*5]*5))['cutoff'])
    def test_minimum_valid_points(self):
        c=trials([[1,2,3,4,5,4,3]])[0]['dose_curve']
        self.assertIsNone(curve_correlation(c,'holding_aircraft',3)['rho'])
        self.assertAlmostEqual(curve_correlation(c,'holding_aircraft',4)['rho'],1)
    def test_finite_but_invalid_status_excluded(self):
        c=trials([[1,2,3,4,5]])[0]['dose_curve'];c[4]['status']='unestimable'
        self.assertIsNone(curve_correlation(c,'holding_aircraft')['rho'])

if __name__=='__main__':unittest.main()
