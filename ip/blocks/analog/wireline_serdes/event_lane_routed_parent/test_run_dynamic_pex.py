#!/usr/bin/env python3
"""Unit checks for dynamic exact-parent stimulus and scoring."""

import unittest
from pathlib import Path

import run_dynamic_pex as target


class DynamicPexTest(unittest.TestCase):
    def test_prbs_is_deterministic_and_nonconstant(self):
        a = target.prbs7(32)
        self.assertEqual(a, target.prbs7(32))
        self.assertEqual(set(a), {-1, 1})

    def test_deck_contains_first_failure_probes(self):
        env = next(x for x in target.base.HCLK_CONTRACT["environments"] if x["id"] == "tt")
        deck = target.compile_deck(Path("parent.pex"), env, target.prbs7(48), 4)
        self.assertIn("diag_fe_e_0", deck)
        self.assertIn("xparent.XEVENT.E_SENSE.t0", deck)
        self.assertIn("diag_restore_cb_o_output_low", deck)

    def test_common_latency_requires_both_phases(self):
        symbols = target.prbs7(48)
        observed = {}
        latency = 2
        for phase in ("e", "o"):
            for index in range(10):
                instant = target.SAMPLE_START[phase] + index * 800e-12
                symbol = target.symbol_at(symbols, instant, latency)
                observed[f"dyn_{phase}_{index}"] = 2.0 * symbol * target.PHASE_POLARITY[phase]
        scored = target.score(observed, symbols, 10)
        self.assertIn(latency, scored["common_passing_latency_ui"])
        self.assertEqual(scored["result"], "pass")

    def test_phase_age_mismatch_cannot_pass(self):
        symbols = target.prbs7(48)
        observed = {}
        for phase, latency in (("e", 1), ("o", 3)):
            for index in range(10):
                instant = target.SAMPLE_START[phase] + index * 800e-12
                symbol = target.symbol_at(symbols, instant, latency)
                observed[f"dyn_{phase}_{index}"] = 2.0 * symbol * target.PHASE_POLARITY[phase]
        scored = target.score(observed, symbols, 10)
        self.assertEqual(scored["common_passing_latency_ui"], [])
        self.assertEqual(scored["result"], "fail")


if __name__ == "__main__":
    unittest.main()
