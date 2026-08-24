#!/usr/bin/env python3
"""Bind the routed fast-converter RX/PI parent to its exact sources and PEX."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subcircuit_ports(text: str, cell: str) -> list[str]:
    lines = text.splitlines()
    prefix = f".subckt {cell} "
    for index, line in enumerate(lines):
        if not line.lower().startswith(prefix.lower()):
            continue
        ports = line[len(prefix):].split()
        for continuation in lines[index + 1:]:
            if not continuation.startswith("+"):
                break
            ports.extend(continuation[1:].split())
        return ports
    raise SystemExit(f"missing .subckt {cell}")


parser = argparse.ArgumentParser()
for name in ("drc", "lvs", "pex", "gds", "render", "top-schematic",
             "capture-schematic", "frontend-schematic", "converter-schematic",
             "top-layout", "capture-layout", "frontend-layout",
             "frontend-base-layout", "converter-layout", "output"):
    parser.add_argument(f"--{name}", required=True, type=Path)
args = parser.parse_args()

drc = args.drc.read_text()
lvs = args.lvs.read_text()
pex = args.pex.read_text()
top_schematic = args.top_schematic.read_text()
count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
resistors = len(re.findall(r"^R\d+\s", pex, re.MULTILINE))
capacitors = len(re.findall(r"^C\d+\s", pex, re.MULTILINE))
checks = {
    "drc_zero": bool(count and int(count.group(1)) == 0),
    "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
    "interface_port_order_match": (
        subcircuit_ports(top_schematic, "lane_rx_pi_capture")
        == subcircuit_ports(pex, "lane_rx_pi_capture_pex")
    ),
    "full_parent_rc": resistors >= 8_500 and capacitors >= 4_800,
    "rendered": args.render.stat().st_size >= 20_000,
}
sources = {
    name: digest(getattr(args, name.replace("-", "_")))
    for name in ("top-schematic", "capture-schematic", "frontend-schematic",
                 "converter-schematic", "top-layout", "capture-layout",
                 "frontend-layout", "frontend-base-layout", "converter-layout")
}
result = {
    "schema_version": 1,
    "claim": "routed_phase_interpolator_rx_fast_dual_capture_parent",
    "checks": checks,
    "drc_error_count": int(count.group(1)) if count else -1,
    "lvs_unique": checks["lvs_unique"],
    "pex_resistor_count": resistors,
    "pex_capacitor_count": capacitors,
    "pex_sha256": digest(args.pex),
    "gds_sha256": digest(args.gds),
    "layout_image_sha256": digest(args.render),
    "source_sha256": sources,
}
result["result"] = "pass" if all(checks.values()) else "fail"
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"fast RX/PI parent: {result['result']}; DRC={result['drc_error_count']}; "
      f"LVS={result['lvs_unique']}; PEX={resistors}R/{capacitors}C")
if result["result"] != "pass":
    raise SystemExit(1)
