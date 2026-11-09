"""Run: python -m unittest discover -s complexity/tests -v."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from complexity import ComplexityConfig, correlation_integral, estimate_complexity


class CorrelationTests(unittest.TestCase):
    def test_strict_boundary_and_no_self_pairs(self):
        points = [[0.0], [1.0], [3.0]]  # unordered distances: 1, 2, 3
        np.testing.assert_allclose(
            correlation_integral(points, [0.5, 1, 2, 3, 4]),
            [0, 0, 1 / 3, 2 / 3, 1],
        )

    def test_against_brute_force(self):
        points = np.random.default_rng(3).normal(size=(40, 8))
        radii = np.geomspace(0.1, 10, 30)
        distances = [np.linalg.norm(points[i] - points[j])
                     for i in range(40) for j in range(i + 1, 40)]
        expected = [np.mean(np.array(distances) < r) for r in radii]
        np.testing.assert_array_equal(correlation_integral(points, radii), expected)

    def test_duplicates_retained(self):
        np.testing.assert_allclose(correlation_integral([[0], [0], [2]], [0.1, 2, 3]),
                                   [1 / 3, 1 / 3, 1])

    def test_normalization_and_no_mutation(self):
        points = np.array([[3., 0.], [0., 4.], [-5., 0.]])
        original = points.copy()
        radii = [0.5, 1.5, 2.1]
        expected = correlation_integral([[1., 0.], [0., 1.], [-1., 0.]], radii)
        np.testing.assert_allclose(correlation_integral(points, radii, normalize=True), expected)
        np.testing.assert_array_equal(points, original)
        for scale in [1e-250, 1e250]:
            np.testing.assert_allclose(correlation_integral(points * scale, radii, normalize=True), expected)

    def test_invalid_input(self):
        bad = [np.ones(4), np.ones((3, 2, 4)), np.empty((2, 0)),
               [[np.nan], [1]], [[np.inf], [1]], [[1j], [2j]], [["x"], ["y"]]]
        for points in bad:
            with self.subTest(points=points), self.assertRaises(ValueError):
                estimate_complexity(points)
        with self.assertRaises(ValueError):
            correlation_integral([[0, 0], [1, 1]], [1], normalize=True)
        with self.assertRaises(ValueError):
            correlation_integral([[0]], [1])

    def test_invalid_scales_and_limits(self):
        for radii in [[], [0], [-1, 1], [1, 1], [2, 1], [np.inf], [[1]], [1j]]:
            with self.subTest(radii=radii), self.assertRaises(ValueError):
                correlation_integral([[0], [1]], radii)
        with self.assertRaisesRegex(ValueError, "max_pairs"):
            correlation_integral([[0], [1], [2]], [1], max_pairs=2)
        with self.assertRaises(ValueError):
            correlation_integral([[0], [1]], [1], max_pairs=1.5)
        with self.assertRaisesRegex(ValueError, "overflow"):
            correlation_integral([[1e308], [-1e308]], [1])


class EstimationTests(unittest.TestCase):
    def setUp(self):
        self.line = np.linspace(0, 1, 1000)[:, None]

    def test_line_dimension(self):
        result = estimate_complexity(self.line, scene_id="hour_01")
        self.assertEqual(result.status, "ok", result.reason)
        self.assertAlmostEqual(result.dimension, 1, delta=0.08)
        self.assertGreater(result.r_squared, 0.99)
        self.assertEqual(result.scene_id, "hour_01")
        self.assertEqual(result.n_pairs, 499500)
        self.assertTrue(np.all(np.diff(result.correlation) >= 0))
        json.dumps(result.to_dict(), allow_nan=False)

    def test_plane_dimension_in_higher_embedding_space(self):
        xy = np.random.default_rng(42).uniform(size=(1500, 2))
        points = np.pad(xy, ((0, 0), (0, 14)))
        result = estimate_complexity(points)
        self.assertEqual(result.status, "ok", result.reason)
        self.assertAlmostEqual(result.dimension, 2, delta=0.3)
        self.assertEqual(result.embedding_dim, 16)

    def test_explicit_range_and_fit_against_numpy(self):
        radii = np.geomspace(0.005, 0.2, 40)
        result = estimate_complexity(self.line, radii=radii, fit_range=(0.01, 0.1))
        self.assertEqual(result.status, "ok", result.reason)
        idx = result.fit_indices
        expected = np.polyfit(np.log(radii[idx]), np.log(np.array(result.correlation)[idx]), 1)
        np.testing.assert_allclose([result.dimension, result.intercept], expected)
        self.assertEqual(result.selection, "explicit_radius_range")
        self.assertEqual(result.requested_fit_range, (0.01, 0.1))
        self.assertGreaterEqual(result.fit_radius_range[0], 0.01)
        self.assertLessEqual(result.fit_radius_range[1], 0.1)

    def test_translation_scaling_and_permutation_invariance(self):
        result = estimate_complexity(self.line)
        for points in [self.line + 5, self.line * 20, self.line[::-1]]:
            other = estimate_complexity(points)
            self.assertEqual(other.status, "ok", other.reason)
            self.assertAlmostEqual(other.dimension, result.dimension, delta=0.005)

    def test_auto_selection_uses_all_eligible_scales(self):
        result = estimate_complexity(self.line)
        cfg = ComplexityConfig()
        c = np.array(result.correlation)
        counts = np.array(result.pair_counts)
        expected = np.flatnonzero((c >= 0.02) & (c <= 0.3) & (counts >= cfg.min_pairs))
        self.assertEqual(result.fit_indices, expected.tolist())

    def test_insufficient_and_collapsed_scenes(self):
        for n in [0, 1, 29]:
            result = estimate_complexity(np.zeros((n, 8)))
            self.assertEqual(result.reason, "insufficient_samples")
            self.assertIsNone(result.zero_distance_pairs)
            self.assertIsNone(result.dimension)
            json.dumps(result.to_dict(), allow_nan=False)
        result = estimate_complexity(np.ones((40, 8)))
        self.assertEqual(result.reason, "collapsed_point_cloud")
        self.assertEqual(result.n_unique, 1)
        self.assertEqual(result.zero_distance_pairs, 780)
        self.assertTrue(result.warnings)
        self.assertIsNone(result.dimension)

    def test_quality_rejections(self):
        poor = estimate_complexity(self.line, config=ComplexityConfig(min_r_squared=1.0))
        self.assertEqual(poor.reason, "poor_linear_fit")
        self.assertIsNone(poor.dimension)
        self.assertIsNotNone(poor.fit_slope)
        few = estimate_complexity(self.line, radii=[0.01, 0.02, 0.05])
        self.assertEqual(few.reason, "insufficient_fit_scales")
        narrow = estimate_complexity(self.line, fit_range=(0.02, 0.025))
        self.assertEqual(narrow.reason, "insufficient_scale_span")
        saturated = estimate_complexity(self.line, radii=np.geomspace(2, 20, 20))
        self.assertEqual(saturated.reason, "insufficient_fit_scales")

    def test_flat_curve(self):
        points = np.repeat([[0.], [100.]], 20, axis=0)
        result = estimate_complexity(points, fit_range=(1, 10))
        self.assertEqual(result.reason, "flat_correlation_curve")
        self.assertIsNone(result.dimension)

    def test_pair_limit(self):
        with self.assertRaisesRegex(ValueError, "max_pairs"):
            estimate_complexity(self.line, config=ComplexityConfig(max_pairs=100))

    def test_numpy_integer_config_serialization(self):
        cfg = ComplexityConfig(n_radii=np.int64(64), min_samples=np.int64(30))
        result = estimate_complexity(self.line, config=cfg)
        json.dumps(result.to_dict(), allow_nan=False)
        self.assertEqual(result.status, "ok")

    def test_config_and_fit_validation(self):
        for kwargs in [{"min_samples": 1}, {"n_radii": 2}, {"min_fit_points": 2},
                       {"min_pairs": 0}, {"min_radius_ratio": 1}, {"normalize": "yes"},
                       {"min_r_squared": 1.1}, {"max_pairs": -1}, {"n_radii": 4.2},
                       {"correlation_bounds": (0.3, 0.02)}, {"min_r_squared": np.nan}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ComplexityConfig(**kwargs)
        for bounds in [(1,), (2, 1), (1, 2, 3), (0, 1)]:
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                estimate_complexity(self.line, fit_range=bounds)


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("PI_SCRATCH_DIR"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = Path(__file__).resolve().parents[2]

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "complexity", *map(str, args)],
                              cwd=self.project, capture_output=True, text=True)

    def test_single_scene(self):
        source, output = self.root / "hour.npy", self.root / "result.json"
        np.save(source, np.linspace(0, 1, 1000)[:, None])
        proc = self.run_cli(source, "-o", output)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(output.read_text())
        self.assertEqual(payload["results"][0]["scene_id"], "hour")
        self.assertEqual(payload["results"][0]["status"], "ok")
        self.assertEqual(payload["metric"], "euclidean")

    def test_multiple_scenes_stdout(self):
        source = self.root / "hours.npz"
        np.savez(source, hour_01=np.linspace(0, 1, 1000)[:, None], hour_02=np.zeros((2, 8)))
        proc = self.run_cli(source)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        results = json.loads(proc.stdout)["results"]
        self.assertEqual([r["scene_id"] for r in results], ["hour_01", "hour_02"])
        self.assertEqual(results[1]["reason"], "insufficient_samples")
        self.assertIsNone(results[1]["dimension"])

    def test_invalid_file_and_no_input_overwrite(self):
        source = self.root / "bad.npy"
        np.save(source, np.array([[np.nan]]))
        original = source.read_bytes()
        proc = self.run_cli(source, "-o", source)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(source.read_bytes(), original)
        proc = self.run_cli(source)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("finite", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        proc = self.run_cli(self.root / "missing.npy")
        self.assertEqual(proc.returncode, 2)

    def test_object_array_and_empty_archive_rejected(self):
        source = self.root / "object.npy"
        np.save(source, np.array([{"x": 1}], dtype=object))
        self.assertEqual(self.run_cli(source).returncode, 2)
        empty = self.root / "empty.npz"
        np.savez(empty)
        self.assertEqual(self.run_cli(empty).returncode, 2)


if __name__ == "__main__":
    unittest.main()
