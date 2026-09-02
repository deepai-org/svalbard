#!/usr/bin/env python3
"""Find extracted-PVT calibration windows for the reference receiver bias."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
source_group = parser.add_mutually_exclusive_group(required=True)
source_group.add_argument("--pex", type=Path)
source_group.add_argument("--dut-source", type=Path)
parser.add_argument("--dut-subckt", required=True)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--biases", nargs="+", type=float, required=True)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)

runs = []
for bias in args.biases:
    tag = f"{bias:.2f}".replace(".", "p")
    output = args.work / f"bias-{tag}.json"
    command = [
        sys.executable, str(Path(__file__).with_name("run_screen.py")),
        "--source", str(args.source),
        "--dut-subckt", args.dut_subckt, "--reference-input",
        "--vbias", f"{bias:.6f}", "--work", str(args.work / tag),
        "--output", str(output),
    ]
    command.extend((["--pex", str(args.pex)] if args.pex else
                    ["--dut-source", str(args.dut_source)]))
    subprocess.run(command, check=False)
    runs.append(json.loads(output.read_text()))

case_ids = [case["case_id"] for case in runs[0]["cases"]]
windows = {}
for case_id in case_ids:
    passing = [run["vbias_v"] for run in runs
               if next(case for case in run["cases"]
                       if case["case_id"] == case_id)["result"] == "pass"]
    windows[case_id] = {
        "passing_biases_v": passing,
        "minimum_v": min(passing) if passing else None,
        "maximum_v": max(passing) if passing else None,
        "result": "pass" if passing else "fail",
    }

result = {
    "schema_version": 1,
    "claim": ("single_ended_reference_" +
              ("extracted" if args.pex else "schematic") +
              "_pvt_programmable_bias"),
    "biases_v": args.biases,
    "case_count": len(case_ids),
    "covered_case_count": sum(item["result"] == "pass"
                              for item in windows.values()),
    "calibration_windows": windows,
    "runs": runs,
    "dut_sha256": hashlib.sha256(
        (args.pex or args.dut_source).read_bytes()).hexdigest(),
    "sweep_runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
if args.pex:
    result["pex_sha256"] = result["dut_sha256"]
result["result"] = ("pass" if result["covered_case_count"] == len(case_ids)
                    else "fail")
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"reference receiver bias coverage: {result['covered_case_count']}/"
      f"{len(case_ids)} corners")
if result["result"] != "pass":
    raise SystemExit(1)
