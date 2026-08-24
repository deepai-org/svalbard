#!/usr/bin/env python3
"""Bind fast-converter geometry, extraction, and extracted timing evidence."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
for name in ("drc", "lvs", "pex", "gds", "render", "layout", "layout-core",
             "schematic", "timing", "output"):
    parser.add_argument(f"--{name}", required=True, type=Path)
args = parser.parse_args()

drc = args.drc.read_text()
lvs = args.lvs.read_text()
pex = args.pex.read_text()
timing = json.loads(args.timing.read_text())
count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
resistors = len(re.findall(r"^R\d+\s", pex, re.MULTILINE))
capacitors = len(re.findall(r"^C\d+\s", pex, re.MULTILINE))
cases = timing.get("cases", [])
checks = {
    "drc_zero": bool(count and int(count.group(1)) == 0),
    "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
    "coupled_full_rc": resistors >= 500 and capacitors >= 300,
    "rendered": args.render.stat().st_size >= 10_000,
    "timing_pass": timing.get("result") == "pass",
    "timing_pex_bound": timing.get("dut_sha256") == digest(args.pex),
    "one_lane_cycle_latency": timing.get("pipeline_latency_ui") == 1,
    "fixed_120ps_qualification": timing.get("sample_delays_s") == [120e-12],
    "bounded_boost_policy": timing.get("boost_policy") == "calibrated",
    "full_slow_corner_boost": timing.get("boost_fraction") == 1.0,
    "ten_contract_cases": (
        timing.get("case_count") == timing.get("complete_case_count") == 10
        and timing.get("passing_contract_case_count") == 10
        and len(cases) == 10
    ),
    "logic_margin": (
        len(cases) == 10
        and min(case["qualified_logic_margin_v"] for case in cases) >= 0.50
    ),
    "average_current": (
        len(cases) == 10
        and max(case["observed"]["supply_current"] for case in cases) <= 0.010
    ),
}
result = {
    "schema_version": 1,
    "claim": "fast_cml_to_cmos_extracted_physical_checkpoint",
    "checks": checks,
    "drc_error_count": int(count.group(1)) if count else -1,
    "pex_resistor_count": resistors,
    "pex_capacitor_count": capacitors,
    "pex_sha256": digest(args.pex),
    "gds_sha256": digest(args.gds),
    "layout_image_sha256": digest(args.render),
    "layout_source_sha256": digest(args.layout),
    "layout_core_source_sha256": digest(args.layout_core),
    "schematic_source_sha256": digest(args.schematic),
    "timing_result_sha256": digest(args.timing),
}
result["result"] = "pass" if all(checks.values()) else "fail"
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"fast CML-to-CMOS physical: {result['result']}; "
      f"DRC={result['drc_error_count']}; LVS={checks['lvs_unique']}; "
      f"PEX={resistors}R/{capacitors}C; timing={checks['timing_pass']}")
if result["result"] != "pass":
    raise SystemExit(1)
