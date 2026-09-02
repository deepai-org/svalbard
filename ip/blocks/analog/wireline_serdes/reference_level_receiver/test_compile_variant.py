#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile_variant as target


class VariantCompilerTest(unittest.TestCase):
    def test_capture_is_baseline_with_renamed_top(self):
        source = target.compile_spice("capture", "capture_level_receiver")
        self.assertIn(".subckt capture_level_receiver IN", source)
        self.assertIn("XGAIN A MIDP VDD VSS rlr_inv WP=8u WN=6u MP=2 MN=2", source)

    def test_sense_strengthens_only_required_path(self):
        source = target.compile_spice("sense", "sense_level_receiver")
        self.assertIn("XGAIN A MIDP VDD VSS rlr_inv WP=8u WN=6u MP=4 MN=4", source)
        self.assertIn("XOUTN MIDP OUTN VDD VSS rlr_inv WP=8u WN=6u MP=6 MN=4", source)
        self.assertIn("XOUTP MIDN OUTP VDD VSS rlr_inv WP=8u WN=6u MP=3 MN=2", source)
        layout = target.compile_layout("sense", "sense_level_receiver")
        self.assertIn("{XOUTN_P pfet_03v3 8 6 40 58 OUTN MIDP VDD}", layout)
        self.assertIn("save /work/sense_level_receiver", layout)

    def test_fast_sense_scales_matched_front_end(self):
        source = target.compile_spice("sense_fast", "sense_fast_receiver")
        self.assertIn("XIS N1 IN TAIL VSS nfet_03v3 w=12u", source)
        self.assertIn("XIR N2 REF TAIL VSS nfet_03v3 w=12u", source)
        self.assertIn("XTAIL TAIL VBIAS VSS VSS nfet_03v3 w=18u", source)
        layout = target.compile_layout("sense_fast", "sense_fast_receiver")
        self.assertIn("{XIS nfet_03v3 12 1", layout)

    def test_schmitt_sense_has_feedback_devices(self):
        source = target.compile_spice("sense_schmitt", "sense_schmitt_receiver")
        self.assertIn("XISOPF PINT A VDD VDD pfet_03v3", source)
        self.assertIn("XISONF NINT A VSS VSS nfet_03v3", source)
        self.assertNotIn("XISO N2 A VDD VSS rlr_inv", source)


if __name__ == "__main__":
    unittest.main()
