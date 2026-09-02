#!/usr/bin/env python3
"""Bind physical evidence for the GF180 reference level receiver."""
import argparse, hashlib, json, re
from decimal import Decimal
from pathlib import Path

parser = argparse.ArgumentParser()
for name in ("drc", "lvs", "pex", "gds", "render", "layout", "schematic", "output"):
    parser.add_argument(f"--{name}", required=True, type=Path)
args = parser.parse_args()
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
drc, lvs, pex = args.drc.read_text(), args.lvs.read_text(), args.pex.read_text()
layout = args.layout.read_text()
count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
mos = len(re.findall(r"^X\S+ .*\b[pn]fet_03v3\b", pex, re.MULTILINE))
resistors = len(re.findall(r"^R\d+\s", pex, re.MULTILINE))
capacitors = len(re.findall(r"^C\d+\s", pex, re.MULTILINE))
layout_devices = []
for kind, width, fingers in re.findall(
        r"\{X\S+\s+([pn]fet_03v3)\s+([0-9.]+)\s+(\d+)\s+", layout):
    layout_devices.extend((kind, Decimal(width)) for _ in range(int(fingers)))
pex_devices = [(kind, Decimal(width)) for kind, width in re.findall(
    r"^X\S+ .*\b([pn]fet_03v3)\b.*\bw=([0-9.]+)u(?:\s|$)", pex,
    re.MULTILINE)]
device_parameters_match = sorted(layout_devices) == sorted(pex_devices)
checks = {"drc_zero": bool(count and int(count.group(1)) == 0),
          "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
          "fingerized_device_identity": mos >= 18,
          "layout_pex_device_parameters": device_parameters_match,
          "full_rc": resistors >= 20 and capacitors >= 10,
          "rendered": args.render.stat().st_size >= 10_000}
result = {"schema_version": 1, "claim": "physical_reference_level_receiver",
          "checks": checks, "drc_error_count": int(count.group(1)) if count else -1,
          "pex_mos_count": mos, "pex_resistor_count": resistors,
          "pex_capacitor_count": capacitors, "pex_sha256": digest(args.pex),
          "layout_device_count": len(layout_devices),
          "gds_sha256": digest(args.gds), "layout_image_sha256": digest(args.render),
          "layout_source_sha256": digest(args.layout),
          "schematic_source_sha256": digest(args.schematic),
          "result": "pass" if all(checks.values()) else "fail"}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"reference receiver physical: {result['result']}; {result['drc_error_count']} DRC; {mos} MOS; {resistors}R/{capacitors}C")
if result["result"] != "pass": raise SystemExit(1)
