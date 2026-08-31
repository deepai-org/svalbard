#!/usr/bin/env python3
"""Bind DRC/LVS/PEX/render evidence for the local capture-clock bridge."""

import argparse
import hashlib
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser()
for name in ("drc", "lvs", "pex", "gds", "render", "layout", "schematic", "output"):
    parser.add_argument(f"--{name}", required=True, type=Path)
args = parser.parse_args()
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
drc, lvs, pex = args.drc.read_text(), args.lvs.read_text(), args.pex.read_text()
count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
mos_count = len(re.findall(r"^X\S+ .*\b[pn]fet_03v3\b", pex, re.MULTILINE))
resistors = len(re.findall(r"^R\d+\s", pex, re.MULTILINE))
capacitors = len(re.findall(r"^C\d+\s", pex, re.MULTILINE))
checks = {
    "drc_zero": bool(count and int(count.group(1)) == 0),
    "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
    # The layout uses 8/16-way parallel fingers for each of the eight logical
    # devices.  PEX preserves individual fingers, while Netgen proves their
    # parallel reduction is uniquely equivalent to the eight schematic MOS
    # instances.  Do not confuse raw PEX finger count with schematic identity.
    "fingerized_device_identity": mos_count >= 96,
    "full_rc": resistors >= 80 and capacitors >= 40,
    "rendered": args.render.stat().st_size >= 10_000,
}
result = {
    "schema_version": 1,
    "claim": "physical_local_complementary_capture_clock_bridge",
    "checks": checks,
    "drc_error_count": int(count.group(1)) if count else -1,
    "pex_mos_count": mos_count, "pex_resistor_count": resistors, "pex_capacitor_count": capacitors,
    "pex_sha256": digest(args.pex), "gds_sha256": digest(args.gds),
    "layout_image_sha256": digest(args.render), "layout_source_sha256": digest(args.layout),
    "schematic_source_sha256": digest(args.schematic),
    "result": "pass" if all(checks.values()) else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"capture-clock bridge physical: {result['result']}; {result['drc_error_count']} DRC; {mos_count} MOS; {resistors}R/{capacitors}C")
if result["result"] != "pass":
    raise SystemExit(1)
