#!/usr/bin/env python3
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "clock_pulse"))

import compile_event_capture_dynamic_physical_source as compiler  # noqa: E402
import generate_pulse_layout as layout  # noqa: E402


class DynamicEventPhysicalTest(unittest.TestCase):
    def test_dynamic_state_flattens_without_changing_device_count(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".spice") as handle:
            handle.write(compiler.compile_source())
            handle.flush()
            devices, groups = layout.flatten(layout.parse(Path(handle.name)),
                                             compiler.TOP)
        self.assertEqual(len(devices), 192)
        self.assertEqual(sum(device.phase == "E" for device in devices), 96)
        self.assertEqual(sum(device.phase == "O" for device in devices), 96)
        self.assertIn("XE__XSB1", groups)
        state = groups["XE__XSB1"]
        self.assertEqual({device.nodes[1] for device in state.devices},
                         {"XE__HSN", "CLKP_H"})

    def test_set_reset_devices_are_adjacent_and_ordered(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".spice") as handle:
            handle.write(compiler.compile_source())
            handle.flush()
            devices, groups = layout.flatten(layout.parse(Path(handle.name)),
                                             compiler.TOP)
        _, group_x = layout.place(devices, groups, expanded_local_spacing=True)
        positions = [group_x[name] for name in
                     ("XE__XHSN__XN", "XE__XSB1", "XE__XSI0")]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[-1] - positions[0], 70.0)


if __name__ == "__main__":
    unittest.main()
