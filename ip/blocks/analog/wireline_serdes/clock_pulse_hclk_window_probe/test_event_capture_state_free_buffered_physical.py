#!/usr/bin/env python3
"""Structural tests for the physical state-free lane-interface lowering."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "clock_pulse"))

import compile_event_capture_state_free_buffered_physical_source as buffered
from generate_pulse_layout import flatten, parse


class BufferedPhysicalSourceTest(unittest.TestCase):
    def test_interface_is_inside_physical_top(self) -> None:
        source = buffered.compile_source()
        self.assertIn("XE_IF E_SENSE_SRC E_BOOST_SRC", source)
        self.assertIn("XO_IF O_SENSE_SRC O_BOOST_SRC", source)
        self.assertEqual(source.count("cp_lane_if_buffer\n"), 3)

    def test_buffer_has_two_realizable_stages_per_signal(self) -> None:
        source = buffered.compile_source()
        for name in ("XSENSEIF", "XBOOSTIF", "XWCLKIF", "XWCLKBIF"):
            self.assertIn(name + "0", source)
            self.assertIn(name + "1", source)
        self.assertIn("XSENSEIF0 SENSE_IN SENSE_B VDD VSS cp_inv WP=8u WN=8u MP=4 MN=2", source)
        self.assertIn("XSENSEIF1 SENSE_B SENSE VDD VSS cp_inv WP=8u WN=8u MP=8 MN=12", source)

    def test_layout_flattener_sees_buffer_devices(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.spice"
            path.write_text(buffered.compile_source())
            devices, groups = flatten(parse(path), buffered.TOP)
        names = {group.name for group in groups.values()}
        self.assertIn("XE_IF__XSENSEIF1", names)
        self.assertIn("XO_IF__XWCLKBIF1", names)
        self.assertEqual(sum(name.startswith(("XE_IF__", "XO_IF__"))
                             for name in names), 16)
        self.assertGreater(len(devices), 152)


if __name__ == "__main__":
    unittest.main()
