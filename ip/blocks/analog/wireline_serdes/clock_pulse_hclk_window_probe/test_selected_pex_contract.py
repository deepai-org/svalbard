#!/usr/bin/env python3
import unittest
from pathlib import Path

import run_selected_pex as selected


class SelectedPexContractTest(unittest.TestCase):
    def test_contract_selection_matches_physical_compiler(self) -> None:
        self.assertEqual(selected.CONTRACT["selected_write_candidate"],
                         selected.physical.SELECTED_WRITE)
        self.assertEqual(selected.CONTRACT["selected_sense_candidate"],
                         selected.physical.SELECTED_SENSE)

    def test_deck_instantiates_extracted_dual_phase_top(self) -> None:
        environment = selected.base.CONTRACT["environments"][0]
        code = selected.base.CONTRACT["control_codes"][0]
        deck = selected.compile_deck(Path("/work/example.pex.spice"),
                                     "selected_dual_control_pulse_pex",
                                     environment, code)
        self.assertIn("selected_dual_control_pulse_pex", deck)
        self.assertIn("VCLKN CLKN_H", deck)
        self.assertIn("meas tran e_sense_rise", deck)
        self.assertIn("meas tran o_write_fall", deck)


if __name__ == "__main__":
    unittest.main()
