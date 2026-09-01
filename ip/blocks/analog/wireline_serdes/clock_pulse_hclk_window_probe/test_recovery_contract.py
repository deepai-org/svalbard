#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

import compile_recovery_physical_source as compile_recovery
import localize_recovery_pex as recovery_localizer
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

    def test_bounded_recovery_revisions_are_explicit(self) -> None:
        balanced = compile_recovery.compile_source("balanced_event")
        compact = compile_recovery.compile_source("compact_taper")
        combined = compile_recovery.compile_source("balanced_compact")
        self.assertIn("XSTR1 STR0 START VDD VSS cp_inv WP=8u WN=6u MP=6 MN=4",
                      balanced)
        self.assertIn("XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=6 MN=4",
                      combined)
        self.assertIn("XWB4 WB2 WRITE VDD VSS cp_final_inv", compact)
        self.assertNotIn("XWB3 ", compact)
        self.assertIn("XWB3 ", compile_recovery.compile_source("retained"))
        isolated = compile_recovery.compile_source("isolated_event")
        self.assertIn("XSTR1 STR0 START_RAW", isolated)
        self.assertIn("XSR3 STARTB START", isolated)
        self.assertIn("XER1 ER0 END_RAW", isolated)
        self.assertIn("XER3 ENDB END", isolated)
        split = compile_recovery.compile_source("split_final_drive")
        self.assertIn("XSTR1 STR0 START VDD VSS cp_inv WP=1.7u WN=1.275u MP=4 MN=3",
                      split)
        self.assertIn("XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=6 MN=4",
                      split)

    def test_pex_internal_probes_are_explicit_and_diagnostic(self) -> None:
        environment = recovery.base.CONTRACT["environments"][0]
        deck = recovery.compile_deck(
            Path("/work/recovery.pex.spice"), "recovery_dual_control_pulse_pex",
            environment, recovery.CONTROLS[0], internal_probes=True)
        self.assertIn("v(xdut.DBG_E_HSN)", deck)
        self.assertIn("v(xdut.DBG_O_SB1)", deck)
        self.assertIn("v(xdut.DBG_EW_HBASE)", deck)
        self.assertIn("v(xdut.DBG_OW_WB4)", deck)
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
        diagnostic = recovery.stage_diagnostics(
            observed, "e", 3.3, 0.25, recovery.CONTROLS[0])
        self.assertEqual(
            diagnostic["paths"]["sense"]["first_failed_stage"], "sb0")
        self.assertEqual(
            diagnostic["paths"]["sense"]["first_failed_transition_stage"],
            "sb0")
        self.assertEqual(
            diagnostic["paths"]["sense"]["first_failed_rail_stage"], "sb0")
        self.assertEqual(
            diagnostic["paths"]["boost"]["first_failed_stage"], "sb0")
        self.assertEqual(
            diagnostic["paths"]["boost"]["first_failed_transition_stage"],
            "sb0")
        self.assertEqual(
            diagnostic["paths"]["boost"]["first_failed_rail_stage"], "sb0")
        self.assertTrue(diagnostic["paths"]["write_end0"]["active"])
        self.assertFalse(diagnostic["paths"]["write_end1"]["active"])
        self.assertIsNone(
            diagnostic["paths"]["write_end1"]["first_failed_rail_stage"])

    def test_base_selector_gate_has_robust_metal2_clearance(self) -> None:
        device = layout.Device(
            "XE__XWRITE__XBTG1__XP", "XE__XWRITE__XBTG1", "E",
            "pfet_03v3", ("D", "G", "S", "VDD"), 8.0, 1)
        self.assertGreaterEqual(layout.gate_extra(device), 0.84)

    def test_semantic_counterfactual_groups_use_extracted_write_labels(self) -> None:
        source = ("Cepoch DBG_EW_HBASE 0 1f\n"
                  "Ctaper DBG_EW_WB4 0 2f\n"
                  "Repoch DBG_EW_HBASE DBG_EW_HEPOCH 10\n")
        variants = recovery_localizer.variants(source)
        self.assertEqual(variants["baseline"], variants["baseline_repeat"])
        self.assertNotIn("Cepoch", variants["c_removed_epoch"])
        self.assertIn("Ctaper", variants["c_removed_epoch"])
        self.assertIn("DBG_EW_HBASE DBG_EW_HEPOCH 1m",
                      variants["r_near_zero_epoch"])
        self.assertIn("DBG_OW_WB4", recovery_localizer.WRITE_TAPER)

if __name__ == "__main__":
    unittest.main()
