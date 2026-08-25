#!/usr/bin/env python3
"""Dependency-free tests for Magic PEX net/path analysis."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_pex_net import device_path_report, number, resistance_paths  # noqa: E402


class AnalyzePexNetTests(unittest.TestCase):
    def test_spice_suffixes(self) -> None:
        self.assertEqual(number("2.5k"), 2500.0)
        self.assertAlmostEqual(number("4p"), 4e-12)

    def test_worst_shortest_path(self) -> None:
        edges = [("VDD", "VDD.t1", 2.0),
                 ("VDD.t1", "VDD.t2", 3.0),
                 ("VDD", "VDD.t3", 9.0),
                 ("VDD.t2", "VDD.t3", 1.0)]
        result = resistance_paths("VDD", {"VDD.t2", "VDD.t3"}, edges)
        self.assertEqual(result["maximum_ohm"], 6.0)
        self.assertEqual(result["worst_target"], "VDD.t3")
        self.assertEqual(sum(item["resistance_ohm"]
                             for item in result["worst_path"]), 6.0)

    def test_device_gate_and_model_select_terminal(self) -> None:
        resistors = [("VDD", "VDD.t1", 4.0), ("VDD", "VDD.t2", 7.0)]
        devices = [
            {"name": "X1", "nodes": ["OUT.t1", "WB3.t1", "VDD.t1", "VDD"],
             "model": "pfet_03v3"},
            {"name": "X2", "nodes": ["OUT.t2", "WB3.t2", "VSS.t1", "VSS"],
             "model": "nfet_03v3"},
        ]
        result = device_path_report(
            "VDD", r"WB3", r"^pfet", "source", resistors, devices)
        self.assertEqual(result["selected_device_count"], 1)
        self.assertEqual(result["maximum_ohm"], 4.0)


if __name__ == "__main__":
    unittest.main()
