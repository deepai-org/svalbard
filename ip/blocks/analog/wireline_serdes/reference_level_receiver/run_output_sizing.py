#!/usr/bin/env python3
"""Screen bounded restoration tapers against the exact StrongARM consumer."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


CANDIDATES = (
    ("baseline", 2, 2, 1, 1, 3, 2),
    ("sense_2x", 4, 4, 1, 1, 6, 4),
    ("balanced_2x", 4, 4, 2, 2, 6, 4),
    ("balanced_3x", 6, 6, 3, 3, 9, 6),
)

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
parser.add_argument("--parent-result", required=True, type=Path)
parser.add_argument("--consumer-pex", required=True, type=Path)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
base = args.source.read_text()
results = []
for name, gain_mp, gain_mn, phase_mp, phase_mn, final_mp, final_mn in CANDIDATES:
    source = base.replace(
        "XGAIN A MIDP VDD VSS rlr_inv WP=8u WN=6u MP=2 MN=2",
        f"XGAIN A MIDP VDD VSS rlr_inv WP=8u WN=6u MP={gain_mp} MN={gain_mn}")
    source = source.replace(
        "XPHASE MIDP MIDN VDD VSS rlr_inv WP=8u WN=4u MP=1 MN=1",
        f"XPHASE MIDP MIDN VDD VSS rlr_inv WP=8u WN=4u MP={phase_mp} MN={phase_mn}")
    source = source.replace(
        "XOUTN MIDP OUTN VDD VSS rlr_inv WP=8u WN=6u MP=3 MN=2",
        f"XOUTN MIDP OUTN VDD VSS rlr_inv WP=8u WN=6u MP={final_mp} MN={final_mn}")
    source = source.replace(
        "XOUTP MIDN OUTP VDD VSS rlr_inv WP=8u WN=6u MP=3 MN=2",
        f"XOUTP MIDN OUTP VDD VSS rlr_inv WP=8u WN=6u MP={final_mp} MN={final_mn}")
    candidate = args.work / f"{name}.spice"
    result_path = args.work / f"{name}.json"
    candidate.write_text(source)
    command = [sys.executable, str(Path(__file__).with_name("run_parent_waveform_replay.py")),
               "--parent-result", str(args.parent_result),
               "--dut-source", str(candidate),
               "--consumer-pex", str(args.consumer_pex),
               "--work", str(args.work / name), "--output", str(result_path),
               "--allow-fail"]
    subprocess.run(command, check=True)
    evidence = json.loads(result_path.read_text())
    results.append({"candidate_id": name, "gain_mp": gain_mp, "gain_mn": gain_mn,
                    "phase_mp": phase_mp, "phase_mn": phase_mn,
                    "final_mp": final_mp, "final_mn": final_mn,
                    "evidence": evidence, "result": evidence["result"]})
summary = {
    "schema_version": 1, "claim": "bounded_sense_output_taper_search",
    "candidate_count": len(results), "candidates": results,
    "passing_candidates": [item["candidate_id"] for item in results
                           if item["result"] == "pass"],
    "not_a_claim": ["physical closure", "PVT coverage", "routed-parent closure"],
}
summary["result"] = "pass" if summary["passing_candidates"] else "fail"
args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": summary["result"],
                  "passing_candidates": summary["passing_candidates"]}, sort_keys=True))
