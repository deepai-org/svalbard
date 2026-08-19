#!/usr/bin/env python3
"""Dependency-free tests for the shared analog evidence kernel."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ip/blocks/analog/wireline_serdes"))

from analog_evidence import (  # noqa: E402
    EvidenceError,
    covers_band,
    covers_value,
    environment_index,
    merge_intervals,
    require_same_environment_keys,
    require_unique_sha256,
    sha256_file,
)


class AnalogEvidenceTests(unittest.TestCase):
    def test_merge_sorts_normalizes_and_joins_touching_intervals(self) -> None:
        self.assertEqual(
            merge_intervals([(5, 4), (1, 2), (2, 3), (8, 9)]),
            [[1.0, 3.0], [4.0, 5.0], [8.0, 9.0]],
        )

    def test_band_must_fit_one_connected_interval(self) -> None:
        intervals = [(1.0, 2.0), (3.0, 4.0)]
        self.assertTrue(covers_value(intervals, 3.5))
        self.assertFalse(covers_band(intervals, 1.5, 3.5))
        self.assertTrue(covers_band(intervals, 3.1, 3.9))

    def test_nonfinite_interval_fails_closed(self) -> None:
        with self.assertRaises(EvidenceError):
            merge_intervals([(1.0, float("nan"))])

    def test_environment_sets_require_identity_and_no_duplicates(self) -> None:
        first = environment_index([
            {"environment": ["typical", "res_typical", 3.3, 27]},
            {"environment": ["ss", "res_ss", 2.97, 125]},
        ])
        second = environment_index(list(reversed(list(first.values()))))
        self.assertEqual(
            require_same_environment_keys([first, second], expected_count=2),
            set(first),
        )
        with self.assertRaises(EvidenceError):
            environment_index([{"environment": ["ss"]}, {"environment": ["ss"]}])
        with self.assertRaises(EvidenceError):
            require_same_environment_keys([first, {("ff",): {}}])

    def test_sha256_validation_rejects_duplicates(self) -> None:
        values = ("0" * 64, "1" * 64)
        self.assertEqual(require_unique_sha256(values, expected_count=2), values)
        with self.assertRaises(EvidenceError):
            require_unique_sha256((values[0], values[0]), expected_count=2)
        with self.assertRaises(EvidenceError):
            require_unique_sha256(("not-a-digest",))

    def test_file_digest(self) -> None:
        path = Path(__file__)
        self.assertEqual(sha256_file(path), hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
