#!/usr/bin/env python3
import unittest

import run_sense_write_composition as compose


class SenseWriteCompositionTest(unittest.TestCase):
    def test_selected_candidate_is_exact(self) -> None:
        self.assertEqual(len(compose.WRITE_CANDIDATES), 4)
        self.assertTrue(all(candidate["id"].startswith("epoch_slow_extra_")
                            for candidate in compose.WRITE_CANDIDATES))

    def test_compiled_deck_has_no_placeholders(self) -> None:
        deck = compose.compile_deck(compose.WRITE_CANDIDATES[0],
                                    compose.SENSE_CANDIDATES[0],
                                    compose.base.CONTRACT["environments"][0], 0)
        self.assertNotIn("@", deck)
        self.assertIn("XWRITE HCLK SEL VDD VSS WRITE WPN hclk_select_window", deck)

    def test_sense_bypass_is_rejected(self) -> None:
        broken = compose.APPEND_PATH.read_text().replace(
            "XHSD1 HSM HSD VDD VSS cp_sense_tail_delay",
            "XHSD1 HCLK HSD VDD VSS cp_sense_tail_delay")
        with self.assertRaisesRegex(compose.base.ContractError,
                                    "connectivity mismatch at XHSD1"):
            compose.base.validate_structural_contract(broken, compose.CONTRACT)


if __name__ == "__main__":
    unittest.main()
