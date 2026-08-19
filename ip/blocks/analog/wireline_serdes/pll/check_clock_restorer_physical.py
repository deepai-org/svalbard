#!/usr/bin/env python3
"""Check structural physical closure of the CML clock restorer."""
import argparse
import json
import re
import sys
from pathlib import Path

SERDES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERDES_ROOT))
from analog_evidence import sha256_file  # noqa: E402

parser = argparse.ArgumentParser()
for name in ("source", "drc", "lvs", "pex", "gds", "render", "output"):
    parser.add_argument(f"--{name}", type=Path, required=True)
parser.add_argument("--claim", default="clock_restorer_structural_physical_closure")
parser.add_argument("--layout-source", default="clock_restorer_layout.tcl")
parser.add_argument("--schematic-source", default="clock_restorer.spice")
parser.add_argument("--minimum-resistors", type=int, default=20)
parser.add_argument("--minimum-capacitors", type=int, default=5)
args = parser.parse_args()
drc, lvs, pex = args.drc.read_text(), args.lvs.read_text(), args.pex.read_text()
count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
result = {
    "schema_version": 1,
    "claim": args.claim,
    "drc_error_count": int(count.group(1)) if count else -1,
    "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
    "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
    "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
    "pex_sha256": sha256_file(args.pex),
    "gds_sha256": sha256_file(args.gds),
    "layout_image_sha256": sha256_file(args.render),
    "layout_source_sha256": sha256_file(args.source / args.layout_source),
    "schematic_source_sha256": sha256_file(args.source / args.schematic_source),
    "checker_source_sha256": sha256_file(Path(__file__)),
}
passed = (result["drc_error_count"] == 0 and result["lvs_unique"]
          and result["pex_resistor_count"] >= args.minimum_resistors
          and result["pex_capacitor_count"] >= args.minimum_capacitors
          and args.render.stat().st_size >= 10_000)
result["result"] = "pass" if passed else "fail"
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"clock restorer physical: DRC={result['drc_error_count']} LVS={result['lvs_unique']} "
      f"PEX={result['pex_resistor_count']}R/{result['pex_capacitor_count']}C")
if not passed:
    raise SystemExit(1)
