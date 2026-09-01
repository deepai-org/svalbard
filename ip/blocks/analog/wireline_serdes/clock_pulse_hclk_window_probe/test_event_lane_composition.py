#!/usr/bin/env python3
import unittest
import json
import hashlib
from pathlib import Path

import run_event_lane_composition as composition


ROOT = Path(__file__).resolve().parent


class EventLaneCompositionTest(unittest.TestCase):
    def test_deck_connects_real_event_outputs_to_real_lane_ports(self) -> None:
        environment = composition.base.CONTRACT["environments"][0]
        control = composition.event_runner.CONTROLS[4]
        deck = composition.compile_deck(Path("event.pex.spice"),
                                        Path("lane.pex.spice"),
                                        environment, control)
        self.assertIn("retimed_event_capture_bridge_pex", deck)
        self.assertIn("lane_rx_regenerative_capture_pex", deck)
        self.assertIn("E_SENSE E_REGEN_CLK E_REGEN_CLKB E_CLK E_CLKB E_BOOST", deck)
        self.assertNotIn("CE_SENSE", deck)
        self.assertNotIn("CE_BOOST", deck)
        self.assertIn("REREGEN E_REGEN_CLK 0 1m", deck)
        self.assertIn("meas tran e_dbg_sb1_high", deck)
        self.assertIn("let e_q_diff_vec = v(EVEN_Q)-v(EVEN_QB)", deck)
        self.assertIn("meas tran e_q_diff find e_q_diff_vec", deck)
        self.assertIn("res_typical", deck)

    def test_contract_matches_selected_event_revision(self) -> None:
        self.assertEqual(composition.CONTRACT["event_source_revision"],
                         composition.event_source.SOURCE_REVISION)
        self.assertEqual(set(composition.CONTRACT["rx_bias_v"]),
                         {item["id"] for item in composition.base.CONTRACT["environments"]})
        self.assertEqual(set(composition.CONTRACT["res_corner"]),
                         set(composition.CONTRACT["rx_bias_v"]))

    def test_candidate_identity_cli_is_explicit(self) -> None:
        source = Path(composition.__file__).read_text()
        self.assertIn("--event-schematic", source)
        self.assertIn("--event-source-revision", source)
        self.assertIn("event physical schematic identity mismatch", source)
        self.assertIn("--skip-debug-stages", source)
        self.assertIn("--interface-debug-stages", source)

    def test_topology_independent_deck_omits_only_internal_probes(self) -> None:
        environment = composition.base.CONTRACT["environments"][0]
        control = composition.event_runner.CONTROLS[4]
        deck = composition.compile_deck(Path("event.pex.spice"),
                                        Path("lane.pex.spice"),
                                        environment, control, ())
        self.assertNotIn("dbg_sb1", deck)
        self.assertIn("meas tran e_q_diff", deck)
        self.assertIn("meas tran e_sense_high", deck)

    def test_local_interface_buffer_is_explicit_and_checks_both_sides(self) -> None:
        environment = composition.base.CONTRACT["environments"][0]
        control = composition.event_runner.CONTROLS[4]
        deck = composition.compile_deck(Path("event.pex.spice"),
                                        Path("lane.pex.spice"),
                                        environment, control, (), True)
        self.assertIn(".subckt lane_if_buffer", deck)
        self.assertIn("XEB_S E_SENSE_SRC E_SENSE", deck)
        self.assertIn("meas tran e_sense_src_high", deck)
        self.assertIn("E_SENSE_SRC E_BOOST_SRC", deck)

    def test_schematic_debug_nodes_are_explicit_measures(self) -> None:
        environment = composition.base.CONTRACT["environments"][0]
        control = composition.event_runner.CONTROLS[4]
        deck = composition.compile_deck(
            Path("event.spice"), Path("lane.spice"), environment, control,
            (), False, (("e_sfdrv", "xevent.xe.SFDRV"),))
        self.assertIn("meas tran sch_e_sfdrv_high max v(xevent.xe.SFDRV)", deck)

    def test_selected_physical_source_identity_matches_record(self) -> None:
        physical = json.loads((ROOT / "event_capture_physical_result.json").read_text())
        expected = hashlib.sha256(
            composition.event_physical_source.compile_source().encode()).hexdigest()
        self.assertEqual(physical["identity"]["schematic_sha256"], expected)

if __name__ == "__main__":
    unittest.main()
