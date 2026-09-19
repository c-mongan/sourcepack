import unittest
from sourcelens.visuals import select_frames,overview_times
from sourcelens.contracts import ContractError

class VisualTests(unittest.TestCase):
 def test_requested_static_change_is_not_deduped(self):
  candidates=[{'source_pts_ms':x,'reason':'overview','fingerprint':'same'} for x in [0,5000,5100,10000]]
  out=select_frames(candidates,10001,[5100],3)
  self.assertIn(5100,[x['source_pts_ms'] for x in out])
  self.assertIn(10000,[x['source_pts_ms'] for x in out])
 def test_overflow_is_explicit(self):
  with self.assertRaises(ContractError):select_frames([],10000,[1,2],1)
 def test_overview_covers_ending_and_offsets(self):
  times=overview_times(20000,12000,6,500)
  self.assertEqual(times[0],20000)
  self.assertEqual(times[-1],31500)
  self.assertEqual(len(times),6)
