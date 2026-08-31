#!/usr/bin/env python3
"""Focused tests for the first product-specific closure contract."""

import unittest

from run_hclk_window_probe import (
    CONTRACT,
    ContractError,
    TEMPLATE,
    validate_structural_contract,
)


class HclkWindowContractTest(unittest.TestCase):
    def test_current_source_satisfies_semantic_bindings(self) -> None:
        result = validate_structural_contract(TEMPLATE, CONTRACT)
        self.assertEqual(result["result"], "pass")
        self.assertIn("XDET", result["checked_instances"])

    def test_raw_start_bypass_is_rejected(self) -> None:
        broken = TEMPLATE.replace(
            "XDET START END WIN VDD VSS cp_fall_window",
            "XDET S0A END WIN VDD VSS cp_fall_window",
        )
        with self.assertRaisesRegex(ContractError, "connectivity mismatch at XDET"):
            validate_structural_contract(broken, CONTRACT)

    def test_selector_polarity_swap_is_rejected(self) -> None:
        broken = TEMPLATE.replace(
            "XTG1 E1 EMUX SEL SELB VDD VSS cp_tg",
            "XTG1 E1 EMUX SELB SEL VDD VSS cp_tg",
        )
        with self.assertRaisesRegex(ContractError, "connectivity mismatch at XTG1"):
            validate_structural_contract(broken, CONTRACT)


if __name__ == "__main__":
    unittest.main()
