#!/usr/bin/env python3
"""Fail closed on the sub-400 ps converter schematic checkpoint."""

import argparse
import hashlib
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--dut", required=True, type=Path)
parser.add_argument("--result", required=True, type=Path)
args = parser.parse_args()

result = json.loads(args.result.read_text())
digest = hashlib.sha256(args.dut.read_bytes()).hexdigest()
cases = result.get("cases", [])
checks = (
    result.get("result") == "pass",
    result.get("dut_sha256") == digest,
    result.get("pipeline_latency_ui") == 1,
    result.get("sample_delays_s") == [120e-12],
    result.get("case_count") == result.get("complete_case_count") == 10,
    result.get("passing_contract_case_count") == 10,
    result.get("group_count") == result.get("passing_group_count") == 10,
    len(cases) == 10,
    min(case["qualified_logic_margin_v"] for case in cases) >= 0.50,
    max(case["observed"]["supply_current"] for case in cases) <= 0.010,
)
if not all(checks):
    raise SystemExit("fast CML-to-CMOS schematic evidence failed")
print("fast CML-to-CMOS schematic evidence: PASS")
