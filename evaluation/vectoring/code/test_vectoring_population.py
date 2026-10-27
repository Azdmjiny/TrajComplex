"""Software regressions, not scene selection or correlation experiments."""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import vectoring_path as path
import vectoring_reference as ref
import vectoring_population as pop
from vectoring_inputs import llh_to_enu
from run_vectoring_eval import _check_deformed_kinematics, VectoringRejected


def inputs(n=75):
    t=np.arange(n)*10.
    raw=np.c_[t,1.+t*.00001,103.+t*.0018,np.full(n,1000.),t,np.full(n,1100.)]
    p=llh_to_enu(raw[:,1],raw[:,2],raw[:,3])
    quality={i:dict(time=float(row[0]),lat=float(row[1]),lon=float(row[2]),
                    geoaltitude=float(row[5]),lastposupdate=float(row[4]),
                    exact_position_rows=[['fixture',i]],positive_nic_exact_match=True,
                    brackets_agree_positive=True,previous_age_s=1.,next_delay_s=1.,
                    previous_quality=[[2,11,3]]) for i,row in enumerate(raw)}
    return p,raw,quality


class PopulationTests(unittest.TestCase):
    def test_missing_evidence_preserves_background_without_fit(self):
        p,raw,q=inputs()
        with patch.object(pop,'fit_track',side_effect=AssertionError('must not fit')):
            r=pop.prepare_population({'a':p},{'a':raw},{})
        np.testing.assert_array_equal(r.baseline['a'],p)
        self.assertEqual(r.injections,{})
        self.assertEqual(pop.summarize(r.records)['background_only'],1)

    def test_quality_required_outside_maneuver_and_no_silent_fill(self):
        p,raw,q=inputs();del q[0]
        with patch.object(pop,'fit_track',side_effect=AssertionError('must not fit')):
            r=pop.prepare_population({'a':p},{'a':raw},{'a':q})
        self.assertIn('missing_quality_match',r.records[0]['rejection_reasons'])
        np.testing.assert_array_equal(r.baseline['a'],p)

    def test_fit_failure_keeps_original_and_does_not_generate(self):
        p,raw,q=inputs()
        with patch.object(pop,'fit_track',side_effect=path.PathRejected('fit_failed')), patch.object(pop.path,'generate',side_effect=AssertionError('no route')):
            r=pop.prepare_population({'a':p},{'a':raw},{'a':q})
        np.testing.assert_array_equal(r.baseline['a'],p)
        self.assertFalse(r.records[0]['fit_success'])
        self.assertEqual(r.records[0]['baseline_version'],'original')

    def test_failed_route_keeps_fitted_background_and_counts_once(self):
        p,raw,q=inputs();xy=p[:,:2]+[1.,2.]
        fake=SimpleNamespace(positions=lambda t:xy.copy())
        with patch.object(pop,'fit_track',return_value=fake),patch.object(pop,'maneuver_reference',return_value=object()),patch.object(pop.path,'generate',side_effect=path.PathRejected('same_failure')):
            r=pop.prepare_population({'a':p},{'a':raw},{'a':q})
        np.testing.assert_array_equal(r.baseline['a'][:,:2],xy)
        np.testing.assert_array_equal(r.baseline['a'][:,2],p[:,2])
        self.assertEqual(pop.summarize(r.records)['rejection_counts']['same_failure'],1)
        self.assertEqual(len(r.records[0]['side_diagnostics']),2)
        self.assertEqual(pop.summarize(r.records)['fitted_background'],1)
        np.testing.assert_array_equal(r.dose([])['a'],r.baseline['a'])

    def test_direction_failure_keeps_fitted_background(self):
        p,raw,q=inputs();xy=p[:,:2]+1.
        with patch.object(pop,'fit_track',return_value=SimpleNamespace(positions=lambda t:xy)),patch.object(pop,'maneuver_reference',side_effect=path.PathRejected('direction_unreliable')),patch.object(pop.path,'generate',side_effect=AssertionError('no route')):
            r=pop.prepare_population({'a':p},{'a':raw},{'a':q})
        self.assertTrue(r.records[0]['fit_success'])
        self.assertFalse(r.records[0]['injectable'])
        np.testing.assert_array_equal(r.baseline['a'][:,:2],xy)

    def test_fitted_background_cannot_bypass_existing_basic_speed_qc(self):
        p,raw,q=inputs();xy=p[:,:2].copy();xy[20,0]+=100000
        with patch.object(pop,'fit_track',return_value=SimpleNamespace(positions=lambda t:xy)):
            r=pop.prepare_population({'a':p},{'a':raw},{'a':q})
        np.testing.assert_array_equal(r.baseline['a'],p)
        self.assertFalse(r.records[0]['fit_success'])
        self.assertIn('fitted_grid_horizontal_speed_over_500_m_s',r.records[0]['rejection_reasons'])

    def test_dose_uses_fixed_members_and_never_exposes_mutable_baseline(self):
        p=np.ones((63,3));left=p.copy();left[1,0]=2
        r=pop.PreparedPopulation({'a':p,'b':p.copy()},{'a':{-1:left,1:left.copy()}},[])
        d=r.dose([('a',-1)]);self.assertEqual(set(d),{'a','b'})
        np.testing.assert_array_equal(d['b'],p)
        d['b'][0,0]=9;self.assertEqual(r.baseline['b'][0,0],1)
        with self.assertRaises(ValueError):r.dose([('a',-1),('a',1)])
        with self.assertRaises(ValueError):r.dose([('b',1)])


