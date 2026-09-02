#!/usr/bin/env python3

import unittest

import compile_event_capture_direct_write_sr_source as compiler


class DirectWriteSrSourceTest(unittest.TestCase):
    def test_full_duty_inputs_write_local_state_nodes(self) -> None:
        source = compiler.compile_source(1, 4, screening_top=True)
        self.assertIn("XSET QB STARTB END VSS cp_cond_npd_comp", source)
        self.assertIn("XRESET Q START ENDB VSS cp_cond_npd_comp", source)
        self.assertIn("XQ QB Q VDD VSS cp_inv", source)
        self.assertIn("XQB Q QB VDD VSS cp_inv", source)
        self.assertNotIn("SETB", source)
        self.assertNotIn("RESETB", source)
        self.assertIn("XO0 QB O0", source)
        self.assertIn("XO1 O0 SENSE", source)
        self.assertNotIn("XO2", source)
        self.assertIn(".subckt retimed_event_capture_bridge_pex ", source)

    def test_candidate_bounds_are_explicit(self) -> None:
        for args in ((3, 4), (1, 3)):
            with self.assertRaises(ValueError):
                compiler.compile_source(*args)
        with self.assertRaises(ValueError):
            compiler.compile_source(1, 4, latch_p_width_um=6)

    def test_latch_pmos_skew_is_explicit(self) -> None:
        source = compiler.compile_source(2, 8, latch_p_width_um=8)
        self.assertIn("XQ QB Q VDD VSS cp_inv WP=8u WN=4u MP=2 MN=2", source)


if __name__ == "__main__":
    unittest.main()
