#!/usr/bin/env python3
import unittest

import localize_selected_pex as localize


PEX = """* test
.subckt selected_dual_control_pulse_pex A B
R0 E_WRITE E_WRITE.t0 12
R1 DBG_E_SB1 DBG_E_SB1.t0 20
C0 E_WRITE 0 10f
C1 DBG_E_SB1.t0 VDD.t0 2f
C2 SEL0.t0 0 3f
X0 E_WRITE.t0 SEL0.t0 0 0 nfet_03v3
.ends
"""


class LocalizeSelectedPexTest(unittest.TestCase):
    def test_output_cap_counterfactual_preserves_devices_and_other_caps(self) -> None:
        transformed = localize.transform(PEX, remove_caps={"E_WRITE"})
        self.assertNotIn("C0 E_WRITE", transformed)
        self.assertIn("C1 DBG_E_SB1", transformed)
        self.assertIn("C2 SEL0", transformed)
        self.assertIn("X0 E_WRITE", transformed)

    def test_semantic_resistance_counterfactual_changes_only_selected_net(self) -> None:
        transformed = localize.transform(PEX,
                                         short_resistance={"DBG_E_SB1"})
        self.assertIn("R0 E_WRITE E_WRITE.t0 12", transformed)
        self.assertIn("R1 DBG_E_SB1 DBG_E_SB1.t0 1m", transformed)


if __name__ == "__main__":
    unittest.main()
