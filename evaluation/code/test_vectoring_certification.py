"""Numerical regressions, independent of observed scenes and correlation."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from scipy.optimize._numdiff import approx_derivative
import vectoring_path as p
import vectoring_certification as c
from test_vectoring_path import reference


class StableCertificateTests(unittest.TestCase):
    def test_true_nearest_branch_switch_is_rejected_with_a_witness(self):
        # Parabola r(u)=(4u-2,(4u-2)^2); points above its focal region
        # have two competing nearest positions, switching as q crosses x=0.
        r=np.array([[-2.,4.],[0.,-4.],[2.,4.]])
        query=(0.,1.,np.array([[-.01,2.],[.01,2.]]))
        w=c.branch_witness(query,[(0.,1.,r)],.5)
        self.assertIsNotNone(w);self.assertEqual(w['classification'],'nearest_branch_conflict')
        self.assertAlmostEqual(w['time_s'],.5,places=10)
        self.assertGreater(w['reference_separation_m'],2.)
        self.assertLess(w['convexity'],0.)
        line=p.polyline(SimpleNamespace(pieces=[(0.,1.,r)]))
        with self.assertRaisesRegex(p.PathRejected,'branch_conflict'):
            p.verify_projection([query],line,1)

    def test_correlated_convexity_bound_contains_independent_dense_values(self):
        r=np.array([[-2.,4.],[0.,-4.],[2.,4.]])
        v=p.derivative(r,1.);acc=p.derivative(v,1.)
        refs=[c.edge(0.,1.,r,v,acc)];qc=np.array([[-.1,-2.],[.1,-1.9]])
        q=p.middle(qc);lower=c.convexity_envelope(refs,q,qc)
        for s in np.linspace(0,1,61):
            pos=p.split(r,s)[0][-1];vel=p.split(v,s)[0][-1];a=p.split(acc,s)[0][-1]
            for z in np.linspace(0,1,11):
                query=p.split(qc,z)[0][-1]
                self.assertLessEqual(lower,float(vel@vel+(pos-query)@a)+1e-12)

    def test_derivative_subdivision_retains_nonzero_velocity_at_ulp_width(self):
        # Position differences at this scale are dominated by cancellation.
        a,b=0.,600.;curve=np.array([[1.e5,2.e5],[2.2e5,2.e5]])
        v=p.derivative(curve,b-a)
        for _ in range(55):
            curve=p.split(curve)[1];v=p.split(v)[1]
        np.testing.assert_allclose(v,[[200.,0.]],atol=0,rtol=0)
        bounds=c.motion_envelope(v,np.array([[0.,0.]]),v)
        self.assertTrue(np.all(bounds>0))

    def test_actual_off_grid_motion_failure_returns_solver_witness(self):
        ref=reference();a,b,r=ref.pieces[0]
        curve=p.elevate(r,8).copy();curve[3:6,1]+=100.
        with self.assertRaises(p.PathRejected) as context:
            p.verify_motion([(a,b,curve)]+ref.pieces[1:],ref)
        w=context.exception.witness
        self.assertEqual(w['kind'],'motion');self.assertGreater(w['time_s'],a);self.assertLess(w['time_s'],b)

    def test_projection_feedback_jacobian_matches_finite_difference(self):
        ref=reference(curve=.01);w=[dict(time_s=310.,reference_time_s=290.)]
        for side in [-1,1]:
            x=np.array([1.,2.,1.]);value,jac=c.convexity_constraints(x,w,ref,side)
            numeric=approx_derivative(lambda z:c.convexity_constraints(z,w,ref,side)[0],x)
            np.testing.assert_allclose(jac,numeric.reshape(1,3),atol=1e-9,rtol=1e-7)

    def test_unresolved_work_is_rejected_not_accepted(self):
        ref=reference();line=p.polyline(ref)
        with patch.object(p,'MAX_VERIFY_NODES',0):
            with self.assertRaisesRegex(p.PathRejected,'work_budget_unresolved'):
                p.verify_projection(ref.pieces,line,1)

    def test_straight_route_passes_with_original_thresholds(self):
        ref=reference()
        with patch.object(p,'PEAK',5000.):
            for side in [-1,1]:
                detail={};q=p.generate(ref,side,detail,sample_s=10)
                self.assertEqual(q.shape,(61,2))
                lo,hi=detail['continuous_peak_distance_bounds_m']
                self.assertGreaterEqual(lo,5000-p.POSITION_TOL);self.assertLessEqual(hi,5000+p.POSITION_TOL)

    def test_motion_witness_is_added_without_resetting_solver_budget(self):
        ref=reference();calls=[];real=p.minimize;real_motion=p.verify_motion
        def solver(*args,**kwargs):
            calls.append(kwargs['options']['maxiter']);return real(*args,**kwargs)
        count=0
        def checked(pieces,reference):
            nonlocal count
            count+=1
            if count==1:c.fail('continuous_longitudinal_acceleration_over_limit',dict(kind='motion',time_s=123.456,quantity='test'))
            return real_motion(pieces,reference)
        with patch.object(p,'PEAK',5000.),patch.object(p,'minimize',side_effect=solver),patch.object(p,'verify_motion',side_effect=checked):
            detail={};p.generate(ref,1,detail)
        self.assertEqual(len(detail['failure_feedback']),1)
        self.assertLess(calls[1],calls[0]);self.assertLessEqual(detail['solver_budget_used'],100)


if __name__=='__main__':unittest.main()
