#!/usr/bin/env python3
"""Select the minimum-current passing control for each declared environment."""

import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--evidence", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
evidence = json.loads(args.evidence.read_text())
plan = {}
for case_id in evidence["calibration_windows"]:
    choices = []
    for run in evidence["runs"]:
        case = next((item for item in run["cases"] if item["case_id"] == case_id), None)
        if case and case["result"] == "pass":
            choices.append((case["observed"]["supply_current"], run["bias_v"],
                            run["reference_offset_v"]))
    if not choices:
        raise ValueError(f"no passing control for {case_id}")
    _, bias, reference_offset = min(choices)
    plan[case_id] = {"bias_v": bias, "reference_offset_v": reference_offset}
args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
print(json.dumps(plan, sort_keys=True))
