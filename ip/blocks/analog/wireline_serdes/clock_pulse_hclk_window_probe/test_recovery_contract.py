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
        retimed = compile_recovery.compile_source("retimed_tap_chain")
        self.assertIn("XTD0 EBASE T0", retimed)
        self.assertIn("XTD2 T1 T2", retimed)
        self.assertIn("XTG0 T1 ENDMUX", retimed)
        self.assertIn("XSR1 SR0 START", retimed)
        self.assertIn("XER1 ER0 END", retimed)
        self.assertNotIn("XEND0 S0A E0", retimed)
        self.assertIn("XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=4 MN=4",
                      compile_recovery.compile_source("retimed_tap_fast2"))
        self.assertIn("XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=8 MN=8",
                      compile_recovery.compile_source("retimed_tap_fast4"))
        self.assertIn("XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=5 MN=5",
                      compile_recovery.compile_source("retimed_tap_m5"))
        self.assertIn("XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=5 MN=4",
                      compile_recovery.compile_source("retimed_tap_p5n4"))
        self.assertIn("XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=4 MN=5",
                      compile_recovery.compile_source("retimed_tap_p4n5"))
        self.assertIn("EXTRA_W=16u EXTRA_M=4",
                      compile_recovery.compile_source("retimed_p5n4_sense2"))
        self.assertIn("EXTRA_W=24u EXTRA_M=4",
                      compile_recovery.compile_source("retimed_p5n4_sense3"))
        isolated_sense = compile_recovery.compile_source(
            "retimed_p5n4_isolated_sense")
        self.assertIn("XTG A XG EN ENB", isolated_sense)
        self.assertIn("XNEX Y XG VSS VSS", isolated_sense)
        self.assertNotIn("XNE0 Y A EN VSS", isolated_sense)
        self.assertIn("EXTRA_W=8u EXTRA_M=8", compile_recovery.compile_source(
            "retimed_p5n4_isolated_sense2"))
        joint = compile_recovery.compile_source("retimed_joint_long")
        self.assertIn("XED1 EDL EDL2", joint)
        self.assertIn("XLN ESEL SEL LONGB", joint)
        self.assertIn("XNN ESEL SELB NORMB", joint)
        self.assertIn("XETG2 EDL2 EMUX LONG LONGB", joint)
        self.assertNotIn("EMUX0", joint)
        self.assertIn("XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=5 MN=4",
                      joint)
        self.assertIn("XED1 EDL EDL2 VDD VSS cp_delay WP=6u WN=3u MP=2 MN=2",
                      compile_recovery.compile_source("retimed_joint_long_6_3"))
        retimed_compact = compile_recovery.compile_source(
            "retimed_joint_long_6_3_compact")
        self.assertIn("XED1 EDL EDL2 VDD VSS cp_delay WP=6u WN=3u MP=2 MN=2",
                      retimed_compact)
        self.assertIn("XWB4 WB2 WRITE VDD VSS cp_final_inv", retimed_compact)
        self.assertNotIn("XWB3 ", retimed_compact)
        retimed_lean = compile_recovery.compile_source(
            "retimed_joint_long_6_3_lean")
        self.assertIn("XWPN WIN WPN VDD VSS cp_inv WP=2u WN=2u MP=2 MN=2",
                      retimed_lean)
        self.assertIn("XWB2 WB2 WB3 VDD VSS cp_inv WP=6u WN=6u MP=4 MN=4",
                      retimed_lean)
        self.assertIn("XWB3 WB3 WB4 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8",
                      retimed_lean)
        retimed_latched = compile_recovery.compile_source(
            "retimed_joint_long_6_3_latched")
        self.assertIn(".subckt cp_output_nor_latch S R Q QB", retimed_latched)
        self.assertIn("XLAT SET RESET WRITE WPN VDD VSS cp_output_nor_latch",
                      retimed_latched)
        self.assertNotIn("XWB4 ", retimed_latched)
        retimed_latched_strong = compile_recovery.compile_source(
            "retimed_joint_long_6_3_latched_strong")
        self.assertIn("XPQ0 PQ R VDD VDD pfet_03v3 w=8u l=0.28u m=112",
                      retimed_latched_strong)
        self.assertIn("XNQ0 Q R VSS VSS nfet_03v3 w=8u l=0.28u m=44",
                      retimed_latched_strong)
        self.assertIn("XPB0 PB S VDD VDD pfet_03v3 w=8u l=0.28u m=28",
                      retimed_latched_strong)

    def test_pex_internal_probes_are_explicit_and_diagnostic(self) -> None:
        environment = recovery.base.CONTRACT["environments"][0]
        deck = recovery.compile_deck(
            Path("/work/recovery.pex.spice"), "recovery_dual_control_pulse_pex",
            environment, recovery.CONTROLS[0], internal_probes=True)
        self.assertIn("v(xdut.DBG_E_HSN)", deck)
        self.assertIn("v(xdut.DBG_O_SB1)", deck)
        self.assertIn("v(xdut.DBG_EW_HBASE)", deck)
        self.assertIn("v(xdut.DBG_OW_WB4)", deck)
        self.assertIn("e_dbg_w_hbase_rise when v(xdut.DBG_EW_HBASE)", deck)
        self.assertIn("o_dbg_w_wb4_fall when v(xdut.DBG_OW_WB4)", deck)
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
