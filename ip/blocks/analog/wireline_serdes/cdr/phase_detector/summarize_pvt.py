#!/usr/bin/env python3
"""Reduce a full phase-detector PVT result to compact reproducible evidence."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--dut", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = json.loads(args.input.read_text())
    if result["result"] != "pass" or result["passing_group_count"] != result["group_count"]:
        raise SystemExit("refusing to summarize a failing PVT result")
    selected = [group["selected_case"] for group in result["groups"]]
    margins = [min(case["early_margin_v"], case["late_margin_v"]) for case in selected]
    currents = [case["observed"]["supply_current"] for case in selected]
    common_modes = [value for case in selected for value in
                    (case["observed"]["early_cm_avg"], case["observed"]["late_cm_avg"])]
    summary = {
        "schema_version": 1,
        "result": "pass",
        "dut_sha256": hashlib.sha256(args.dut.read_bytes()).hexdigest(),
        "full_result_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "case_count": result["case_count"],
        "complete_case_count": result["complete_case_count"],
        "group_count": result["group_count"],
        "passing_group_count": result["passing_group_count"],
        "minimum_passing_bias_codes": min(group["passing_bias_count"] for group in result["groups"]),
        "selected_bias_histogram": dict(sorted(collections.Counter(
            f"{case['bias_v']:.2f}" for case in selected).items())),
        "selected_margin_v": {"minimum": min(margins), "maximum": max(margins)},
        "selected_supply_current_a": {"minimum": min(currents), "maximum": max(currents)},
        "selected_output_common_mode_v": {"minimum": min(common_modes), "maximum": max(common_modes)},
        "maximum_early_late_margin_mismatch_v": max(
            abs(case["early_margin_v"] - case["late_margin_v"]) for case in selected),
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
