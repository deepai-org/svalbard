#!/usr/bin/env python3
"""Verify the committed fast-converter checkpoint and exact PEX identity."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
for name in ("physical", "timing", "pex", "render", "layout", "layout-core",
             "schematic"):
    parser.add_argument(f"--{name}", required=True, type=Path)
args = parser.parse_args()

physical = json.loads(args.physical.read_text())
timing = json.loads(args.timing.read_text())
cases = timing.get("cases", [])
checks = (
    physical.get("result") == timing.get("result") == "pass",
    all(physical.get("checks", {}).values()),
    physical.get("pex_sha256") == timing.get("dut_sha256") == digest(args.pex),
    physical.get("layout_image_sha256") == digest(args.render),
    physical.get("layout_source_sha256") == digest(args.layout),
    physical.get("layout_core_source_sha256") == digest(args.layout_core),
    physical.get("schematic_source_sha256") == digest(args.schematic),
    physical.get("timing_result_sha256") == digest(args.timing),
    timing.get("case_count") == timing.get("complete_case_count") == 10,
    timing.get("passing_contract_case_count") == 10,
    len(cases) == 10,
    min(case["qualified_logic_margin_v"] for case in cases) >= 0.50,
    max(case["observed"]["supply_current"] for case in cases) <= 0.010,
)
if not all(checks):
    raise SystemExit("fast CML-to-CMOS committed checkpoint failed")
print("fast CML-to-CMOS committed checkpoint: PASS")
