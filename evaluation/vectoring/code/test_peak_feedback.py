"""Deterministic numerical regression checks; no observational evaluation."""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import vectoring_path as p


def reference():
    t=np.arange(-10,611,10.);grid=np.arange(-5,606,5.)
    xy=np.c_[200*t,np.zeros(len(t))];original=np.c_[200*grid,np.zeros(len(grid))]
    return p.make_reference(xy,t,np.full(len(t),3.),grid,original)


def offgrid_controls(ref):
    times=np.unique(np.r_[np.arange(0,601,5.),ref.breaks])
    line=p.polyline(ref);basis=p.offset_basis(ref,times,1)
    x=np.array([2.5,1.5,1.])
    peak=(p.sampled_peak_constraint(x,ref.values(times),basis,line)[0]+1)*p.PEAK
    return x*p.PEAK/peak


class PeakFeedbackTests(unittest.TestCase):
    def test_saved_offgrid_peak_is_fed_back_and_same_route_family_is_reoptimized(self):
        ref=reference();x=offgrid_controls(ref);real_minimize=p.minimize
        line=p.polyline(ref);old=p.peak_bounds(p.construct(ref,x,1),line)
        self.assertGreater(old[0],5000+p.POSITION_TOL)
        calls=[];objectives=[]
        def solve(fun,x0,**kwargs):
            calls.append(kwargs['options']['maxiter']);objectives.append(fun)
            if len(calls)==1:
                self.assertAlmostEqual(kwargs['constraints'][0]['fun'](x),0.,places=10)
                return SimpleNamespace(success=True,x=x.copy(),nit=7,message='controlled sampled solution')
            np.testing.assert_array_equal(x0,x)
            self.assertGreater(kwargs['constraints'][0]['fun'](x),0.)
            return real_minimize(fun,x0,**kwargs)
        d={}
        with patch.object(p,'minimize',side_effect=solve):out=p.generate(ref,1,d,sample_s=10)
        self.assertEqual(out.shape,(61,2));self.assertGreaterEqual(len(calls),2)
        self.assertEqual(calls[:2],[100,93])
        self.assertTrue(all(fun is objectives[0] for fun in objectives))
        self.assertEqual(d['peak_feedback_times_s'][0],old[2])
        self.assertLessEqual(d['solver_budget_used'],100)
        self.assertLessEqual(d['peak_verification_work']['used'],p.MAX_VERIFY_NODES)
        self.assertGreaterEqual(d['continuous_peak_distance_bounds_m'][0],4999.97)
        self.assertLessEqual(d['continuous_peak_distance_bounds_m'][1],5000.03)
        self.assertGreater(d['peak_refinement_history'][1]['constraint_time_count'],d['peak_refinement_history'][0]['constraint_time_count'])

    def test_restarts_share_one_iteration_budget(self):
        ref=reference();x=offgrid_controls(ref);calls=[]
        def solve(fun,x0,**kwargs):
            calls.append(kwargs['options']['maxiter'])
            return SimpleNamespace(success=True,x=x.copy(),nit=99 if len(calls)==1 else 1,message='unchanged infeasible controls')
        d={}
        with patch.object(p,'minimize',side_effect=solve):
            with self.assertRaisesRegex(p.PathRejected,'solver_budget_exhausted'):p.generate(ref,1,d)
        self.assertEqual(calls,[100,1]);self.assertEqual(d['solver_budget_used'],100)
        self.assertEqual(len(d['peak_refinement_history']),2)

    def test_peak_subdivision_budget_is_shared_across_calls(self):
        ref=reference();pieces=p.construct(ref,offgrid_controls(ref),1);line=p.polyline(ref)
        work={'used':0};p.peak_bounds(pieces,line,work=work)
        consumed=work['used'];self.assertGreater(consumed,0)
        with patch.object(p,'MAX_VERIFY_NODES',consumed):
            with self.assertRaisesRegex(p.PathRejected,'peak_unresolved'):p.peak_bounds(pieces,line,work=work)
        self.assertEqual(work['used'],consumed)

    def test_solver_failure_cannot_be_bypassed_by_peak_feedback(self):
        ref=reference();d={}
        fake=SimpleNamespace(success=False,x=offgrid_controls(ref),nit=1,message='failed')
        with patch.object(p,'minimize',return_value=fake) as solve:
            with self.assertRaisesRegex(p.PathRejected,'solver_failed'):p.generate(ref,1,d)
        self.assertEqual(solve.call_count,1);self.assertEqual(d['peak_feedback_times_s'],[])

    def test_feedback_does_not_bypass_final_motion_checks(self):
        ref=reference()
        with patch.object(p,'verify_motion',side_effect=p.PathRejected('continuous_motion_rejected')):
            with self.assertRaisesRegex(p.PathRejected,'continuous_motion_rejected'):p.generate(ref,1)

    def test_fixed_thresholds_and_output_cadences(self):
        self.assertEqual((p.PEAK,p.POSITION_TOL,p.DURATION,p.SOLVER_MAXITER,p.MAX_VERIFY_NODES),(5000.,.03,600.,100,100000))
        self.assertEqual((p.MAX_SPEED,p.MAX_LONGITUDINAL,p.MIN_SPEED_RATIO),(500.,2.,.5))
        for cadence,n in [(5,121),(10,61)]:
            d={};q=p.generate(reference(),1,d,sample_s=cadence)
            self.assertEqual(q.shape,(n,2));self.assertGreaterEqual(d['continuous_peak_distance_bounds_m'][0],4999.97)
            self.assertLessEqual(d['continuous_peak_distance_bounds_m'][1],5000.03)


if __name__=='__main__':unittest.main()
