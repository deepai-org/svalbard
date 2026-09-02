#!/usr/bin/env python3
import unittest

import compile_segment


class SegmentLoweringTest(unittest.TestCase):
    def test_selected_chain_is_preserved_across_cut(self) -> None:
        sampler = (compile_segment.compile_source("sampler_pre")
                   + compile_segment.compile_source("sampler_final"))
        capture = (compile_segment.compile_source("capture_pre")
                   + compile_segment.compile_source("capture_final"))
        for mult in (6, 16, 32):
            self.assertIn(f"MP={mult} MN={mult}", sampler)
        for mult in (4, 8):
            self.assertIn(f"MP={mult} MN={mult}", capture)

    def test_lvs_views_expand_width_and_remove_parameters(self) -> None:
        for kind, (_, stages) in compile_segment.KINDS.items():
            source = compile_segment.compile_source(kind, True)
            self.assertNotIn("params:", source)
            for mult in stages:
                self.assertIn(f"w={8 * mult}u", source)


if __name__ == "__main__":
    unittest.main()
