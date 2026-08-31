#!/usr/bin/env python3
import unittest

import compile_selected_physical_source as physical


class CompileSelectedPhysicalSourceTest(unittest.TestCase):
    def test_selected_identity_is_in_current_manifest(self) -> None:
        self.assertIn(physical.SELECTED_WRITE,
                      [candidate["id"] for candidate in physical.compose.WRITE_CANDIDATES])
        self.assertIn(physical.SELECTED_SENSE,
                      [candidate["id"] for candidate in physical.compose.SENSE_CANDIDATES])

    def test_compiled_source_has_exact_top_and_no_placeholders(self) -> None:
        source = physical.compile_source()
        self.assertNotIn("@", source)
        self.assertIn(".subckt selected_dual_control_pulse ", source)
        self.assertIn("XWRITE HCLK SEL ESEL VDD VSS WRITE WPN hclk_select_window", source)
        self.assertIn("XSLOW1 HSM HSLOW VDD VSS cp_delay WP=4u WN=2u MP=4 MN=4", source)
        self.assertIn("PMP=12 BASE_MN=4 EXTRA_W=8u EXTRA_M=4", source)
        self.assertIn("XNE0 Y A EN VSS cp_cond_npd_comp", source)
        self.assertIn("XNE1 Y A EN VSS cp_cond_npd_comp", source)


if __name__ == "__main__":
    unittest.main()
