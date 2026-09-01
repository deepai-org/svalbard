#!/usr/bin/env python3
"""Structural tests for edge-selective release candidates."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "clock_pulse"))

import compile_event_capture_state_free_edge_hold_source as compiler
from generate_pulse_layout import flatten, parse


class EdgeHoldSourceTest(unittest.TestCase):
    def test_direct_driver_and_conditional_hold_are_both_present(self) -> None:
        source = compiler.compile_source(2)
        self.assertIn("XSENSE SFDRV SSEL SENSE", source)
        self.assertIn("XREL SFDRV SFREL", source)
        self.assertIn("XHOLD SENSE SFREL SSEL VSS", source)
        self.assertIn("W=8u M=2", source)

    def test_candidate_flattens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.spice"
            path.write_text(compiler.compile_source(2))
            devices, groups = flatten(parse(path), compiler.TOP)
        self.assertIn("XE__XHOLD", groups)
        self.assertIn("XE_IF__XSENSEIF1", groups)
        self.assertGreater(len(devices), 184)


if __name__ == "__main__":
    unittest.main()
