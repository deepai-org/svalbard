#!/usr/bin/env python3
"""Tests for PEX route localization."""

import tempfile
import unittest
from pathlib import Path

import localize_pex_paths as target


class PexPathTest(unittest.TestCase):
    def test_shortest_resistor_path_and_component_capacitance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.pex"
            path.write_text("R1 A B 2\nR2 B C 3\nR3 A C 10\nC1 A VSS 2f\nC2 C VSS 3f\n")
            graph, caps = target.parse(path)
            resistance, nodes = target.shortest(graph, "A", "C")
            capacitance, count = target.component_capacitance(graph, caps, "A")
            self.assertEqual(resistance, 5)
            self.assertEqual(nodes, ["A", "B", "C"])
            self.assertAlmostEqual(capacitance, 5e-15)
            self.assertEqual(count, 3)

    def test_numeric_suffixes(self):
        self.assertEqual(target.numeric("2.5k"), 2500)
        self.assertAlmostEqual(target.numeric("14f"), 14e-15)


if __name__ == "__main__":
    unittest.main()
