import unittest
import numpy as np
from probe_rail_startup import checkpoint_steps

class CheckpointTests(unittest.TestCase):
    def test_valid_trace(self):
        self.assertAlmostEqual(checkpoint_steps(np.array([[0,3.3],[1e-9,3.3]]),1e-9)['max'],1e-9)
    def test_operating_point_is_not_transient(self):
        with self.assertRaises(ValueError):checkpoint_steps(np.array([[3.3,3.3]]),1e-9)
    def test_wrong_endpoint(self):
        with self.assertRaises(ValueError):checkpoint_steps(np.array([[0,3.3],[2e-9,3.3]]),1e-9)
    def test_invalid_times_and_values(self):
        for values in ([[0,3.3],[0,3.3],[1e-9,3.3]],[[0,3.3],[1e-9,float('nan')]]):
            with self.assertRaises(ValueError):checkpoint_steps(np.array(values),1e-9)

if __name__=='__main__':unittest.main()
