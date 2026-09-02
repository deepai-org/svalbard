#!/usr/bin/env python3
import unittest

import combine_pex


class SegmentCompositionTest(unittest.TestCase):
    def test_wrapper_has_six_complete_predriver_final_paths(self) -> None:
        source = combine_pex.wrapper()
        for name in ("SE", "SO", "CE", "CO", "CBE", "CBO"):
            self.assertIn(f"X{name}P ", source)
            self.assertIn(f"X{name}F ", source)
            self.assertIn(f"{name}_MID", source)
        self.assertEqual(source.count("distributed_sampler_pre_pex"), 2)
        self.assertEqual(source.count("distributed_sampler_final_pex"), 2)
        self.assertEqual(source.count("distributed_capture_pre_pex"), 4)
        self.assertEqual(source.count("distributed_capture_final_pex"), 4)


if __name__ == "__main__":
    unittest.main()
