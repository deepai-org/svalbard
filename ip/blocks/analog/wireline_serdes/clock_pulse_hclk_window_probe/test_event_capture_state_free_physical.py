#!/usr/bin/env python3
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "clock_pulse"))

import compile_event_capture_state_free_physical_source as compiler  # noqa: E402
import generate_pulse_layout as layout  # noqa: E402


class StateFreeEventPhysicalTest(unittest.TestCase):
    def flatten(self):
        with tempfile.NamedTemporaryFile("w", suffix=".spice") as handle:
            handle.write(compiler.compile_source())
            handle.flush()
            return layout.flatten(layout.parse(Path(handle.name)), compiler.TOP)

    def test_flattens_symmetrically_without_dynamic_state(self) -> None:
        devices, groups = self.flatten()
        self.assertEqual(len(devices), 152)
        self.assertEqual(sum(device.phase == "E" for device in devices), 76)
        self.assertEqual(sum(device.phase == "O" for device in devices), 76)
        self.assertNotIn("XE__XSTATE", groups)

    def test_start_assist_branch_has_causal_order(self) -> None:
        devices, groups = self.flatten()
        _, group_x = layout.place(devices, groups, expanded_local_spacing=True)
        names = ("XE__XWRITE__XSR1", "XE__XSF0", "XE__XSF1",
                 "XE__XBOOST", "XE__XSENSE")
        positions = [group_x[name] for name in names]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[-1] - positions[0], 80.0)

    def test_output_drivers_are_unambiguous(self) -> None:
        _, groups = self.flatten()
        expected = {"E_SENSE": "XE__XSENSE", "E_BOOST": "XE__XBOOST",
                    "O_SENSE": "XO__XSENSE", "O_BOOST": "XO__XBOOST"}
        for net, name in expected.items():
            drivers = [group.name for group in groups.values()
                       if any(group.ports.get(pin) == net
                              for pin in ("Y", "D", "Q"))]
            outer = [driver for driver in drivers
                     if not any(other != driver
                                and driver.startswith(other + "__")
                                for other in drivers)]
            self.assertEqual(outer, [name])


if __name__ == "__main__":
    unittest.main()
