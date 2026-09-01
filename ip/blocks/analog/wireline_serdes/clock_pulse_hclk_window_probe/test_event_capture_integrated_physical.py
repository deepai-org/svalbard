#!/usr/bin/env python3
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "clock_pulse"))

import compile_event_capture_integrated_physical_source as compiler  # noqa: E402
import generate_pulse_layout as layout  # noqa: E402


class IntegratedEventPhysicalTest(unittest.TestCase):
    def flatten(self):
        with tempfile.NamedTemporaryFile("w", suffix=".spice") as handle:
            handle.write(compiler.compile_source())
            handle.flush()
            return layout.flatten(layout.parse(Path(handle.name)), compiler.TOP)

    def test_integrated_state_flattens_symmetrically(self) -> None:
        devices, groups = self.flatten()
        self.assertEqual(sum(device.phase == "E" for device in devices),
                         sum(device.phase == "O" for device in devices))
        self.assertIn("XE__XSTATE", groups)
        state = groups["XE__XSTATE"]
        self.assertTrue({"XE__HSN", "CLKP_H"}
                        <= {device.nodes[1] for device in state.devices})

    def test_state_and_local_tapers_have_causal_order(self) -> None:
        devices, groups = self.flatten()
        _, group_x = layout.place(devices, groups, expanded_local_spacing=True)
        names = ("XE__XHSN__XN", "XE__XSTATE", "XE__XLS0", "XE__XLS1",
                 "XE__XLS2", "XE__XLS3", "XE__XSB2")
        positions = [group_x[name] for name in names]
        self.assertEqual(positions, sorted(positions))

    def test_integrated_output_drivers_are_unambiguous(self) -> None:
        _, groups = self.flatten()
        expected = {"E_SENSE": "XE__XSB2", "E_BOOST": "XE__XLB2",
                    "O_SENSE": "XO__XSB2", "O_BOOST": "XO__XLB2"}
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
