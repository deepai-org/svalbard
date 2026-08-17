#!/usr/bin/env python3
"""Validate and compact the integrated-detector calibration result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = json.loads(args.input.read_text())
    groups = result.get("groups", [])
    checks = {
        "all_cases_complete": (result.get("case_count") == 1260
                               and result.get("complete_case_count") == 1260),
        "all_environments_calibrate": (result.get("group_count") == 9
                                       and result.get("passing_group_count") == 9
                                       and len(groups) == 9),
        "multiple_valid_settings": all(group.get("valid_setting_count", 0) >= 2
                                       for group in groups),
        "selected_settings_present": all(group.get("selected_setting") for group in groups),
    }
    passed = result.get("result") == "pass" and all(checks.values())
    selected = [group["selected_setting"] for group in groups]
    summary = {
        "schema_version": 1, "result": "pass" if passed else "fail", "checks": checks,
        "source_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "case_count": result.get("case_count"), "environment_count": len(groups),
        "observed": {
            "valid_setting_count": [min(group["valid_setting_count"] for group in groups),
                                    max(group["valid_setting_count"] for group in groups)],
            "selected_sampler_bias_v": [min(item["sampler_bias_v"] for item in selected),
                                         max(item["sampler_bias_v"] for item in selected)],
            "selected_edge_phase_deg": [min(item["edge_phase_deg"] for item in selected),
                                         max(item["edge_phase_deg"] for item in selected)],
            "selected_minimum_margin_v": [min(item["minimum_margin_v"] for item in selected),
                                           max(item["minimum_margin_v"] for item in selected)],
        },
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if not passed:
        raise SystemExit("integrated detector summary checks failed")
    print("cdr_alexander_frontend compact checks: PASS")


if __name__ == "__main__":
    main()
