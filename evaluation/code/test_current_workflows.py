"""Software regressions using fixtures/saved results, not new evaluation arms."""
import json,tempfile,unittest
from pathlib import Path
import numpy as np
from evaluation_runtime import RUNS,new_output,checked_encoder
import run_holding_eval as h
from complexity.calculator import ComplexityConfig
from diagnose_fixed_scales import fixed_estimate,SCENE
from truncation import curve_correlation

class CurrentWorkflowTests(unittest.TestCase):
    def test_new_output_rejects_published_results_and_existing_directory(self):
        with self.assertRaises(ValueError):new_output(RUNS/'test-overwrite')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileExistsError):new_output(folder)

    def test_wrong_checkpoint_rejected_before_loading_model(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'wrong.pt';p.write_bytes(b'not the frozen model')
            with self.assertRaisesRegex(ValueError,'strict-10-second'):checked_encoder(p)

    def test_matched_terminal_append_and_undefined_direction_rejection(self):
        p=np.c_[np.arange(80)*2000.,np.zeros(80),np.full(80,1500.)]
        hold,straight,detail=h.append_equal_duration_pair(p)
        self.assertEqual(h.SAMPLE_S,10);self.assertEqual(len(hold),104);self.assertEqual(len(straight),104)
        np.testing.assert_array_equal(hold[:80],p);np.testing.assert_array_equal(straight[:80],p)
        np.testing.assert_array_equal(hold[-1],p[-1]);self.assertEqual(detail['added_duration_s'],240)
        np.testing.assert_allclose(straight[-1,:2]-p[-1,:2],[48000,0])
        p[-1]=p[-2]
        with self.assertRaisesRegex(ValueError,'undefined_endpoint_heading'):h.append_equal_duration_pair(p)

    def test_saved_fixed_scale_diagnostic_not_dynamic_rescue(self):
        root=RUNS/'four-scene-vectoring-evaluation'
        trials=json.loads((root/'results/experiment-results.json').read_text())['qc500_safe']['vectoring']['scenes']
        trials=[t for t in trials if t['scene_id']==SCENE]
        expected=json.loads((RUNS/'vectoring-fixed-baseline-scales/results/fixed-dose-curves.json').read_text())
        cfg=ComplexityConfig(normalize=False)
        with np.load(root/'results'/(SCENE+'-embeddings.npz')) as z:
            indices=np.array(trials[0]['dose_curve'][0]['fit_indices'])
            for t,e in zip(trials,expected):
                current=z['baseline'].copy();curve=[]
                for dose in range(6):
                    if dose:
                        a=t['assignments'][dose-1];current[a['baseline_index']]=z['left' if a['side']<0 else 'right'][a['baseline_index']]
                    result=fixed_estimate(current,z['radii'],indices,cfg)
                    self.assertEqual(result,{k:v for k,v in e['dose_curve'][dose].items() if k!='vectoring_aircraft'})
                    curve.append(dict(vectoring_aircraft=dose,**result))
                if t['replicate']==3:self.assertAlmostEqual(curve_correlation(curve,'vectoring_aircraft')['rho'],-.3188740696088466)
                if t['replicate']==4:self.assertEqual(sum(p['status']=='ok' for p in curve),3)

if __name__=='__main__':unittest.main()
