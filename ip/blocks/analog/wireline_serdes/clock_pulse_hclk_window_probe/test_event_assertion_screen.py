#!/usr/bin/env python3
"""Tests for assertion-duration candidate lowering."""

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "clock_pulse"))

import compile_event_capture_state_free_stretched_source as compiler
from generate_pulse_layout import flatten, parse


class AssertionSourceTest(unittest.TestCase):
    def test_candidate_has_requested_realizable_delay(self) -> None:
        for cells in range(0, 5):
            source = compiler.compile_source(cells)
            self.assertEqual(source.count("XSWD"), cells)
            expected = "SFDRV" if cells == 0 else "SFDELAY"
            self.assertIn(f"XSWEN {expected} SSEL SFWIDE", source)
            self.assertIn("XSTRETCH SFDRV SFWIDE SENSE", source)

    def test_screening_top_is_explicit(self) -> None:
        source = compiler.compile_source(2, True)
        self.assertIn(".subckt retimed_event_capture_bridge_pex ", source)
        self.assertNotIn(".subckt retimed_event_capture_bridge ", source)

    def test_candidate_flattens_with_physical_interface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.spice"
            path.write_text(compiler.compile_source(2))
            devices, groups = flatten(parse(path), compiler.TOP)
        self.assertIn("XE__XSTRETCH__XO", groups)
        self.assertIn("XE_IF__XSENSEIF1", groups)
        self.assertGreater(len(devices), 184)


if __name__ == "__main__":
    unittest.main()
