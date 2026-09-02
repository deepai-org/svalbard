#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "clock_pulse"))

import compile_local_clock_fanout_source as compiler
from generate_pulse_layout import flatten, parse


class LocalClockFanoutSourceTest(unittest.TestCase):
    def test_selected_fanout_flattens_with_six_symmetric_branches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fanout.spice"
            source.write_text(compiler.compile_source())
            devices, groups = flatten(parse(source), compiler.TOP)
        self.assertEqual(len(groups), 12)
        self.assertEqual(len(devices), 24)
        self.assertEqual(sum(device.mult for device in devices), 192)
        self.assertEqual(sum(device.mult for device in devices if device.phase == "E"), 96)
        self.assertEqual(sum(device.mult for device in devices if device.phase == "O"), 96)
        for phase in ("E", "O"):
            for branch in ("S", "C", "CB"):
                self.assertIn(f"X{phase}{branch}__XI0", groups)
                self.assertIn(f"X{phase}{branch}__XI1", groups)

    def test_source_identity_and_ports_are_explicit(self) -> None:
        source = compiler.compile_source()
        self.assertIn(compiler.SOURCE_REVISION, source)
        self.assertIn("E_SENSE E_CAPTURE_CLK E_CAPTURE_CLKB", source)
        self.assertIn("O_SENSE O_CAPTURE_CLK O_CAPTURE_CLKB", source)
        self.assertEqual(source.count(" clock_fanout_buffer PRE="), 6)

    def test_retained_physical_identity_matches_replay_artifacts(self) -> None:
        physical = json.loads((ROOT / "local_clock_fanout_physical.json").read_text())
        self.assertEqual(physical["result"], "pass")
        for key, name in (("schematic_sha256", "local_clock_fanout.spice"),
                          ("pex_sha256", "local_clock_fanout.pex.spice")):
            observed = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            self.assertEqual(physical["identity"][key], observed)
        image = ROOT.parents[4] / "docs/images/pcie-local-clock-fanout-layout.png"
        self.assertEqual(physical["identity"]["layout_png_sha256"],
                         hashlib.sha256(image.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
