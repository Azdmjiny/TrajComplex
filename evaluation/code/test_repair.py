import ast, sys, unittest, math
from types import SimpleNamespace
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
ns=dict(np=np,math=math,SAMPLE_S=5,TURN_RATE=math.radians(3),LEG_S=60)
node=next(n for n in ast.parse((ROOT/'run_holding_eval.py').read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef) and n.name=='add_racetrack')
exec(compile(ast.Module(body=[node],type_ignores=[]),'holding','exec'),ns)
h=SimpleNamespace(add_racetrack=ns['add_racetrack'])
from trajectory_quality import quality_reasons

class RepairTests(unittest.TestCase):
    def test_closed_constant_speed_holding(self):
        for angle in [0,.7,2.8]:
            direction=np.array([np.cos(angle),np.sin(angle),0])
            p=np.arange(121)[:,None]*1000*direction+np.array([300,500,1000])
            q,s,idx=h.add_racetrack(p)
            self.assertEqual(len(q),len(p)+48)
            np.testing.assert_allclose(q[:idx+1],p[:idx+1])
            np.testing.assert_allclose(q[idx+49:],p[idx+1:])
            np.testing.assert_allclose(q[idx+48],p[idx])
            speeds=np.linalg.norm(np.diff(q[:,:2],axis=0),axis=1)/5
            self.assertLessEqual(speeds.max(),200+1e-8)
            self.assertGreater(speeds.min(),198)
    def test_quality(self):
        a=np.column_stack([np.arange(20)*10,np.ones(20),np.ones(20)*104,np.ones(20)*1000])
        p=np.column_stack([np.arange(20)*2000,np.zeros(20),np.ones(20)*1000])
        self.assertEqual(quality_reasons(a,p),[])
        jump=p.copy();jump[10,0]+=20000
        self.assertIn('horizontal_speed',quality_reasons(a,jump))
        jump=p.copy();jump[10,2]+=2000
        self.assertIn('vertical_speed',quality_reasons(a,jump))
        a[0,1]=91
        self.assertIn('coordinate_range',quality_reasons(a,p))
    def test_vectoring_eligibility(self):
        import run_vectoring_eval as v
        from test_vectoring_repair import straight
        p,raw=straight(121)
        self.assertFalse(v.vectoring_eligible(p,source_observations=raw))
        self.assertEqual(v.vectoring_eligibility(p,raw)[1],['missing_quality_matches'])
        self.assertFalse(v.vectoring_eligible(p[:100],source_observations=raw))
        p[60,0]+=20000
        self.assertFalse(v.vectoring_eligible(p,source_observations=raw))

if __name__=='__main__':unittest.main()
