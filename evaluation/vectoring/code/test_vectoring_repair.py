"""Regression checks for known defects; no Encoder or evaluation experiment."""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import ast
import csv
import gzip
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile
import numpy as np
import run_vectoring_eval as v
import vectoring_path as path
from position_timeline import position_grid, resample_positions
from build_report import count_candidate_reasons


def straight(n=141):
    p=np.column_stack((np.arange(n)*1000.,np.zeros(n),np.zeros(n)))
    times=np.arange(0,(n-1)*5+1,10.)
    raw=np.column_stack((times,np.ones(len(times)),100+times*.001,
                         np.zeros(len(times)),times))
    return p,raw


class VectoringRepairTests(unittest.TestCase):
    def test_quality_checked_paths_reused_only_for_same_trajectory(self):
        p,raw=straight()
        matches={i:dict(zip(['time','lat','lon','geoaltitude','lastposupdate'],row))
                 for i,row in enumerate(raw)}
        for row in matches.values():
            row.update(exact_position_rows=[0],positive_nic_exact_match=True,
                       brackets_agree_positive=True,previous_age_s=1.,next_delay_s=1.,
                       previous_quality=[[2,11,3]])
        # Use the reader's ENU transform in the test without importing torch.
        node=next(n for n in ast.parse((EVALUATION_ROOT/'holding/code/run_holding_eval.py').read_text(encoding='utf8')).body
                  if isinstance(n,ast.FunctionDef) and n.name=='llh_to_enu')
        import math
        ns=dict(np=np,math=math,A=6378137.,E2=6.69437999014e-3,
                LAT0=math.radians(1.3592111111111111),LON0=math.radians(103.989325),H0=6.66)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'transform','exec'),ns)
        enu=ns['llh_to_enu'](raw[:,1],raw[:,2],raw[:,3])
        p=resample_positions(raw,enu,position_grid(raw))
        prepared={};diag={}
        with patch.dict('sys.modules',{'run_holding_eval':SimpleNamespace(llh_to_enu=ns['llh_to_enu'])}), patch.object(path,'generate',wraps=path.generate) as generator:
            ok,reasons=v.vectoring_eligibility(p,raw,quality_matches=matches,prepared=prepared,diagnostics=diag)
            self.assertTrue(ok,reasons);self.assertEqual(generator.call_count,2)
            for side in (-1,1):
                q,start,end=v.add_vectoring(p,side,frame=prepared)
                np.testing.assert_array_equal(q[:,2],p[:,2])
                np.testing.assert_array_equal(q[:start],p[:start])
                np.testing.assert_array_equal(q[end:],p[end:])
                q[:]=0
                self.assertFalse(np.all(v.add_vectoring(p,side,frame=prepared)[0]==0))
            self.assertEqual(generator.call_count,2)
            changed=p.copy();changed[0,0]+=1
            with self.assertRaisesRegex(v.VectoringRejected,'trajectory_mismatch'):
                v.add_vectoring(changed,1,frame=prepared)
            self.assertFalse(v.vectoring_eligibility(p,raw,prepared=prepared)[0])
            self.assertEqual(prepared,{})
        json.dumps(diag,allow_nan=False)

    def test_deduplicate_after_normalizing_sides(self):
        counts=count_candidate_reasons([
            dict(rejection_reasons=['side_-1:curvature','side_1:curvature','stale']),
            dict(rejection_reasons=['side_1:curvature'])])
        self.assertEqual(counts,{'curvature':2,'stale':1})

    def test_missing_source_cannot_bypass_screen(self):
        p,_=straight()
        self.assertEqual(v.vectoring_eligibility(p),(False,['missing_source_observations']))

    def test_interpolation_bracket_outside_old_window_is_checked(self):
        p,raw=straight(125)
        # Maneuver begins at t=10. Its preceding sample at t=5 uses t=0,
        # outside the old [start-5,end+5] raw filter. That source is stale.
        raw[0,4]=-30
        diagnostics={}
        ok,reasons=v.vectoring_eligibility(p,raw,diagnostics=diagnostics)
        self.assertFalse(ok)
        self.assertIn('stale_or_invalid_position_timestamp',reasons)
        # Whole-track timing validation now rejects before interpolation.
        self.assertNotIn('sample_support',diagnostics)

    def test_repeated_raw_position_is_rejected(self):
        p,raw=straight()
        raw[30,1:3]=raw[29,1:3]
        self.assertIn('repeated_raw_horizontal_position',v.vectoring_eligibility(p,raw)[1])

    def test_zero_tangent_never_creates_zero_offset(self):
        p,_=straight()
        p[69:72]=p[70]
        with self.assertRaisesRegex(v.VectoringRejected,'zero_tangent'):
            v.add_vectoring(p,1)

    @patch.object(path, 'PEAK', 5000.)  # Historical 5 km fixture; production remains 15 km.
    def test_fixed_peak_and_diagnostics(self):
        p,raw=straight()
        diagnostic={}
        self.assertFalse(v.vectoring_eligibility(p,raw,diagnostics=diagnostic)[0])
        t=np.arange(0,701,10.);grid=np.arange(45,656,5.)
        ref=path.make_reference(np.c_[200*t,np.zeros(len(t))],t,np.full(len(t),3.),grid,p[9:132,:2])
        frame={'reference':ref,'source_trajectory':p.copy()}
        for side in (-1,1):
            q,start,end=v.add_vectoring(p,side,frame=frame)
            self.assertAlmostEqual(np.linalg.norm(q[start+60,:2]-p[start+60,:2]),5000.,places=2)
            np.testing.assert_allclose(q[[start,end-1]],p[[start,end-1]],atol=1e-9)
        json.dumps(diagnostic,allow_nan=False)

    def test_longitudinal_acceleration_is_not_lateral(self):
        t=np.arange(10)*5.
        p=np.column_stack((100*t+t*t,np.zeros(10),np.zeros(10)))
        d=v.kinematic_diagnostics(p)
        self.assertAlmostEqual(d['maximum_abs_longitudinal_acceleration_m_s2']['value'],2.)
        self.assertAlmostEqual(d['maximum_lateral_acceleration_m_s2']['value'],0.)

    def test_midpoint_velocity_cancellation_is_undefined(self):
        p=np.array([[0,0,0],[100,0,0],[0,0,0]],dtype=float)
        d=v.kinematic_diagnostics(p)
        self.assertIsNone(d['maximum_lateral_acceleration_m_s2'])
        self.assertEqual(d['undefined_acceleration_direction_samples'],[1])

    def test_known_circle_collapse_rejected(self):
        angle=np.arange(121)*5*200/5000
        p=np.column_stack((5000*np.cos(angle),5000*np.sin(angle),np.zeros(121)))
        with self.assertRaises(v.VectoringRejected):
            v.add_vectoring(p,1,frame={'normals':np.column_stack((-np.cos(angle),-np.sin(angle))),'curvature_intervals':np.tile([1/5000,1/5000],(121,1))})

    def test_approved_policy_still_requires_geometry_frame(self):
        self.assertEqual(v.require_confirmed_vectoring_policy(),'approved-2026-10-22')
        p,_=straight()
        with self.assertRaisesRegex(v.VectoringRejected,'missing_approved_geometry_frame'):
            v.add_vectoring(p,1)

    def test_duplicate_time_keeps_matching_metadata(self):
        # Isolate the reader to avoid loading torch or requiring private paths.
        source=(EVALUATION_ROOT/'holding/code/run_holding_eval.py').read_text(encoding='utf8')
        node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='read_scene')
        import math
        ns=dict(np=np,math=math,io=io,csv=csv,gzip=gzip,MIN_RAW=16,MAX_GAP_S=20,SAMPLE_S=10,
                quality_reasons=lambda *a,**kw:[],position_grid=position_grid,resample_positions=resample_positions,
                llh_to_enu=lambda lat,lon,alt:np.column_stack((lat,lon,alt)))
        exec(compile(ast.Module(body=[node],type_ignores=[]),'reader','exec'),ns)
        rows=['time,lat,lon,geoaltitude,lastposupdate,icao24,onground,baroaltitude']
        for i in range(32):
            rows.append(f'{10*i},1,{100+i},1000,{10*i},abc,false,900')
            if i==5: rows.append('50,9,999,1000,45,abc,false,900')
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w') as z:
            z.writestr('scene.csv.gz',gzip.compress(('\n'.join(rows)).encode()))
        payload.seek(0)
        metadata={}
        with zipfile.ZipFile(payload) as z:
            tracks=ns['read_scene'](z,'scene.csv.gz',vectoring_source=metadata)
        self.assertEqual(metadata['abc'][5,4],50.)
        self.assertEqual(metadata['abc'][5,2],105.)
        self.assertEqual(tracks['abc'][5,1],105.)
        self.assertEqual(tracks['abc'][5,2],900.)


if __name__=='__main__': unittest.main()
