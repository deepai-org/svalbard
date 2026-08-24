#!/usr/bin/env python3
"""Scan shared clock-converter bias against one exact extracted netlist."""

import argparse
import json
import subprocess
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
parser.add_argument("--pex", required=True, type=Path)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
scans = []
bias_points_mv = (*range(900, 1151, 25), 1250)
for millivolts in bias_points_mv:
    vbias = millivolts / 1000
    output = args.work / f"bias-{millivolts}.json"
    subprocess.run([
        "python3", str(args.source / "run_level_converter.py"),
        "--source", str(args.source), "--pex", str(args.pex),
        "--vbias", str(vbias), "--work", str(args.work / f"cases-{millivolts}"),
        "--output", str(output),
    ], check=False)
    scans.append(json.loads(output.read_text()))

case_ids = [case["case_id"] for case in scans[0]["cases"]]
coverage = {}
for case_id in case_ids:
    passing = [scan["vbias_v"] for scan in scans
               for case in scan["cases"]
               if case["case_id"] == case_id and case["result"] == "pass"]
    coverage[case_id] = passing
result = {
    "schema_version": 1,
    "claim": "clock_level_converter_extracted_bias_range_scan",
    "bias_values_v": [scan["vbias_v"] for scan in scans],
    "case_passing_bias_values_v": coverage,
    "covered_case_count": sum(bool(values) for values in coverage.values()),
    "case_count": len(case_ids),
    "scans": scans,
}
result["result"] = ("pass" if result["covered_case_count"] == len(case_ids)
                    else "fail")
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"clock converter extracted bias coverage: "
      f"{result['covered_case_count']}/{result['case_count']}")
if result["result"] != "pass":
    raise SystemExit(1)
