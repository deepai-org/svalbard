#!/usr/bin/env python3
"""Run the no-ideal-control-clock extracted PCIe capture-boundary smoke test."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
ENVIRONMENTS = (
    ("tt", "typical", "res_typical", 3.30, 27, 1.30),
    ("ff_cold", "ff", "res_ff", 3.63, -40, 1.20),
    ("ff_hot", "ff", "res_ss", 2.97, 125, 1.20),
    ("ss_hot", "ss", "res_ff", 2.97, 125, 1.50),
    ("ss_cold", "ss", "res_ss", 3.63, -40, 1.50),
)
REQUIRED = {
    "e_sense_high", "o_sense_high", "e_write_high", "o_write_high",
    "e_clk_high", "o_clk_high", "e_clkb_low", "o_clkb_low",
    "e_clk_rise_first", "o_clk_rise_first",
    "e_clk_rise", "e_clkb_fall", "e_clk_fall", "e_clkb_rise",
    "o_clk_rise", "o_clkb_fall", "o_clk_fall", "o_clkb_rise",
    "e_q_diff", "o_q_diff", "supply_current",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
parser.add_argument("--pulse-pex", required=True, type=Path)
parser.add_argument("--pulse-physical", required=True, type=Path)
parser.add_argument("--bridge-pex", required=True, type=Path)
parser.add_argument("--bridge-physical", required=True, type=Path)
parser.add_argument("--lane-pex", required=True, type=Path)
parser.add_argument("--lane-physical", required=True, type=Path)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)


def require_bound(path: Path, physical: Path, name: str) -> dict:
    record = json.loads(physical.read_text())
    if record.get("result") != "pass" or record.get("pex_sha256") != digest(path):
        raise SystemExit(f"{name} PEX does not match a passing physical record")
    return record


pulse_physical = require_bound(args.pulse_pex, args.pulse_physical, "pulse")
bridge_physical = require_bound(args.bridge_pex, args.bridge_physical, "bridge")
lane_physical = require_bound(args.lane_pex, args.lane_physical, "lane")
template = (args.source / "pulse_bridge_lane" / "pulse_bridge_lane_tb.spice.in").read_text()
cases = []
for case_id, mos, res, vdd, temperature, rx_bias in ENVIRONMENTS:
    values = {
        "MOS_CORNER": mos, "RES_CORNER": res, "VDD_V": f"{vdd:.6f}",
        "TEMP_C": str(temperature), "VMID": f"{vdd / 2:.6f}",
        "RXP_V": f"{vdd / 2 + 0.10:.6f}", "RXN_V": f"{vdd / 2 - 0.10:.6f}",
        "RX_BIAS_V": f"{rx_bias:.6f}", "PULSE_PEX": str(args.pulse_pex),
        "BRIDGE_PEX": str(args.bridge_pex), "LANE_PEX": str(args.lane_pex),
    }
    deck = args.work / f"{case_id}.spice"
    log = args.work / f"{case_id}.log"
    text = template
    for key, value in values.items():
        text = text.replace(f"@{key}@", value)
    deck.write_text(text)
    try:
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=600, check=False)
        returncode = run.returncode
    except subprocess.TimeoutExpired:
        returncode = 124
    observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
    complete = returncode == 0 and REQUIRED <= observed.keys()
    skew = {
        "even_entry_ps": (observed.get("e_clk_rise", 0) - observed.get("e_clkb_fall", 0)) * 1e12,
        "even_exit_ps": (observed.get("e_clkb_rise", 0) - observed.get("e_clk_fall", 0)) * 1e12,
        "odd_entry_ps": (observed.get("o_clk_rise", 0) - observed.get("o_clkb_fall", 0)) * 1e12,
        "odd_exit_ps": (observed.get("o_clkb_rise", 0) - observed.get("o_clk_fall", 0)) * 1e12,
    }
    clock_period_ps = {
        "even": (observed.get("e_clk_rise", 0)
                 - observed.get("e_clk_rise_first", 0)) * 1e12,
        "odd": (observed.get("o_clk_rise", 0)
                - observed.get("o_clk_rise_first", 0)) * 1e12,
    }
    rails = all(observed.get(key, 0.0) >= vdd - 0.25 for key in
                ("e_sense_high", "o_sense_high", "e_write_high", "o_write_high",
                 "e_clk_high", "o_clk_high")) and all(
                    observed.get(key, vdd) <= 0.25 for key in
                    ("e_clkb_low", "o_clkb_low"))
    resolved = (abs(observed.get("e_q_diff", 0.0)) >= 0.50
                and abs(observed.get("o_q_diff", 0.0)) >= 0.50)
    passed = (complete and rails and resolved
              and all(abs(value) <= 125.0 for value in skew.values())
              and all(700.0 <= value <= 900.0
                      for value in clock_period_ps.values())
              and 0 < observed.get("supply_current", 0.0) <= 0.100)
    cases.append({
        "id": case_id, "environment": [mos, res, vdd, temperature],
        "complete": complete, "observed": observed, "clock_skew_ps": skew,
        "clock_period_ps": clock_period_ps,
        "result": "pass" if passed else "fail",
    })

result = {
    "schema_version": 1,
    "claim": "extracted_pulse_bridge_regenerative_lane_static_input",
    "evidence_class": "composed_leaf_pex_with_unrouted_parent_interconnect",
    "boundary": {
        "ideal_sources_retained": ["upstream recovered rail-clock", "static receiver input"],
        "ideal_timing_sources_removed": ["sense", "boost", "write", "capture clock", "capture clock complement"],
    },
    "case_count": len(cases),
    "passing_case_count": sum(case["result"] == "pass" for case in cases),
    "cases": cases,
    "source_sha256": {
        "runner": digest(Path(__file__)),
        "testbench": digest(args.source / "pulse_bridge_lane" / "pulse_bridge_lane_tb.spice.in"),
    },
    "pulse_pex_sha256": digest(args.pulse_pex),
    "pulse_physical_sha256": digest(args.pulse_physical),
    "bridge_pex_sha256": digest(args.bridge_pex),
    "bridge_physical_sha256": digest(args.bridge_physical),
    "lane_pex_sha256": digest(args.lane_pex),
    "lane_physical_sha256": digest(args.lane_physical),
    "result": "pass" if cases and all(case["result"] == "pass" for case in cases) else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": result["result"], "passing": result["passing_case_count"],
                  "cases": result["case_count"]}, sort_keys=True))
if result["result"] != "pass":
    raise SystemExit(1)
