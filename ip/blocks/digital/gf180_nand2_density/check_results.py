#!/usr/bin/env python3
"""Bind the NAND2 search and signoff evidence into one result."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--work", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
comparison = json.loads((args.work / "comparison.json").read_text())
screen = json.loads((args.work / "physical-screen.json").read_text())
cells = ("nand2_min_3v3", "nand2_fast_3v3", "nand2_std_5v")
verification = {}
for cell in cells:
    drc = next((args.work / f"drc-{cell}").glob(f"{cell}.magic.drc/{cell}.magic.drc.rpt"))
    lvs = next((args.work / f"lvs-{cell}").glob(f"{cell}.magic.lvs/{cell}.lvs.out"))
    pex = args.work / f"pex-{cell}" / f"{cell}.pex.spice"
    match = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc.read_text())
    verification[cell] = {
        "drc_errors": int(match.group(1)) if match else -1,
        "lvs_unique": "Circuits match uniquely." in lvs.read_text(),
        "pex_resistors": len(re.findall(r"^R\d+\s", pex.read_text(), re.MULTILINE)),
        "pex_capacitors": len(re.findall(r"^C\d+\s", pex.read_text(), re.MULTILINE)),
        "gds_sha256": digest(args.work / f"{cell}.gds"),
        "pex_sha256": digest(pex),
    }
passed = (comparison["result"] == "pass" and screen["result"] == "pass" and
          all(item["drc_errors"] == 0 and item["lvs_unique"] for item in verification.values()))
result = {
    "schema_version": 1,
    "claim": "gf180_nand2_density_and_fo1_speed_study",
    "fo1_definition": "middle of three identical exact-PEX NAND2 stages; output drives one identical input",
    "minimum_search_domain": "four-transistor static CMOS, 3.3 V minimum-L PDK PCells, shared diffusion, one accessible pin per input/output",
    "minimum_candidate": comparison["summaries"]["minimum_3v3"],
    "fast_under_default_area_candidate": comparison["summaries"]["fastest_under_default_area_3v3"],
    "default_candidate": comparison["summaries"]["default_7t5v0"],
    "physical_sweep": {"candidate_count": screen["candidate_count"], "smallest": screen["smallest"],
                       "fastest_unbounded_endpoint": screen["fastest"]},
    "verification": verification,
    "render_sha256": digest(args.work / "nand2-layout-comparison.png"),
    "source_sha256": __import__("os").environ.get("ANALOG_SOURCE_SHA256", "unbound"),
    "result": "pass" if passed else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
if not passed:
    raise SystemExit(1)
