#!/usr/bin/env python3
"""Identity and topology tests for event/bridge physical lowering."""

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
PULSE = ROOT.parent / "clock_pulse"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PULSE))

import compile_event_capture_physical_source as compiler  # noqa: E402
import generate_pulse_layout as layout  # noqa: E402


class EventCapturePhysicalSourceTest(unittest.TestCase):
    def test_selected_bridge_is_internal_and_exact(self) -> None:
        source = compiler.compile_source()
        self.assertIn(f".subckt {compiler.TOP}", source)
        self.assertNotIn(".subckt retimed_capture_events", source)
        self.assertEqual(source.count("XWCB0 START STARTB"), 1)
        self.assertEqual(source.count("XWCLK END CAPTURE_CLK"), 1)
        self.assertIn("XWCB0 START STARTB VDD VSS cp_inv WP=5u WN=3u MP=4 MN=4", source)
        self.assertIn("XWCLK END CAPTURE_CLK VDD VSS cp_inv WP=12u WN=5u MP=8 MN=8", source)
        self.assertNotIn("XWCK0", source)
        self.assertNotIn("XWCK1", source)

    def test_layout_sees_two_symmetric_phases(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".spice") as handle:
            handle.write(compiler.compile_source())
            handle.flush()
            devices, groups = layout.flatten(
                layout.parse(Path(handle.name)), compiler.TOP)
        # The generator represents each explicit MOS statement once; SPICE
        # multiplicity is retained on that device rather than expanded here.
        self.assertEqual(len(devices), 192)
        self.assertEqual(
            sorted(group.name.removeprefix("XE") for group in groups.values()
                   if group.phase == "E"),
            sorted(group.name.removeprefix("XO") for group in groups.values()
                   if group.phase == "O"),
        )
        self.assertEqual(sum(device.phase == "E" for device in devices), 96)
        self.assertEqual(sum(device.phase == "O" for device in devices), 96)

    def test_final_sense_delay_is_adjacent_to_detector(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".spice") as handle:
            handle.write(compiler.compile_source())
            handle.flush()
            devices, groups = layout.flatten(
                layout.parse(Path(handle.name)), compiler.TOP)
        _, group_x = layout.place(devices, groups, expanded_local_spacing=True)
        ordered = [group_x[f"XE__{name}"] for name in (
            "XHSD1__XD1", "XHSD2__XI0", "XHSD2__XI1",
            "XHSN__XIA", "XHSN__XN")]
        self.assertEqual(ordered, sorted(ordered))
        self.assertLess(ordered[-1] - ordered[0], 50.0)


if __name__ == "__main__":
    unittest.main()
