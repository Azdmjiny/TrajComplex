import importlib.util
import unittest
from pathlib import Path
import numpy as np
SPEC=importlib.util.spec_from_file_location('holding_eval',Path(__file__).with_name('run_holding.py'))
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
class HoldingTests(unittest.TestCase):
 def setUp(self):
  t=np.arange(100)*10.;self.track=np.column_stack((230*t,1500*np.sin(t/900),np.full(100,10000.)));self.before=self.track.copy();self.candidate,_=M.candidate(self.track)
 def test_insertion_and_trim_conserve_length_and_input(self):
  state,removed=M.inject_trim((self.track.copy(),['original']*len(self.track)),self.candidate)
  self.assertEqual(len(state[0]),len(self.track));self.assertEqual(state[1].count('holding'),24);self.assertEqual(removed['original'],24)
  np.testing.assert_array_equal(self.track,self.before)
 def test_repeat_anchor_uses_event_order_and_trims_from_tail(self):
  state,_=M.inject_trim((self.track.copy(),['original']*len(self.track)),self.candidate,prior_events=0)
  state2,_=M.inject_trim(state,self.candidate,prior_events=1)
  i=self.candidate['index']; np.testing.assert_array_equal(state2[0][i+1:i+25],self.candidate['block']); np.testing.assert_array_equal(state2[0][i+25:i+49],self.candidate['block'])
  for _ in range(4): state2,_=M.inject_trim(state2,self.candidate,prior_events=1)
  self.assertEqual(len(state2[0]),len(self.track))
 def test_racetrack_closes_and_repeat_is_a_new_event(self):
  self.assertLess(self.candidate['closure'],1e-6)
  state,_=M.inject_trim((self.track.copy(),['original']*len(self.track)),self.candidate)
  state2,removed2=M.inject_trim(state,self.candidate,prior_events=1)
  self.assertEqual(len(state2[0]),len(self.track));self.assertEqual(state2[1].count('holding'),48)
  self.assertEqual(removed2['original'],24)
  i=self.candidate['index']; np.testing.assert_array_equal(state2[0][i+1:i+25],self.candidate['block']); np.testing.assert_array_equal(state2[0][i+25:i+49],self.candidate['block'])
if __name__=='__main__':unittest.main()
