#!/usr/bin/env python3
"""Bind the freshly extracted pulse leaf used by the product composition."""

import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--drc-log", required=True, type=Path)
parser.add_argument("--lvs-log", required=True, type=Path)
parser.add_argument("--pex", required=True, type=Path)
parser.add_argument("--schematic", required=True, type=Path)
parser.add_argument("--layout-generator", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
drc, lvs = args.drc_log.read_text(), args.lvs_log.read_text()
checks = {
    "drc_clean": "Magic DRC is clean" in drc,
    "lvs_unique": "Magic+Netgen LVS is OK" in lvs,
    "pex_present": args.pex.stat().st_size > 10_000,
}
result = {
    "schema_version": 1,
    "claim": "fresh_extracted_pulse_leaf_for_composed_capture_boundary",
    "checks": checks,
    "pex_sha256": digest(args.pex),
    "schematic_source_sha256": digest(args.schematic),
    "layout_generator_sha256": digest(args.layout_generator),
    "result": "pass" if all(checks.values()) else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"pulse extract for composition: {result['result']}")
if result["result"] != "pass":
    raise SystemExit(1)
