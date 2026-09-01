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

    def test_selected_physical_source_identity_matches_record(self) -> None:
        physical = json.loads((ROOT / "event_capture_physical_result.json").read_text())
        expected = hashlib.sha256(
            composition.event_physical_source.compile_source().encode()).hexdigest()
        self.assertEqual(physical["identity"]["schematic_sha256"], expected)

if __name__ == "__main__":
    unittest.main()
