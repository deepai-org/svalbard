#!/usr/bin/env python3
"""Bind the two independently placeable branch physical identities."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from compile_branch import KINDS, SOURCE_REVISION


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
work = Path("/work")
branches = {}
for kind, (top, stages, _) in KINDS.items():
    pex = work / f"{kind}.pex.spice"
    text = pex.read_text()
    lvs = next((work / f"{kind}-lvs").rglob("*.lvs.out"))
    drc = next((work / f"{kind}-drc").rglob("*.rpt"))
    lvs_text, drc_text = lvs.read_text(), drc.read_text()
    if "Circuits match uniquely" not in lvs_text:
        raise RuntimeError(f"{kind} LVS did not match uniquely")
    drc_numbers = [int(value) for value in re.findall(r"(?:TOTAL DRC Errors\s*=|COUNT:)\s*(\d+)", drc_text)]
    if not drc_numbers or max(drc_numbers) != 0:
        raise RuntimeError(f"{kind} DRC did not close")
    if "Property errors were found" in lvs_text:
        raise RuntimeError(f"{kind} LVS has device-property errors")
    branches[kind] = {
        "top": top,
        "stage_multiplicities": list(stages),
        "drc_errors": 0,
        "lvs_result": "pass_unique",
        "pex_resistor_count": len(re.findall(r"^R\S+\s", text, re.I | re.M)),
        "pex_capacitor_count": len(re.findall(r"^C\S+\s", text, re.I | re.M)),
        "identity": {
            "source_sha256": digest(work / f"{kind}.spice"),
            "lvs_view_sha256": digest(work / f"{kind}-lvs.spice"),
            "layout_tcl_sha256": digest(work / f"{kind}-layout.tcl"),
            "mag_sha256": digest(work / f"{top}.mag"),
            "pex_sha256": digest(pex),
        },
    }
result = {
    "schema_version": 1,
    "claim": "distributed_clock_fanout_branch_physical_legality",
    "source_revision": SOURCE_REVISION,
    "physical_intent": "three pair macros placed beside their consumers; remote nets terminate only on first-stage gates",
    "branches": branches,
    "result": "pass",
    "not_a_claim": ["placed parent", "composed PEX timing", "PCIe compliance"],
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
