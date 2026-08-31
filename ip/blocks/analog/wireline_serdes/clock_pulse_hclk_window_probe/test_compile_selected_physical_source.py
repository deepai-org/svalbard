#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

import compile_selected_physical_source as physical

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clock_pulse"))
import generate_pulse_layout as layout  # noqa: E402


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

    def test_physical_lowering_sees_through_write_wrapper(self) -> None:
        self.assertEqual(layout.instance_path("XE__XWRITE__XWB4"), ["XWB4"])
        self.assertEqual(layout.instance_root("XO__XWRITE__XDET__XIY"), "XDET")
        wrapped = layout.Group("XE__XWRITE__XSLOW0__XI0", "cp_inv", "E", {})
        self.assertEqual(layout.functional_lane(wrapped), 3)


if __name__ == "__main__":
    unittest.main()