class ReferenceTests(unittest.TestCase):
    def test_positive_jerk_fit_is_disk_feasible_without_redundant_boundary_solve(self):
        t=np.arange(0,721,10.);xy=np.c_[200*t,100*np.sin(t/60)]
        d={};f=ref.fit_track(xy,t,np.full(len(t),3.),d)
        self.assertEqual(d['quadratic_tie_break']['status'],'PrimalInfeasible')
        self.assertEqual(d['minimum_jerk']['status'],'Solved')
        self.assertTrue(np.all(np.linalg.norm(f.fitted_xy-f.raw_xy,axis=1)<=3))
        self.assertGreater(d['integrated_squared_jerk'],0)
        with self.assertRaisesRegex(path.PathRejected,'extrapolation'):f.positions([-1])

    def test_epoch_does_not_change_full_fit(self):
        t=np.arange(0,721,10.);xy=np.c_[200*t,100*np.sin(t/60)]
        a=ref.fit_track(xy,t,np.full(len(t),3.))
        b=ref.fit_track(xy,t+1790000000.,np.full(len(t),3.))
        np.testing.assert_allclose(a.fitted_xy,b.fitted_xy,rtol=0,atol=path.POSITION_TOL)

    def test_natural_fit_and_true_knots(self):
        t=np.arange(0,721,10.)+.001
        xy=np.c_[200*(t-t[0]),.002*(t-t[0])**2]
        d={};f=ref.fit_track(xy,t,np.full(len(t),3.),d)
        self.assertEqual(d['minimum_jerk']['status'],'ExactZeroJerkQuadratic')
        self.assertEqual(d['quadratic_tie_break']['status'],'Solved')
        self.assertEqual(d['source_points'],len(t))
        self.assertFalse(d['interpolation_grid_used_as_knots'])
        self.assertTrue(np.all(np.linalg.norm(f.fitted_xy-f.raw_xy,axis=1)<=3))
        for order in (3,4):
            np.testing.assert_allclose(f.mapping([0,720],nu=order)@f.fitted_xy,0,atol=1e-8)
        self.assertLess(d['integrated_squared_jerk'],1e-8)

    def test_uncertainty_recentered_and_not_replaced_by_smoothness(self):
        t=np.arange(0,721,10.);xy=np.c_[200*t,np.zeros(len(t))]
        f=ref.fit_track(xy,t,np.full(len(t),3.))
        a={};ref.maneuver_reference(f,t,6,a)
        f.fitted_xy=f.fitted_xy+np.c_[np.zeros(len(t)),20*np.sin(t/30)]
        b={}
        try:ref.maneuver_reference(f,t,6,b)
        except path.PathRejected:pass
        self.assertGreater(max(x['derivative_error_m_s'] for x in b['direction_intervals']),
                           max(x['derivative_error_m_s'] for x in a['direction_intervals']))

    def test_uncertain_direction_rejects_and_no_radius_shrink(self):
        t=np.arange(0,721,10.);xy=np.c_[200*t,np.zeros(len(t))]
        f=ref.fit_track(xy,t,np.full(len(t),18520.))
        with self.assertRaisesRegex(path.PathRejected,'direction_unreliable'):
            ref.maneuver_reference(f,t,6)
        np.testing.assert_array_equal(f.radii,18520.)

    def test_straight_route_both_sides_fixed_5km_10s_and_joins(self):
        t=np.arange(0,721,10.);xy=np.c_[200*t,np.zeros(len(t))]
        f=ref.fit_track(xy,t,np.full(len(t),3.));r=ref.maneuver_reference(f,t,6)
        for side in (-1,1):
            d={};q=path.generate(r,side,d,sample_s=10)
            self.assertEqual(q.shape,(61,2))
            self.assertGreaterEqual(d['continuous_peak_distance_bounds_m'][0],5000-path.POSITION_TOL)
            self.assertLessEqual(d['continuous_peak_distance_bounds_m'][1],5000+path.POSITION_TOL)
            np.testing.assert_allclose(q[[0,-1]],f.positions(t[[6,66]]),atol=path.POSITION_TOL)

    def test_solver_reduced_accuracy_is_rejected(self):
        fake=SimpleNamespace(status='AlmostSolved',iterations=1,r_prim=0.,r_dual=0.,x=[0])
        with patch.object(ref.clarabel,'DefaultSolver',return_value=SimpleNamespace(solve=lambda:fake)):
            with self.assertRaisesRegex(path.PathRejected,'AlmostSolved'):
                ref.fit_track(np.c_[np.arange(70)*2000,np.zeros(70)],np.arange(70)*10,np.full(70,3.))

    def test_low_speed_and_direction_reversal_do_not_pass_max_speed_alone(self):
        original=np.c_[np.arange(63)*2000,np.zeros(63),np.zeros(63)]
        q=original.copy();q[31,:2]=q[30,:2]
        with self.assertRaises(VectoringRejected):_check_deformed_kinematics(original,q,sample_s=10)


if __name__=='__main__':unittest.main()
