#!/usr/bin/env python3
import unittest

import compile_event_capture_dynamic_state as compiler


class DynamicEventStateTest(unittest.TestCase):
    def test_state_uses_separate_set_and_reset_devices(self) -> None:
        source = compiler.compile_source()
        self.assertIn(".subckt cp_dynamic_event_state SETB RESET Q VDD VSS", source)
        self.assertIn("XP Q SETB VDD VDD pfet_03v3", source)
        self.assertIn("XN Q RESET VSS VSS nfet_03v3", source)
        self.assertIn("XSB1 HSN HCLK SB1 VDD VSS cp_dynamic_event_state", source)
        self.assertNotIn("XSB1 HSN SB1 VDD VSS cp_inv", source)
        self.assertEqual(source.count("cp_dynamic_event_state WP="), 1)

    def test_selected_source_remains_unchanged(self) -> None:
        self.assertIn("XSB1 HSN SB1 VDD VSS cp_inv",
                      compiler.selected.compile_source())


if __name__ == "__main__":
    unittest.main()
