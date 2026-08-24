#!/usr/bin/env python3
"""Check physical closure and extracted timing of the clock converter."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
for name in ("source", "drc", "lvs", "pex", "gds", "render", "timing",
             "composed", "output"):
    parser.add_argument(f"--{name}", required=True, type=Path)
args = parser.parse_args()
drc = args.drc.read_text()
lvs = args.lvs.read_text()
pex = args.pex.read_text()
timing = json.loads(args.timing.read_text())
composed = json.loads(args.composed.read_text())
count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
result = {
    "schema_version": 1,
    "claim": "clock_level_converter_full_rc_physical_pvt",
    "drc_error_count": int(count.group(1)) if count else -1,
    "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
    "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
    "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
    "pex_sha256": digest(args.pex),
    "gds_sha256": digest(args.gds),
    "layout_image_sha256": digest(args.render),
    "layout_image_bytes": args.render.stat().st_size,
    "layout_source_sha256": digest(args.source / "layout.tcl"),
    "schematic_source_sha256": digest(
        args.source / "clock_level_converter.spice"),
    "checker_source_sha256": digest(Path(__file__)),
    "timing_evidence_sha256": digest(args.timing),
    "timing_result": timing.get("result"),
    "timing_case_count": timing.get("case_count"),
    "timing_passing_case_count": timing.get("passing_case_count"),
    "composed_evidence_sha256": digest(args.composed),
    "composed_result": composed.get("result"),
    "composed_case_count": composed.get("case_count"),
    "composed_passing_case_count": composed.get("passing_case_count"),
    "composed_environment_count": composed.get("environment_count"),
    "composed_covered_environment_count": composed.get(
        "covered_environment_count"),
}
passed = (result["drc_error_count"] == 0
          and result["lvs_unique"]
          and result["pex_resistor_count"] >= 100
          and result["pex_capacitor_count"] >= 100
          and result["layout_image_bytes"] >= 15_000
          and result["timing_result"] == "pass"
          and result["timing_case_count"] == 5
          and result["timing_passing_case_count"] == 5
          and timing.get("pex_sha256") == result["pex_sha256"]
          and result["composed_result"] == "pass"
          and result["composed_case_count"] == 28
          and result["composed_environment_count"] == 5
          and result["composed_covered_environment_count"] == 5
          and composed.get("pex_sha256", {}).get("clock_level_converter")
          == result["pex_sha256"])
result["result"] = "pass" if passed else "fail"
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"clock converter physical: DRC={result['drc_error_count']} "
      f"LVS={result['lvs_unique']} PEX={result['pex_resistor_count']}R/"
      f"{result['pex_capacitor_count']}C timing="
      f"{result['timing_passing_case_count']}/{result['timing_case_count']} "
      f"composed={result['composed_covered_environment_count']}/"
      f"{result['composed_environment_count']} environments")
if not passed:
    raise SystemExit(1)
