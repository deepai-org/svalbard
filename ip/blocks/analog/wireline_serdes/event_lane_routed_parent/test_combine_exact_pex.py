#!/usr/bin/env python3
"""Tests for fail-closed split-campaign composition."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import combine_exact_pex as target


def result(environments, identity="pex"):
    cases = [{"environment_id": item, "result": "pass"} for item in environments]
    return {"schema_version": 1, "claim": "c", "scope": "s",
            "physical_sha256": "physical", "pex_sha256": identity,
            "control": {"id": "code"}, "case_count": len(cases),
            "passing_case_count": len(cases), "cases": cases,
            "not_a_claim": ["system"], "result": "pass"}


class CombineTest(unittest.TestCase):
    def write(self, root, name, value):
        path = root / name
        path.write_text(json.dumps(value))
        return path

    def test_complete_disjoint_union(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "contract.json"
            contract.write_text(json.dumps({"environments": [{"id": x} for x in "abcde"]}))
            paths = [self.write(root, "a.json", result(["a", "b"])),
                     self.write(root, "b.json", result(["c", "d", "e"]))]
            with mock.patch.object(target, "HCLK_CONTRACT", contract):
                combined = target.combine(paths)
            self.assertEqual(combined["result"], "pass")
            self.assertEqual(combined["case_count"], 5)

    def test_rejects_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [self.write(root, "a.json", result(["a"])),
                     self.write(root, "b.json", result(["b"], "other"))]
            with self.assertRaisesRegex(ValueError, "pex_sha256 mismatch"):
                target.combine(paths)

    def test_rejects_duplicate_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "contract.json"
            contract.write_text(json.dumps({"environments": [{"id": "a"}]}))
            paths = [self.write(root, "a.json", result(["a"])),
                     self.write(root, "b.json", result(["a"]))]
            with mock.patch.object(target, "HCLK_CONTRACT", contract), \
                    self.assertRaisesRegex(ValueError, "duplicate"):
                target.combine(paths)


if __name__ == "__main__":
    unittest.main()
