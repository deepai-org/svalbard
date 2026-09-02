#!/usr/bin/env python3

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "clock_pulse"))

import compile_event_capture_state_free_sr_source as compiler
from generate_pulse_layout import flatten, functional_lane, parse, place


class StartEndSrPhysicalTest(unittest.TestCase):
    def test_selected_identity_flattens_for_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.spice"
            source.write_text(compiler.compile_source(2, 4, 8))
            devices, groups = flatten(parse(source), compiler.TOP)
            _, group_x = place(devices, groups)
        names = set(groups)
        for phase in ("XE", "XO"):
            for instance in ("XSETB", "XRESETB", "XQ", "XQB", "XO3"):
                self.assertIn(f"{phase}__XSENSESR__{instance}", names)
        self.assertEqual(len(devices), 232)
        core = [f"XE__XSENSESR__{name}" for name in
                ("XIS", "XIE", "XSETB", "XRESETB", "XQ", "XQB")]
        taper = [f"XE__XSENSESR__XO{index}" for index in range(4)]
        self.assertTrue(all(functional_lane(groups[name]) == 3 for name in core))
        self.assertTrue(all(functional_lane(groups[name]) == 2 for name in taper))
        self.assertLess(abs(group_x[core[0]] - group_x["XE__XWRITE__XSR1"]), 30.0)
        self.assertLess(abs(group_x[core[1]] - group_x["XE__XWRITE__XER1"]), 30.0)


if __name__ == "__main__":
    unittest.main()
