#!/usr/bin/env python3

import unittest

import compile_event_capture_state_free_sr_source as compiler


class StartEndSrSourceTest(unittest.TestCase):
    def test_independent_set_reset_events_replace_contention_driver(self) -> None:
        source = compiler.compile_source(2, 4, 8, screening_top=True)
        self.assertIn("XSETB STARTB END SETB", source)
        self.assertIn("XRESETB START ENDB RESETB", source)
        self.assertIn("XQ RESETB QB Q", source)
        self.assertIn("XQB SETB Q QB", source)
        self.assertIn("XO0 QB O0 VDD VSS cp_inv WP=4u WN=2u MP=1 MN=1", source)
        self.assertIn("XO3 O2 SENSE", source)
        self.assertIn("XSENSESR START END SENSE", source)
        self.assertIn("XSRSELLOAD SSEL SRSEL_UNUSED", source)
        self.assertNotIn("XSENSE SFDRV SSEL SENSE", source)
        self.assertIn(".subckt retimed_event_capture_bridge_pex ", source)

    def test_candidate_bounds_are_explicit(self) -> None:
        with self.assertRaises(ValueError):
            compiler.compile_source(3, 4, 8)
        with self.assertRaises(ValueError):
            compiler.compile_source(2, 3, 8)
        with self.assertRaises(ValueError):
            compiler.compile_source(2, 4, 10)
        with self.assertRaises(ValueError):
            compiler.compile_source(2, 4, 8, set_mult=4)

    def test_set_strength_is_a_bounded_circuit_identity(self) -> None:
        baseline = compiler.compile_source(2, 4, 8, set_mult=2)
        strong = compiler.compile_source(2, 4, 8, set_mult=8)
        self.assertIn("XSETB STARTB END SETB VDD VSS cp_nand2_comp WP=4u WN=4u MP=2 MN=2", baseline)
        self.assertIn("XSETB STARTB END SETB VDD VSS cp_nand2_comp WP=4u WN=4u MP=2 MN=8", strong)


if __name__ == "__main__":
    unittest.main()
