#!/usr/bin/env python3
import re
import unittest

import compile_event_capture_integrated_state as integrated
import compile_event_capture_source as selected


class IntegratedEventStateTest(unittest.TestCase):
    def test_candidate_is_isolated_from_selected_source(self) -> None:
        selected_source = selected.compile_source()
        candidate = integrated.compile_source()
        self.assertNotEqual(candidate, selected_source)
        self.assertNotIn("cp_capture_event_state", selected_source)
        self.assertNotIn("XSTATE", selected_source)

    def test_storage_node_drives_only_one_small_local_gate(self) -> None:
        source = integrated.compile_source()
        estate_gate_loads = re.findall(r"^X\S+\s+ESTATE\s+", source,
                                       flags=re.MULTILINE)
        self.assertEqual(len(estate_gate_loads), 1)
        self.assertIn("XSTATE HSN HCLK ESTATE VDD VSS cp_capture_event_state "
                      "WP=8u WN=4u MP=4 MN=1", source)
        self.assertIn("XN Q RESET VSS VSS", source)
        self.assertNotIn("XSB1 HSN SB1", source)
        self.assertNotIn("XRB2 SB1 BOOST", source)

    def test_outputs_split_after_geometric_shared_taper(self) -> None:
        source = integrated.compile_source()
        self.assertIn("XLS3 SIB SDRV VDD VSS cp_inv WP=8u WN=8u MP=20 MN=16", source)
        self.assertIn("XSB2 SDRV SSEL SENSE", source)
        self.assertIn("XLB2 LSTATE BOOST VDD VSS cp_inv WP=8u WN=8u MP=7 MN=8", source)
        self.assertIn("XLC0 ESTATE LC0B VDD VSS cp_inv WP=4u WN=2u MP=4 MN=4", source)
        self.assertIn("XLC1 LC0B LC1 VDD VSS cp_inv WP=6u WN=3u MP=6 MN=6", source)
        self.assertIn("XLC2 LC1 LC2B VDD VSS cp_inv WP=8u WN=4u MP=8 MN=8", source)
        self.assertIn("XLC3 LC2B LSTATE VDD VSS cp_inv WP=8u WN=4u MP=16 MN=16", source)
        self.assertNotIn("XLB0", source)
        self.assertNotIn("XLS0", source)
        self.assertIn("PMP=24 BASE_MN=5 EXTRA_W=8u EXTRA_M=4", source)


if __name__ == "__main__":
    unittest.main()
