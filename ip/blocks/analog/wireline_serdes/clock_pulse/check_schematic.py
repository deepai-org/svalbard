#!/usr/bin/env python3
"""Fail closed on the CML-to-CMOS clock-converter schematic checkpoint."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


result = json.loads((HERE / "schematic_result.json").read_text())
if (result.get("result") != "pass"
        or result.get("case_count") != 5
        or result.get("passing_case_count") != 5):
    raise SystemExit("clock converter schematic matrix is not 5/5 passing")

expected_hashes = {
    "dut": digest(HERE / "clock_level_converter.spice"),
    "testbench": digest(HERE / "clock_level_converter_tb.spice.in"),
    "runner": digest(HERE / "run_level_converter.py"),
}
if result.get("source_sha256") != expected_hashes:
    raise SystemExit("clock converter source identity changed")

for case in result.get("cases", []):
    observed = case.get("observed", {})
    if (case.get("result") != "pass"
            or not case.get("complete")
            or not 0.35 <= case.get("duty_cycle", 0) <= 0.65
            or abs(case.get("rise_delay_s", 1)) > 400e-12
            or abs(case.get("fall_delay_s", 1)) > 400e-12
            or case.get("rise_complement_skew_s", 1) > 110e-12
            or case.get("fall_complement_skew_s", 1) > 110e-12
            or not 0 < observed.get("supply_current", 0) <= 0.008):
        raise SystemExit(f"clock converter case contract changed: {case.get('case_id')}")

print("clock level converter schematic evidence: PASS")
