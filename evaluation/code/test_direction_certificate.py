"""Regression tests for direction certification, not new evaluation experiments."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import vectoring_reference as ref
import vectoring_path as path


def fixture(raw, fitted, radii):
    return SimpleNamespace(raw_xy=np.asarray(raw,float),fitted_xy=np.asarray(fitted,float),
                           radii=np.asarray(radii,float))


class DirectionCertificateTests(unittest.TestCase):
    def test_exact_disk_avoids_unnecessary_recentering_expansion(self):
        f=fixture([[250,0]],[[240,10]],[30])
        vw=np.ones((1,1)); previous=(30+np.sqrt(200))/240
        self.assertGreater(previous,np.sin(path.DIRECTION_ERROR))
        d=ref.certify_local_direction(f,[(0.,1.,vw)],0.)
        self.assertEqual(d['status'],'continuous_certificate_pass')
        self.assertLess(ref._direction_point(vw[0],f)['maximum_direction_error_deg'],10)
        np.testing.assert_array_equal(f.radii,[30])

    def test_off_grid_failure_cannot_pass_using_only_endpoints(self):
        f=fixture([[200,0],[0,200]],[[200,0],[0,0]],[1,1])
        vw=np.array([[1.,0],[1.,1],[1.,0]])
        self.assertTrue(ref._direction_point(vw[0],f)['passed'])
        self.assertTrue(ref._direction_point(vw[-1],f)['passed'])
        d=ref.certify_local_direction(f,[(0.,1.,vw)],0.)
        self.assertEqual(d['status'],'point_witness_failure')
        self.assertEqual(d['witness']['time_s'],.5)

    def test_subdivision_proves_curved_velocity_interval(self):
        f=fixture([[200,200],[200,-200]],[[200,200],[200,-200]],[.1,.1])
        vw=np.eye(2)
        self.assertFalse(ref._direction_interval(vw,f)[0])
        d=ref.certify_local_direction(f,[(0.,1.,vw)],0.)
        self.assertEqual(d['status'],'continuous_certificate_pass')
        self.assertGreater(d['subdivisions'],0)

    def test_unresolved_budget_is_not_acceptance_or_confirmed_failure(self):
        f=fixture([[200,200],[200,-200]],[[200,200],[200,-200]],[.1,.1])
        with patch.object(path,'MAX_VERIFY_NODES',1):
            d=ref.certify_local_direction(f,[(0.,1.,np.eye(2))],0.)
        self.assertEqual(d['status'],'unresolved')
        self.assertEqual(d['cause'],'verification_budget_exhausted')
        self.assertEqual(d['nodes'],1)

    def test_observation_uncertainty_and_zero_velocity_are_not_erased(self):
        for raw,fitted,radius in [([200,0],[200,0],40),([0,0],[200,0],1),([200,0],[0,0],1)]:
            f=fixture([raw],[fitted],[radius])
            d=ref.certify_local_direction(f,[(0.,1.,np.ones((1,1)))],0.)
            self.assertEqual(d['status'],'point_witness_failure')

    def test_join_failure_cannot_be_hidden_by_maneuver_pass(self):
        f=fixture([[200,0],[0,200]],[[200,0],[0,0]],[1,1])
        maneuver=(0.,600.,np.array([[1.,0]]))
        join=(-10.,0.,np.array([[1.,1]]))
        self.assertEqual(ref.certify_local_direction(f,[maneuver],0.)['status'],'continuous_certificate_pass')
        d=ref.certify_local_direction(f,[maneuver,join],0.)
        self.assertEqual(d['status'],'point_witness_failure')
        self.assertLess(d['witness']['time_s'],0)

    def test_reversed_reference_still_rejected_by_independent_chord_gate(self):
        t=np.arange(0,721,10.)
        xy=np.c_[200*t+30000*np.sin(t/75),10000*np.cos(t/75)]
        f=ref.fit_track(xy,t,np.full(len(t),3.)); detail={}
        with self.assertRaises(path.PathRejected):ref.maneuver_reference(f,t,6,detail)
        self.assertEqual(detail['direction_certificate']['status'],'continuous_certificate_pass')
        self.assertIn('reference_chord_progress_nonpositive',detail['rejection_reasons'])
        self.assertNotIn('continuous_reference_direction_unreliable',detail['rejection_reasons'])
        self.assertEqual(detail['curvature_status'],'blocked_by_chord_progress')


if __name__=='__main__':unittest.main()
