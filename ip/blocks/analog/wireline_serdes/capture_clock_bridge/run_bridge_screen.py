#!/usr/bin/env python3
"""Screen the local capture-clock bridge into the extracted capture load."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
ENVIRONMENTS = (
    ("tt", "typical", 3.30, 27),
    ("ff_cold", "ff", 3.63, -40),
    ("ff_hot", "ff", 2.97, 125),
    ("ss_hot", "ss", 2.97, 125),
    ("ss_cold", "ss", 3.63, -40),
)
REQUIRED = {
    "e_clk_rise", "e_clkb_fall", "e_clk_fall", "e_clkb_rise",
    "o_clk_rise", "o_clkb_fall", "o_clk_fall", "o_clkb_rise",
    "e_clk_high", "e_clk_low", "e_clkb_high", "e_clkb_low",
    "o_clk_high", "o_clk_low", "o_clkb_high", "o_clkb_low",
    "e_q_diff", "o_q_diff", "supply_current",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
parser.add_argument("--capture-pex", required=True, type=Path)
parser.add_argument("--capture-physical", required=True, type=Path)
parser.add_argument("--bridge-pex", type=Path)
parser.add_argument("--bridge-physical", type=Path)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--write-width-ps", type=float, default=200.0)
parser.add_argument("--environment", action="append")
args = parser.parse_args()
if not 100.0 <= args.write_width_ps <= 220.0:
    parser.error("write width must stay inside the pulse-generator contract")
if bool(args.bridge_pex) != bool(args.bridge_physical):
    parser.error("bridge PEX and bridge physical evidence must be supplied together")
args.work.mkdir(parents=True, exist_ok=True)
capture_physical = json.loads(args.capture_physical.read_text())
capture_pex_hash = digest(args.capture_pex)
if (capture_physical.get("result") != "pass"
        or capture_physical.get("pex_sha256") != capture_pex_hash):
    raise SystemExit("capture PEX does not match its physical evidence record")
template_path = args.source / "capture_clock_bridge" / "capture_clock_bridge_tb.spice.in"
bridge_path = args.source / "capture_clock_bridge" / "capture_clock_bridge.spice"
bridge_subckt = "capture_clock_bridge"
if args.bridge_pex:
    bridge_physical = json.loads(args.bridge_physical.read_text())
    bridge_pex_hash = digest(args.bridge_pex)
    if (bridge_physical.get("result") != "pass"
            or bridge_physical.get("pex_sha256") != bridge_pex_hash):
        raise SystemExit("bridge PEX does not match its physical evidence record")
    bridge_path = args.bridge_pex
    bridge_subckt = "capture_clock_bridge_pex"
template = template_path.read_text()
selected = tuple(env for env in ENVIRONMENTS
                 if not args.environment or env[0] in args.environment)
if not selected:
    parser.error("no selected environment")


cases = []
for name, corner, vdd, temperature in selected:
    text = template
    for key, value in {
        "MOS_CORNER": corner,
        "TEMP_C": str(temperature),
        "VDD_V": f"{vdd:.6f}",
        "VMID": f"{vdd / 2:.6f}",
        "WRITE_WIDTH": f"{args.write_width_ps * 1e-12:.12g}",
        "BRIDGE_PATH": str(bridge_path),
        "BRIDGE_SUBCKT": bridge_subckt,
        "CAPTURE_PEX": str(args.capture_pex),
    }.items():
        text = text.replace(f"@{key}@", value)
    deck, log = args.work / f"{name}.spice", args.work / f"{name}.log"
    deck.write_text(text)
    try:
        with log.open("w") as handle:
            process = subprocess.run(["ngspice", "-b", str(deck)],
                                     stdout=handle, stderr=subprocess.STDOUT,
                                     timeout=300, check=False)
        returncode = process.returncode
    except subprocess.TimeoutExpired:
        returncode = 124
    observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
    complete = returncode == 0 and REQUIRED <= observed.keys()
    skew = {
        # Positive entry means the PMOS side enables first.  Negative exit
        # means that same PMOS side disables first.  Both are intentional and
        # bounded; converting them to a modulo-period delay hid this fact.
        "entry_ps": (observed.get("e_clk_rise", 0)
                     - observed.get("e_clkb_fall", 0)) * 1e12,
        "exit_ps": (observed.get("e_clkb_rise", 0)
                    - observed.get("e_clk_fall", 0)) * 1e12,
        "odd_entry_ps": (observed.get("o_clk_rise", 0)
                         - observed.get("o_clkb_fall", 0)) * 1e12,
        "odd_exit_ps": (observed.get("o_clkb_rise", 0)
                        - observed.get("o_clk_fall", 0)) * 1e12,
    }
    rails = all(observed.get(key, 0.0) >= vdd - 0.25 for key in
                ("e_clk_high", "e_clkb_high", "o_clk_high", "o_clkb_high")) and all(
                    observed.get(key, vdd) <= 0.25 for key in
                    ("e_clk_low", "e_clkb_low", "o_clk_low", "o_clkb_low"))
    passed = (complete and rails and all(abs(value) <= 125.0 for value in skew.values())
              and observed.get("e_q_diff", 0.0) >= 0.50
              and observed.get("o_q_diff", 0.0) <= -0.50
              and 0.0 < observed.get("supply_current", 0.0) <= 0.075)
    cases.append({
        "id": name, "environment": [corner, vdd, temperature],
        "complete": complete, "clock_skew_ps": skew, "observed": observed,
        "result": "pass" if passed else "fail",
    })

result = {
    "schema_version": 1,
    "claim": "local_complementary_capture_clock_bridge_into_extracted_capture",
    "evidence_class": ("extracted_bridge_and_capture"
                       if args.bridge_pex else
                       "schematic_bridge_with_extracted_capture_load"),
    "case_count": len(cases),
    "passing_case_count": sum(case["result"] == "pass" for case in cases),
    "write_width_ps": args.write_width_ps,
    "source_sha256": {"bridge": digest(bridge_path), "runner": digest(Path(__file__)),
                      "testbench": digest(template_path)},
    "capture_pex_sha256": digest(args.capture_pex),
    "capture_physical_sha256": digest(args.capture_physical),
    "cases": cases,
    "result": "pass" if cases and all(case["result"] == "pass" for case in cases) else "fail",
}
if args.bridge_pex:
    result["bridge_pex_sha256"] = digest(args.bridge_pex)
    result["bridge_physical_sha256"] = digest(args.bridge_physical)
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": result["result"], "passing": result["passing_case_count"],
                  "cases": result["case_count"]}, sort_keys=True))
if result["result"] != "pass":
    raise SystemExit(1)
