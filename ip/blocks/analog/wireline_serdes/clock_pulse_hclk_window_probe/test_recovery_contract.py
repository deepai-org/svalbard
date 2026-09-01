#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

import compile_recovery_physical_source as compile_recovery
import run_recovery_schematic as recovery

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clock_pulse"))
import generate_pulse_layout as layout  # noqa: E402


class RecoveryContractTest(unittest.TestCase):
    def test_controls_are_structurally_independent(self) -> None:
        source = compile_recovery.compile_source()
        self.assertIn("XSB2 SB1 SSEL SENSE", source)
        self.assertIn("XWRITE HCLK WSEL ESEL", source)
        self.assertIn("XSB1 SB0 SB1 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=4", source)
        self.assertIn("cp_sense_final_select PMP=12 BASE_MN=4", source)
        self.assertIn("XRB2 SB1 BOOST", source)
        self.assertNotIn("XRB0 ", source)

    def test_full_control_cube_and_exact_top(self) -> None:
        self.assertEqual(len(recovery.CONTROLS), 8)
        self.assertEqual(len({c["id"] for c in recovery.CONTROLS}), 8)
        deck = recovery.compile_deck(
            Path("/work/recovery.spice"), "recovery_dual_control_pulse",
            recovery.base.CONTRACT["environments"][0],
            recovery.CONTROLS[0])
        self.assertIn("VSEL2 SEL2", deck)
        self.assertIn("recovery_dual_control_pulse", deck)

    def test_pex_internal_probes_are_explicit_and_diagnostic(self) -> None:
        environment = recovery.base.CONTRACT["environments"][0]
        deck = recovery.compile_deck(
            Path("/work/recovery.pex.spice"), "recovery_dual_control_pulse_pex",
            environment, recovery.CONTROLS[0], internal_probes=True)
        self.assertIn("v(xdut.DBG_E_HSN)", deck)
        self.assertIn("v(xdut.DBG_O_SB1)", deck)
        self.assertNotIn("DBG_E_RB0", deck)
        observed = {
            "e_dbg_hsn_high": 3.3, "e_dbg_hsn_low": 0.0,
            "e_dbg_sb0_high": 3.3, "e_dbg_sb0_low": 2.0,
            "e_dbg_sb1_high": 2.0, "e_dbg_sb1_low": 0.0,
            "e_dbg_rb0_high": 2.0, "e_dbg_rb0_low": 0.0,
            "e_sense_high": 2.0, "e_sense_low": 0.0,
            "e_boost_high": 2.0, "e_boost_low": 0.0,
            "e_write_high": 3.3, "e_write_low": 0.0,
        }
        diagnostic = recovery.stage_diagnostics(observed, "e", 3.3, 0.25)
        self.assertEqual(
            diagnostic["paths"]["sense"]["first_failed_stage"], "sb0")
        self.assertEqual(
            diagnostic["paths"]["boost"]["first_failed_stage"], "sb0")

    def test_base_selector_gate_has_robust_metal2_clearance(self) -> None:
        device = layout.Device(
            "XE__XWRITE__XBTG1__XP", "XE__XWRITE__XBTG1", "E",
            "pfet_03v3", ("D", "G", "S", "VDD"), 8.0, 1)
        self.assertGreaterEqual(layout.gate_extra(device), 0.84)

if __name__ == "__main__":
    unittest.main()
