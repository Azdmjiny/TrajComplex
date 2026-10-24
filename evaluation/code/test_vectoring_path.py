"""Deterministic software regressions; no observed data, Encoder or D evaluation."""
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from numpy.polynomial import Polynomial
from scipy.optimize._numdiff import approx_derivative
import vectoring_path as p


def reference(radius=3.,epoch=0.,curve=0.):
    t=np.arange(-10,611,10.)
    grid=np.arange(-5,606,5.)
    xy=np.c_[200*t,curve*t*t]
    original=np.column_stack([np.interp(grid,t,col) for col in xy.T])
    return p.make_reference(xy,t+epoch,np.full(len(t),radius),grid+epoch,original)


class ContinuousPathTests(unittest.TestCase):
    def test_offset_derivatives_match_independent_power_polynomials(self):
        ref=reference();times=np.array([0.,.001,5.,123.456,300.,599.999,600.])
        u=Polynomial([0.,1.]);one=Polynomial([1.,-1.])
        for side in (-1,1):
            normal=side*np.array([-ref.axis[1],ref.axis[0]])
            for order in range(4):
                expected=np.stack([(p.PEAK*p.math.comb(8,j)*u**j*one**(8-j)).deriv(order)(times/p.DURATION)/p.DURATION**order
                                   for j in (3,4,5)],axis=-1)[:,None,:]*normal[None,:,None]
                np.testing.assert_allclose(p.offset_basis(ref,times,side,order),expected,atol=1e-9,rtol=1e-10)

    def test_offset_derivatives_do_not_depend_on_coordinate_origin(self):
        ref=reference();shifted=SimpleNamespace(axis=ref.axis,origin=np.array([1e12,-1e12]))
        for order in range(4):
            np.testing.assert_array_equal(p.offset_basis(ref,[.001,250.,599.999],1,order),
                                          p.offset_basis(shifted,[.001,250.,599.999],1,order))

    def test_short_reference_intervals_have_reliable_solver_derivatives(self):
        t=np.arange(-10,611,10.)+.001;grid=np.arange(-5,606,5.)
        xy=np.c_[200*t,.001*t*t]
        original=np.column_stack([np.interp(grid,t,col) for col in xy.T])
        ref=p.make_reference(xy,t,np.full(len(t),3.),grid,original)
        self.assertLess(np.diff(ref.breaks).min(),.00101)
        def inspect(fun,x0,*,jac,method,bounds,constraints,options):
            x=x0+np.array([.08,-.04,.02])
            motion=constraints[1]
            numeric=approx_derivative(motion['fun'],x,method='2-point',abs_step=np.sqrt(np.finfo(float).eps))
            np.testing.assert_allclose(motion['jac'](x),numeric,atol=2e-7,rtol=2e-5)
            # This larger symmetric diagnostic step checks the objective
            # derivative without subtracting nearly identical objective values.
            obj_numeric=approx_derivative(fun,x,method='3-point',abs_step=1e-3).ravel()
            np.testing.assert_allclose(jac(x),obj_numeric,atol=1e-9,rtol=2e-4)
            self.assertEqual(options['maxiter'],100)
            self.assertEqual(options['ftol'],p.POSITION_TOL/p.PEAK)
            return SimpleNamespace(success=False,message='inspection only',nit=0,x=x)
        with patch.object(p,'minimize',side_effect=inspect):
            with self.assertRaisesRegex(p.PathRejected,'solver_failed'):p.generate(ref,1)

    def test_motion_jacobian_matches_finite_differences_both_sides(self):
        ref=reference(curve=.005);t=np.array([37.,141.,287.,431.,563.]);x=np.array([1.4,1.7,1.2])
        for side in (-1,1):
            args=(ref.values(t,1),ref.values(t,2),p.offset_basis(ref,t,side,1),p.offset_basis(ref,t,side,2))
            values,jac=p.sampled_motion_constraints(x,*args)
            numeric=approx_derivative(lambda c:p.sampled_motion_constraints(c,*args)[0],x,method='3-point')
            np.testing.assert_allclose(jac,numeric,atol=1e-9,rtol=1e-6)
            self.assertEqual(values.shape,(20,))

    def test_peak_jacobian_reselects_active_sample_and_segment(self):
        ref=reference();times=np.array([100.,250.,400.,500.]);basis=p.offset_basis(ref,times,1)
        positions=np.c_[times*200,np.zeros(len(times))]
        line={'a':np.array([[0.,0.],[60000.,0.]]),'b':np.array([[60000.,0.],[120000.,0.]])}
        branches=[]
        for x in (np.array([3.,.2,.1]),np.array([.1,.2,3.])):
            value,jac,active=p.sampled_peak_constraint(x,positions,basis,line)
            numeric=approx_derivative(lambda c:p.sampled_peak_constraint(c,positions,basis,line)[0],x,method='3-point').ravel()
            np.testing.assert_allclose(jac,numeric,atol=1e-10,rtol=1e-7)
            branches.append((active['sample_index'],active['segment_index']))
        self.assertNotEqual(branches[0],branches[1])

    def test_peak_ties_and_zero_distance_are_deterministic_and_finite(self):
        ref=reference();times=np.array([100.,500.]);basis=p.offset_basis(ref,times,1)
        positions=np.c_[times*200,np.zeros(len(times))]
        line={'a':np.array([[0.,0.]]),'b':np.array([[120000.,0.]])}
        value,jac,active=p.sampled_peak_constraint(np.zeros(3),positions,basis,line)
        self.assertEqual(value,-1.)
        np.testing.assert_array_equal(jac,np.zeros(3))
        self.assertEqual(active['maximizing_sample_ties'],2)
        self.assertEqual(active['sample_index'],0)

    def test_gentle_curve_has_actual_cross_track_peak_not_same_time_offset(self):
        ref=reference(curve=.01)
        for side in (-1,1):
            detail={};q=p.generate(ref,side,detail)
            lo,hi=detail['continuous_peak_distance_bounds_m']
            self.assertGreaterEqual(lo,4999.97);self.assertLessEqual(hi,5000.03)
            # A chord-normal displacement is not the same as spatial distance.
            displacement=np.linalg.norm(q-(p.sample_pieces(ref.pieces,np.arange(0,601,5))+ref.origin),axis=1)
            line=p.polyline(ref)
            distance=p.point_segment(q-ref.origin,line['a'],line['b'])[0].min(axis=1)
            self.assertGreater(float(np.max(displacement-distance)),0.1)

    def test_straight_fixed_distance_and_c2_joins_both_sides(self):
        ref=reference()
        for side in (-1,1):
            detail={};q=p.generate(ref,side,detail)
            self.assertEqual(q.shape,(121,2))
            self.assertAlmostEqual(np.max(np.abs(q[:,1])),5000.,places=2)
            lo,hi=detail['continuous_peak_distance_bounds_m']
            self.assertGreaterEqual(lo,4999.97);self.assertLessEqual(hi,5000.03)
            pieces=p.construct(ref,np.array(detail['controls_m'])/p.PEAK,side)
            for order,tol in [(0,p.POSITION_TOL),(1,p.SPEED_TOL),(2,p.ACCELERATION_TOL)]:
                np.testing.assert_allclose(p.sample_pieces(pieces,[0,600],order),
                    p.sample_pieces(ref.pieces,[0,600],order),atol=tol,rtol=0)
            json.dumps(detail,allow_nan=False)

    def test_epoch_translation_does_not_change_geometry(self):
        a=reference();b=reference(epoch=1790000000.)
        np.testing.assert_allclose(p.sample_pieces(a.pieces,[0,123.4,600]),
                                   p.sample_pieces(b.pieces,[0,123.4,600]),rtol=0,atol=1e-8)

    def test_nacp_uncertainty_cannot_be_ignored(self):
        with self.assertRaisesRegex(p.PathRejected,'direction_unreliable'):
            reference(radius=18520.)

    def test_known_radius_collapse_cannot_enter_new_generator(self):
        t=np.arange(-10,611,10.);grid=np.arange(-5,606,5.)
        xy=np.c_[5000*np.cos(t*200/5000),5000*np.sin(t*200/5000)]
        original=np.column_stack([np.interp(grid,t,col) for col in xy.T])
        with self.assertRaisesRegex(p.PathRejected,'direction_unreliable'):
            p.make_reference(xy,t,np.full(len(t),3.),grid,original)

    def test_wrong_grid_or_missing_observations_reject(self):
        t=np.arange(-10,611,10.);grid=np.arange(-5,606,5.);xy=np.c_[t*200,np.zeros(len(t))]
        original=np.c_[grid*200,np.zeros(len(grid))]
        bad=original.copy();bad[50,1]=1.
        with self.assertRaisesRegex(p.PathRejected,'provenance_mismatch'):
            p.make_reference(xy,t,np.full(len(t),3.),grid,bad)
        xy[20,0]=np.nan
        with self.assertRaisesRegex(p.PathRejected,'invalid_continuous_reference_support'):
            p.make_reference(xy,t,np.full(len(t),3.),grid,original)

    def test_solver_success_does_not_bypass_fixed_peak(self):
        fake=SimpleNamespace(success=True,message='synthetic solver result',nit=0,x=np.zeros(3))
        with patch.object(p,'minimize',return_value=fake):
            with self.assertRaisesRegex(p.PathRejected,'cross_track_not_fixed_5km'):
                p.generate(reference(),1)

    def test_solver_failure_is_not_claimed_global_infeasibility(self):
        fake=SimpleNamespace(success=False,message='iteration limit',nit=100,x=np.ones(3))
        with patch.object(p,'minimize',return_value=fake):
            with self.assertRaisesRegex(p.PathRejected,'no_validated_path_solver_failed'):
                p.generate(reference(),1)

    def test_between_sample_acceleration_is_checked(self):
        # A five-second polynomial leaves endpoints unchanged but is violent
        # between them. A sample-only position/speed check would miss it.
        ref=reference();a,b,r=ref.pieces[0]
        c=p.elevate(r,8).copy();c[3:6,1]+=100.
        pieces=[(a,b,c)]+ref.pieces[1:]
        with self.assertRaises(p.PathRejected):p.verify_motion(pieces,ref)

    def test_verification_work_cap_rejects_instead_of_accepting(self):
        ref=reference()
        with patch.object(p,'MAX_VERIFY_NODES',0):
            with self.assertRaisesRegex(p.PathRejected,'unresolved'):p.generate(ref,1)


if __name__=='__main__':unittest.main()
