import importlib.util
import unittest
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    'injection_runner', Path(__file__).with_name('run_experiment.py')
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
W = M.W


class HoldingTests(unittest.TestCase):
    def setUp(self):
        t = np.arange(100) * 10.0
        self.track = np.column_stack((230 * t, 1500 * np.sin(t / 900), np.full(100, 10000.0)))
        self.before = self.track.copy()
        self.candidate, reason = W.holding_candidate(self.track)
        self.assertIsNone(reason)

    def test_candidate_is_allowed_near_arp(self):
        track = self.track.copy()
        track[:, :2] -= track[len(track) // 2, :2] - np.array([1000.0, 0.0])
        candidate, reason = W.holding_candidate(track)
        self.assertIsNone(reason)
        self.assertLess(candidate['anchor_distance_m'], 40000)

    def test_insertion_and_tail_trim_conserve_length_and_input(self):
        state, removed = W.holding_inject_trim((self.track.copy(), ['original'] * len(self.track)), self.candidate)
        self.assertEqual(len(state[0]), len(self.track))
        self.assertEqual(state[1].count('holding'), 36)
        self.assertEqual(removed, {'original': 36, 'holding': 0})
        np.testing.assert_array_equal(self.track, self.before)

    def test_holding_sequence_never_repeats_aircraft(self):
        candidates = {'a': self.candidate, 'b': self.candidate, 'c': self.candidate}
        selected = W.holding_sequence(candidates, np.random.default_rng(7))
        self.assertEqual(len(selected), len(set(selected)))
        self.assertLessEqual(len(selected), W.EVENT_CAP)

    def test_racetrack_closes_and_has_36_points(self):
        self.assertLess(self.candidate['closure'], 1e-6)
        self.assertEqual(len(self.candidate['block']), 36)


if __name__ == '__main__':
    unittest.main()
