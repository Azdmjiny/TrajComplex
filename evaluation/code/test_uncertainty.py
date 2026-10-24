import unittest
import numpy as np
from vectoring_uncertainty import local_frame,quality_radii

class UncertaintyTests(unittest.TestCase):
    def test_straight_conditional_bounds_and_unit_normals(self):
        t=np.arange(7)*10.;xy=np.column_stack((t*200,np.zeros(7)))
        f=local_frame(xy,t,np.full(7,30.),t[1:-1])
        self.assertTrue(np.all(f['curvature_intervals'][:,0]<=0))
        self.assertTrue(np.all(f['curvature_intervals'][:,1]>=0))
        np.testing.assert_allclose(np.linalg.norm(f['normals'],axis=1),1)

    def test_exact_quadratic_derivatives_contained_under_bounded_errors(self):
        t=np.arange(5)*10.;true=np.column_stack((200*t,t*t))
        # Fixed adversarial disk-bound perturbations, not a Monte Carlo study.
        for signs in ([1,-1,1,-1,1],[-1,1,-1,1,-1]):
            observed=true+np.column_stack((np.zeros(5),np.asarray(signs)*10))
            f=local_frame(observed,t,np.full(5,10.),[20.])
            expected=400/(200**2+40**2)**1.5
            self.assertLessEqual(f['curvature_intervals'][0,0],expected)
            self.assertGreaterEqual(f['curvature_intervals'][0,1],expected)

    def test_uncertain_direction_rejected(self):
        t=np.arange(5)*10.;xy=np.column_stack((t,np.zeros(5)))
        with self.assertRaisesRegex(ValueError,'direction_uncertainty'):
            local_frame(xy,t,np.full(5,30.),[20.])

    def test_time_gap_cannot_be_filled(self):
        raw=np.array([[0.,1.,100.,1000.,0.]])
        row=dict(time='0',lat='1',lon='100',geoaltitude='1000',lastposupdate='0',exact_position_rows=[0],positive_nic_exact_match=True,brackets_agree_positive=True,previous_age_s=10.001,next_delay_s=1.,previous_quality=[[2,9,3]])
        radii,reasons=quality_radii(raw,[0],{0:row})
        self.assertIsNone(radii);self.assertIn('status_bracket_over_10_s',reasons)
        row['previous_age_s']=10.
        self.assertEqual(quality_radii(raw,[0],{0:row})[0][0],30.)
        row['lat']='2'
        self.assertIn('quality_source_mismatch',quality_radii(raw,[0],{0:row})[1])

    def test_inconsistent_quadratic_rejected(self):
        t=np.arange(5)*10.;xy=np.column_stack((200*t,np.array([0,0,1000,0,0])))
        with self.assertRaisesRegex(ValueError,'model_inconsistent'):
            local_frame(xy,t,np.full(5,10.),[20.])

if __name__=='__main__':unittest.main()
