#!/usr/bin/env python3
"""Localize which composed input/output envelope dimensions break the leaf."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROFILES = (
    ("nominal", 370.0, 0.0, 100e-15, 100e-15),
    ("short_sense_pulse", 510.0, 0.0, 100e-15, 100e-15),
    ("capture_parent", 414.0, 182.0, 120e-15, 120e-15),
    ("sense_parent", 510.0, 187.0, 190e-15, 50e-15),
)
BIAS_CODES = (0.85, 0.90, 1.00, 1.08, 1.20, 1.40, 1.60, 1.80)

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
source_group = parser.add_mutually_exclusive_group(required=True)
source_group.add_argument("--pex", type=Path)
source_group.add_argument("--dut-source", type=Path)
parser.add_argument("--dut-subckt", default="reference_level_receiver_pex")
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)

profiles = []
for name, pulse_high, source_r, load_p, load_n in PROFILES:
    output = args.work / f"{name}.json"
    command = [
        sys.executable, str(Path(__file__).with_name("run_bias_sweep.py")),
        "--source", str(args.source), "--dut-subckt", args.dut_subckt,
        "--pulse-high-ps", str(pulse_high),
        "--source-resistance-ohm", str(source_r),
        "--load-p-f", str(load_p), "--load-n-f", str(load_n),
        "--work", str(args.work / name), "--output", str(output),
        "--biases", *(str(code) for code in BIAS_CODES),
    ]
    command.extend((["--pex", str(args.pex)] if args.pex else
                    ["--dut-source", str(args.dut_source)]))
    run = subprocess.run(command, check=False)
    evidence = json.loads(output.read_text())
    profiles.append({"profile_id": name, "runner_returncode": run.returncode,
                     "pulse_high_s": pulse_high * 1e-12,
                     "source_resistance_ohm": source_r,
                     "load_p_f": load_p, "load_n_f": load_n,
                     "covered_case_count": evidence["covered_case_count"],
                     "candidate_result": evidence["result"],
                     "evidence": evidence})

result = {
    "schema_version": 1,
    "claim": "bounded_parent_envelope_failure_localization",
    "profile_count": len(profiles),
    "profiles": profiles,
    "result": "pass" if all(item["candidate_result"] == "pass"
                            and item["covered_case_count"] == 5
                            for item in profiles) else "fail",
    "not_a_claim": ["parent closure", "PVT yield", "PCIe compliance"],
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print("; ".join(f"{item['profile_id']}={item['covered_case_count']}/5"
                for item in profiles))
