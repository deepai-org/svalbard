#!/usr/bin/env python3
import unittest

import compile_branch


class DistributedBranchTest(unittest.TestCase):
    def test_sampler_preserves_selected_v7_taper(self) -> None:
        source = compile_branch.compile_source("sampler")
        self.assertIn(".subckt distributed_sampler_branch CLKP_H CLKN_H VDD VSS E_SENSE O_DUMMY", source)
        for index, mult in enumerate((6, 16, 32)):
            self.assertIn(f"XES__XI{index} ", source)
            self.assertIn(f"MP={mult} MN={mult}", source)
        self.assertIn("XOS__XI0", source)

    def test_capture_preserves_selected_v7_taper(self) -> None:
        source = compile_branch.compile_source("capture")
        self.assertIn(".subckt distributed_capture_branch CLKP_H CLKN_H VDD VSS E_CAPTURE_CLK O_DUMMY", source)
        for index, mult in enumerate((4, 8)):
            self.assertIn(f"XES__XI{index} ", source)
            self.assertIn(f"MP={mult} MN={mult}", source)

    def test_lvs_view_expands_the_same_sampler_widths(self) -> None:
        source = compile_branch.compile_lvs_source("sampler")
        for width in (48, 128, 256):
            self.assertEqual(source.count(f"w={width}u"), 2)
        self.assertNotIn("params:", source)


if __name__ == "__main__":
    unittest.main()
