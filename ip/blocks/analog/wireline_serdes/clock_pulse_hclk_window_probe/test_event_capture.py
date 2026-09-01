#!/usr/bin/env python3
import unittest
from pathlib import Path

import compile_event_capture_source as compiler
import run_event_capture_schematic as runner
import summarize_event_capture_candidates as candidate_summary


class EventCaptureTest(unittest.TestCase):
    def test_candidate_summary_rejects_non_campaign_record(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"result": "pass"}')
            with self.assertRaisesRegex(ValueError, "missing campaign fields"):
                candidate_summary.summarize(path)

    def test_event_source_removes_narrow_write_path(self) -> None:
        source = compiler.compile_source()
        self.assertIn(".subckt retimed_capture_events", source)
        self.assertIn("E_START E_END O_SENSE", source)
        self.assertIn("XWRITE HCLK WSEL ESEL VDD VSS START END", source)
        self.assertIn("XSI0 SB1 SIB VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8", source)
        self.assertIn("XSI1 SIB SDRV VDD VSS cp_inv WP=8u WN=8u MP=12 MN=16", source)
        self.assertIn("XSB2 SDRV SSEL SENSE VDD VSS cp_sense_final_select PMP=12 BASE_MN=4 EXTRA_W=8u EXTRA_M=4", source)
        self.assertEqual(source.count("PMP="), 2)
        self.assertIn("XHSD2 HSD HSDX VDD VSS cp_delay WP=2u WN=1u MP=2 MN=2", source)
        self.assertIn(".subckt cp_fall_nand_bar A B YB VDD VSS", source)
        self.assertIn("XHSN HCLK HSDX HSN VDD VSS cp_fall_nand_bar", source)
        self.assertIn("XSB1 HSN SB1 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=4", source)
        self.assertIn("XRB2 SB1 BOOST VDD VSS cp_inv WP=8u WN=8u MP=5 MN=8", source)
        self.assertNotIn("XSB0 HSN SB0", source)
        self.assertNotIn("XHSD3 ", source)
        self.assertIn("XNE0 Y A EN VSS", source)
        self.assertNotIn("XDET START END WIN", source)
        self.assertNotIn("XWB4 ", source)

    def test_control_cube_and_contract_are_fixed(self) -> None:
        self.assertEqual(len(runner.CONTROLS), 8)
        self.assertEqual(len({item["id"] for item in runner.CONTROLS}), 8)
        self.assertEqual(runner.CONTRACT["source_revision"],
                         compiler.SOURCE_REVISION)
        self.assertEqual(
            runner.INTERNAL_STAGES,
            ("hsdx", "hsn", "sb1", "sib", "sdrv", "start", "startb", "end"),
        )

    def test_combined_pex_deck_has_no_schematic_bridge(self) -> None:
        environment = runner.base.CONTRACT["environments"][0]
        deck = runner.compile_deck(
            Path("combined.pex.spice"), None, Path("capture.pex.spice"),
            environment, runner.CONTROLS[0], combined_pex=True)
        self.assertIn("retimed_event_capture_bridge_pex", deck)
        self.assertNotIn("event_capture_bridge\n", deck)
        self.assertNotIn("E_START", deck)
        self.assertEqual(deck.count("CE_SENSE E_SENSE"), 1)

    def test_combined_pex_internal_probes_are_hierarchical(self) -> None:
        environment = runner.base.CONTRACT["environments"][0]
        deck = runner.compile_deck(
            Path("combined.pex.spice"), None, Path("capture.pex.spice"),
            environment, runner.CONTROLS[0], combined_pex=True,
            internal_probes=True)
        self.assertIn("v(xsource.DBG_E_START)", deck)
        self.assertIn("v(xsource.DBG_O_STARTB)", deck)
        self.assertIn("v(xsource.DBG_E_SDRV)", deck)

    def test_schematic_deck_retains_separate_bridge(self) -> None:
        environment = runner.base.CONTRACT["environments"][0]
        deck = runner.compile_deck(
            Path("source.spice"), Path("bridge.spice"),
            Path("capture.pex.spice"), environment, runner.CONTROLS[0])
        self.assertIn("event_capture_bridge", deck)
        self.assertIn("E_START", deck)
        self.assertEqual(deck.count("CE_SENSE E_SENSE"), 1)

    def test_entry_correction_changes_only_start_pullup_multiplicity(self) -> None:
        root = Path(__file__).resolve().parent
        baseline = (root / "event_capture_bridge.spice").read_text()
        corrected = (root / "event_capture_bridge_slow_entry.spice").read_text()
        baseline = "\n".join(line for line in baseline.splitlines()
                             if line and not line.startswith("*"))
        corrected = "\n".join(line for line in corrected.splitlines()
                              if line and not line.startswith("*"))
        self.assertEqual(baseline.replace("MP=2 MN=2\nXCLKB",
                                          "MP=1 MN=2\nXCLKB", 1),
                         corrected)

    def test_trimmed_entry_changes_only_start_pullup_width(self) -> None:
        root = Path(__file__).resolve().parent
        baseline = (root / "event_capture_bridge.spice").read_text()
        trimmed = (root / "event_capture_bridge_trimmed_entry.spice").read_text()
        baseline = "\n".join(line for line in baseline.splitlines()
                             if line and not line.startswith("*"))
        trimmed = "\n".join(line for line in trimmed.splitlines()
                            if line and not line.startswith("*"))
        self.assertEqual(baseline.replace("XCB0 START STARTB VDD VSS ecb_inv WP=8u",
                                          "XCB0 START STARTB VDD VSS ecb_inv WP=6u"),
                         trimmed)

    def test_balanced_entry_changes_only_final_clk_pulldown(self) -> None:
        root = Path(__file__).resolve().parent
        trimmed = (root / "event_capture_bridge_trimmed_entry.spice").read_text()
        balanced = (root / "event_capture_bridge_balanced_entry.spice").read_text()
        trimmed = "\n".join(line for line in trimmed.splitlines()
                            if line and not line.startswith("*"))
        balanced = "\n".join(line for line in balanced.splitlines()
                             if line and not line.startswith("*"))
        self.assertEqual(trimmed.replace("XCLK ENDR CLK VDD VSS ecb_inv WP=12u WN=5u",
                                         "XCLK ENDR CLK VDD VSS ecb_inv WP=12u WN=7u"),
                         balanced)

    def test_balanced_edges_changes_only_start_pulldown(self) -> None:
        root = Path(__file__).resolve().parent
        trimmed = (root / "event_capture_bridge_trimmed_entry.spice").read_text()
        balanced = (root / "event_capture_bridge_balanced_edges.spice").read_text()
        trimmed = "\n".join(line for line in trimmed.splitlines()
                            if line and not line.startswith("*"))
        balanced = "\n".join(line for line in balanced.splitlines()
                             if line and not line.startswith("*"))
        self.assertEqual(trimmed.replace("XCB0 START STARTB VDD VSS ecb_inv WP=6u WN=4u",
                                         "XCB0 START STARTB VDD VSS ecb_inv WP=6u WN=3u"),
                         balanced)

    def test_five_three_revision_changes_only_start_pullup(self) -> None:
        root = Path(__file__).resolve().parent
        balanced = (root / "event_capture_bridge_balanced_edges.spice").read_text()
        five_three = (root / "event_capture_bridge_balanced_edges_5_3.spice").read_text()
        balanced = "\n".join(line for line in balanced.splitlines()
                             if line and not line.startswith("*"))
        five_three = "\n".join(line for line in five_three.splitlines()
                               if line and not line.startswith("*"))
        self.assertEqual(balanced.replace("XCB0 START STARTB VDD VSS ecb_inv WP=6u",
                                          "XCB0 START STARTB VDD VSS ecb_inv WP=5u"),
                         five_three)

    def test_five_two_point_five_changes_only_start_pulldown(self) -> None:
        root = Path(__file__).resolve().parent
        five_three = (root / "event_capture_bridge_balanced_edges_5_3.spice").read_text()
        candidate = (root / "event_capture_bridge_balanced_edges_5_2p5.spice").read_text()
        five_three = "\n".join(line for line in five_three.splitlines()
                               if line and not line.startswith("*"))
        candidate = "\n".join(line for line in candidate.splitlines()
                              if line and not line.startswith("*"))
        self.assertEqual(five_three.replace("WP=5u WN=3u MP=2 MN=2",
                                            "WP=5u WN=2.5u MP=2 MN=2"),
                         candidate)

    def test_interpolated_revision_changes_only_start_pulldown(self) -> None:
        root = Path(__file__).resolve().parent
        five_three = (root / "event_capture_bridge_balanced_edges_5_3.spice").read_text()
        candidate = (root / "event_capture_bridge_balanced_edges_5_2p75.spice").read_text()
        five_three = "\n".join(line for line in five_three.splitlines()
                               if line and not line.startswith("*"))
        candidate = "\n".join(line for line in candidate.splitlines()
                              if line and not line.startswith("*"))
        self.assertEqual(five_three.replace("WP=5u WN=3u MP=2 MN=2",
                                            "WP=5u WN=2.75u MP=2 MN=2"),
                         candidate)

    def test_retapered_revision_changes_only_final_multiplicity(self) -> None:
        root = Path(__file__).resolve().parent
        balanced = (root / "event_capture_bridge_balanced_edges_5_2p75.spice").read_text()
        retapered = (root / "event_capture_bridge_5_2p75_clk8.spice").read_text()
        balanced = "\n".join(line for line in balanced.splitlines()
                             if line and not line.startswith("*"))
        retapered = "\n".join(line for line in retapered.splitlines()
                              if line and not line.startswith("*"))
        self.assertEqual(balanced.replace("XCLK ENDR CLK VDD VSS ecb_inv WP=12u WN=5u MP=16 MN=16",
                                          "XCLK ENDR CLK VDD VSS ecb_inv WP=12u WN=5u MP=8 MN=8"),
                         retapered)

    def test_direct_end_revision_removes_only_redundant_clk_stages(self) -> None:
        root = Path(__file__).resolve().parent
        direct = (root / "event_capture_bridge_direct_end.spice").read_text()
        circuit = "\n".join(line for line in direct.splitlines()
                            if line and not line.startswith("*"))
        self.assertIn("XCB0 START STARTB VDD VSS ecb_inv WP=5u WN=2.75u MP=4 MN=4", direct)
        self.assertIn("XCLK END CLK VDD VSS ecb_inv WP=12u WN=5u MP=8 MN=8", direct)
        self.assertNotIn("XCK0", circuit)
        self.assertNotIn("XCK1", circuit)
        self.assertEqual(sum(line.startswith(("XE ", "XO "))
                             and line.endswith(" event_capture_phase")
                             for line in circuit.splitlines()), 2)

    def test_skewed_direct_end_changes_only_start_edge_strengths(self) -> None:
        root = Path(__file__).resolve().parent
        direct = (root / "event_capture_bridge_direct_end.spice").read_text()
        skewed = (root / "event_capture_bridge_direct_end_skewed.spice").read_text()
        direct = "\n".join(line for line in direct.splitlines()
                           if line and not line.startswith("*"))
        skewed = "\n".join(line for line in skewed.splitlines()
                           if line and not line.startswith("*"))
        self.assertEqual(
            direct.replace("WP=5u WN=2.75u MP=4 MN=4",
                           "WP=5u WN=4u MP=3 MN=4"),
            skewed)

    def test_rebalanced_direct_end_changes_only_start_edge_strengths(self) -> None:
        root = Path(__file__).resolve().parent
        direct = (root / "event_capture_bridge_direct_end.spice").read_text()
        rebalanced = (root / "event_capture_bridge_direct_end_rebalanced.spice").read_text()
        direct = "\n".join(line for line in direct.splitlines()
                           if line and not line.startswith("*"))
        rebalanced = "\n".join(line for line in rebalanced.splitlines()
                               if line and not line.startswith("*"))
        self.assertEqual(
            direct.replace("WP=5u WN=2.75u MP=4 MN=4",
                           "WP=5u WN=3u MP=4 MN=4"),
            rebalanced)


if __name__ == "__main__":
    unittest.main()
