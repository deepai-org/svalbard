#!/usr/bin/env python3
"""Unit checks for the exact-parent PEX deck compiler."""

import tempfile
import unittest
from pathlib import Path

import run_exact_pex as target


class ExactPexDeckTest(unittest.TestCase):
    def test_single_parent_and_explicit_controls(self):
        env = next(e for e in target.HCLK_CONTRACT["environments"] if e["id"] == "tt")
        deck = target.compile_deck(Path("parent.pex.spice"), env)
        self.assertEqual(deck.count("XPARENT CLKP_H"), 1)
        self.assertIn("event_lane_routed_parent_pex", deck)
        self.assertIn("VEBOOST E_SENSE_BOOST 0 3.3", deck)
        self.assertIn("VEREGEN E_REGEN_CLK 0 0", deck)
        self.assertIn(".save i(VDD)", deck)

    def test_manifest_hash_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pex"
            path.write_text("pex")
            self.assertEqual(target.digest(path),
                             "262f0d56e252a408a2cd66e65f1b32cca3633518067a7a773ab271849798932a")

    def test_static_latch_does_not_need_both_outputs_to_toggle(self):
        # The acceptance implementation is exercised through a synthetic
        # ngspice measure log in reuse mode.
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            values = {"supply_current": 0.08}
            for phase in ("e", "o"):
                values.update({f"{phase}_fe_diff": 2.7, f"{phase}_q_diff": 2.7,
                               f"{phase}_q_high": 3.2, f"{phase}_q_low": 3.1,
                               f"{phase}_qb_high": 0.4, f"{phase}_qb_low": 0.2})
            (work / "tt.log").write_text("\n".join(f"{k} = {v}" for k, v in values.items()))
            env = next(e for e in target.HCLK_CONTRACT["environments"] if e["id"] == "tt")
            case = target.run_case(Path("unused"), work, env, 1, reuse_log=True)
            self.assertTrue(case["output_rails_pass"])
            self.assertEqual(case["result"], "pass")


if __name__ == "__main__":
    unittest.main()
