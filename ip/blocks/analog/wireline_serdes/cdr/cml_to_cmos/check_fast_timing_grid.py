#!/usr/bin/env python3
"""Check the exact-PEX handoff from retained to newly resolved data."""

import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--current", required=True, type=Path)
parser.add_argument("--previous", required=True, type=Path)
args = parser.parse_args()
current = json.loads(args.current.read_text())
previous = json.loads(args.previous.read_text())


def delays(result: dict) -> dict[int, dict]:
    return {round(item["delay_s"] / 1e-12): item
            for item in result["delay_summary"]}


current_delays = delays(current)
previous_delays = delays(previous)
checks = (
    current.get("dut_sha256") == previous.get("dut_sha256"),
    current.get("case_count") == previous.get("case_count") == 3,
    current.get("complete_case_count") == previous.get("complete_case_count") == 3,
    previous_delays[500]["passing_contract_case_count"] == 3,
    previous_delays[600]["passing_contract_case_count"] < 3,
    current_delays[750]["passing_contract_case_count"] < 3,
    current_delays[760]["passing_contract_case_count"] == 3,
    current_delays[770]["passing_contract_case_count"] == 3,
    current_delays[780]["passing_contract_case_count"] == 3,
    current_delays[770]["minimum_contract_logic_margin_v"] >= 0.15,
)
if not all(checks):
    raise SystemExit("fast CML-to-CMOS timing-grid checkpoint failed")
print("fast CML-to-CMOS timing grid: PASS; retained through 500 ps, "
      "new data valid by 760 ps and >=150 mV margin by 770 ps")
