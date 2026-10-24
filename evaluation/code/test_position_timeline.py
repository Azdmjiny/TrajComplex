"""Timing regression checks only; no Encoder or evaluation experiment."""
import unittest
import numpy as np
from position_timeline import position_grid, resample_positions
from trajectory_quality import quality_reasons
from run_vectoring_eval import _source_support


class PositionTimeTests(unittest.TestCase):
    def test_constant_motion_with_variable_snapshot_age_has_no_speed_spike(self):
        snapshots=np.arange(0,100,10.)
        updates=snapshots-np.array([1,4,1,4,1,4,1,4,1,4])
        raw=np.column_stack((snapshots,updates*.001,updates*.002,np.zeros(10),updates))
        enu=np.column_stack((updates*250,np.zeros(10),snapshots*2))
        grid=position_grid(raw)
        p=resample_positions(raw,enu,grid)
        np.testing.assert_allclose(np.diff(p[:,0])/5,250)
        np.testing.assert_allclose(np.diff(p[:,0],n=2),0,atol=1e-9)
        np.testing.assert_allclose(p[:,2],grid*2)
        self.assertEqual(grid[-1],85)
        self.assertLessEqual(grid[-1],updates[-1])
        with self.assertRaisesRegex(ValueError,'extrapolation'):
            resample_positions(raw,enu,np.array([90.]))

    def test_update_support_not_snapshot_support(self):
        snapshots=np.arange(0,710,10.)
        updates=snapshots-4
        raw=np.column_stack((snapshots,updates*.001,updates*.002,np.zeros(len(updates)),updates))
        grid=position_grid(raw)
        p=np.column_stack((grid*200,np.zeros(len(grid)),np.zeros(len(grid))))
        d={}
        self.assertEqual(_source_support(p,raw,d),[])
        for s,t in zip(d['sample_support'],d['sample_times']):
            self.assertLessEqual(updates[s['left_raw_index']],t)
            self.assertGreaterEqual(updates[s['right_raw_index']],t)
        # t=90 belongs between update times 86 and 96, not snapshot time 90.
        s=next(s for s,t in zip(d['sample_support'],d['sample_times']) if t==90)
        self.assertEqual((s['left_raw_index'],s['right_raw_index']),(9,10))

    def test_invalid_updates_are_not_sorted_filled_or_merged(self):
        raw=np.array([[0,1,100,0,-1],[10,2,101,0,9],[20,3,102,0,19]],float)
        for value in (-1,-2,float('nan')):
            bad=raw.copy();bad[1,4]=value
            with self.assertRaises(ValueError):position_grid(bad)
        bad=raw.copy();bad[1,1:3]=bad[0,1:3]
        with self.assertRaisesRegex(ValueError,'repeated'):position_grid(bad)

    def test_speed_quality_uses_update_clock_vertical_keeps_snapshot_clock(self):
        obs=np.array([[0,1,100,0],[10,1.01,100.01,0],[20,1.02,100.02,0]])
        times=np.array([-1.,5.,19.])
        enu=np.column_stack((times*250,np.zeros(3),np.array([0,500,1000])))
        self.assertIn('horizontal_speed',quality_reasons(obs,enu,300))
        self.assertEqual(quality_reasons(obs,enu,300,position_times=times),[])


if __name__=='__main__':unittest.main()
