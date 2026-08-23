#!/usr/bin/env python3
"""Bind CML-to-CMOS DRC, LVS, PEX, GDS, and rendered layout."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
for name in ("drc", "lvs", "pex", "gds", "render", "layout", "schematic", "output"):
    parser.add_argument(f"--{name}", required=True, type=Path)
args = parser.parse_args()
drc, lvs, pex = args.drc.read_text(), args.lvs.read_text(), args.pex.read_text()
count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
resistors = len(re.findall(r"^R\d+\s", pex, re.MULTILINE))
capacitors = len(re.findall(r"^C\d+\s", pex, re.MULTILINE))
checks = {
    "drc_zero": bool(count and int(count.group(1)) == 0),
    "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
    "full_rc": resistors >= 2000 and capacitors >= 1300,
    "rendered": args.render.stat().st_size >= 10_000,
}
result = {
    "schema_version": 1,
    "claim": "physical_cml_to_cmos_frontend",
    "checks": checks,
    "drc_error_count": int(count.group(1)) if count else -1,
    "pex_resistor_count": resistors,
    "pex_capacitor_count": capacitors,
    "pex_sha256": sha256(args.pex),
    "gds_sha256": sha256(args.gds),
    "layout_image_sha256": sha256(args.render),
    "layout_source_sha256": sha256(args.layout),
    "schematic_source_sha256": sha256(args.schematic),
    "result": "pass" if all(checks.values()) else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"CML-to-CMOS physical: {result['result']}; "
      f"DRC={result['drc_error_count']}; LVS={checks['lvs_unique']}; "
      f"PEX={resistors}R/{capacitors}C")
if result["result"] != "pass":
    raise SystemExit(1)
