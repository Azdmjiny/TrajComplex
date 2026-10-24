"""Saved-record integration checks; no inference, generation or D estimation."""
import ast,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from evaluation_runtime import RUNS
import postprocess_results as pp
from build_report import build_report

class PostprocessingTests(unittest.TestCase):
    def test_holding_exact_published_products(self):
        root=RUNS/'holding-equal-duration'
        for name,actual in pp.holding_summaries(root).items():
            self.assertEqual(actual,pp.read(root/'results'/name),name)

    def test_vectoring_exact_published_products(self):
        root=RUNS/'four-scene-vectoring-evaluation'
        for name,actual in pp.vectoring_summaries(root).items():
            self.assertEqual(actual,pp.read(root/'results'/name),name)

    def test_standalone_pipeline_preserves_inputs_and_refuses_overwrite(self):
        for kind,package in [('holding','holding-equal-duration'),('vectoring','four-scene-vectoring-evaluation')]:
            source=RUNS/package
            with tempfile.TemporaryDirectory(dir=RUNS.parent) as folder:
                output=Path(folder)
                pp.process(kind,source,output)
                self.assertEqual((source/'results/experiment-results.json').read_bytes(),(output/'results/experiment-results.json').read_bytes())
                self.assertTrue((output/'report.md').is_file())
                self.assertEqual(pp.read(output/'postprocessing-manifest.json')['D_estimation'],0)
                if kind=='holding': self.assertEqual(pp.holding_summaries(output)['summary.json'],pp.read(output/'results/summary.json'))
                else: self.assertEqual(len(list((output/'results').glob('*-embeddings.npz'))),len(list((source/'results').glob('*-embeddings.npz'))))
                with self.assertRaises(FileExistsError):pp.process(kind,source,output)
            with self.assertRaises(ValueError):pp.process(kind,source,source)

    def test_report_counts_are_data_driven(self):
        def altered(path):
            result=pp.read(path)
            if Path(path).name=='scene-summary.json':
                return [dict(eligible=2,valid_D=1,positive=1,negative=0)]
            if 'vectoring-fixed-baseline-scales' in str(path):
                result['curves']=result['curves'][:1]
                result['curves'][0]['fixed_correlation'].update(total=7,valid=6)
            return result
        with tempfile.TemporaryDirectory(dir=RUNS.parent) as folder:
            with patch('build_report.read',side_effect=altered):build_report(RUNS,Path(folder))
            text=(Path(folder)/'report.md').read_text()
            self.assertIn('2 accepted candidates across 1 scenes',text)
            self.assertIn('0 scenes have no accepted D',text)
            self.assertIn('6/7',text)
            self.assertNotIn('21 accepted candidates',text)

    def test_inference_entrypoints_invoke_postprocessing(self):
        code=Path(__file__).parent
        for name,kind in [('evaluate_holding_control.py','holding'),('evaluate_saved_vectoring.py','vectoring')]:
            tree=ast.parse((code/name).read_text())
            calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='process']
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0].args[0].value,kind)

if __name__=='__main__':unittest.main()
