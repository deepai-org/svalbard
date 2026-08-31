#!/usr/bin/env python3
"""Screen final bridge pull-up strength into the extracted PCIe capture load."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


ENVIRONMENTS = (
    ("tt", "typical", 3.30, 27),
    ("ff_cold", "ff", 3.63, -40),
    ("ff_hot", "ff", 2.97, 125),
    ("ss_hot", "ss", 2.97, 125),
    ("ss_cold", "ss", 3.63, -40),
)
PMOS_MULTIPLIERS = (1, 2, 3, 4, 6, 8)
WRITE_WIDTH_PS = 200.0
RAIL_HEADROOM_V = 0.25
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
REQUIRED = {
    "e_clk_rise", "e_clkb_fall", "e_clk_fall", "e_clkb_rise",
    "o_clk_rise", "o_clkb_fall", "o_clk_fall", "o_clkb_rise",
    "e_clk_high", "e_clk_low", "e_clkb_high", "e_clkb_low",
    "o_clk_high", "o_clk_low", "o_clkb_high", "o_clkb_low",
    "e_q_diff", "o_q_diff", "supply_current",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fill(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    missing = sorted(set(re.findall(r"@[A-Z0-9_]+@", template)))
    if missing:
        raise ValueError(f"unfilled testbench tokens: {missing}")
    return template


def candidate_source(base: str, multiplier: int) -> str:
    needle = "XCLK CLKB CLK VDD VSS ccb_inv WP=12u WN=5u MP=16 MN=16"
    replacement = (
        "XCLK CLKB CLK VDD VSS ccb_inv WP=12u WN=5u "
        f"MP={16 * multiplier} MN=16")
    if base.count(needle) != 1:
        raise ValueError("capture-bridge final-stage identity changed")
    return base.replace(needle, replacement)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--capture-pex", required=True, type=Path)
    parser.add_argument("--capture-physical", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    args.work.mkdir(parents=True, exist_ok=True)
    physical = json.loads(args.capture_physical.read_text())
    if physical.get("result") != "pass" or physical.get("pex_sha256") != digest(args.capture_pex):
        raise SystemExit("capture PEX does not match a passing physical record")
    bridge_path = args.source / "capture_clock_bridge" / "capture_clock_bridge.spice"
    template_path = args.source / "capture_clock_bridge" / "capture_clock_bridge_tb.spice.in"
    base = bridge_path.read_text()
    template = template_path.read_text()

    def run_case(spec: tuple[tuple[str, str, float, int], int]) -> dict[str, object]:
        (name, corner, vdd, temp), multiplier = spec
        root = args.work / f"{name}_pmosx{multiplier}"
        root.mkdir(parents=True, exist_ok=True)
        candidate = root / "candidate_bridge.spice"
        deck = root / "bridge.spice"
        log = root / "bridge.log"
        candidate.write_text(candidate_source(base, multiplier))
        deck.write_text(fill(template, {
            "MOS_CORNER": corner, "TEMP_C": str(temp), "VDD_V": f"{vdd:.6f}",
            "VMID": f"{vdd / 2:.6f}", "WRITE_WIDTH": f"{WRITE_WIDTH_PS * 1e-12:.12g}",
            "BRIDGE_PATH": str(candidate), "BRIDGE_SUBCKT": "capture_clock_bridge",
            "CAPTURE_PEX": str(args.capture_pex),
        }))
        try:
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=300, check=False)
            returncode = run.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
        observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
        complete = returncode == 0 and REQUIRED <= observed.keys()
        skew = {
            "e_entry_ps": (observed.get("e_clk_rise", 0.0) - observed.get("e_clkb_fall", 0.0)) * 1e12,
            "e_exit_ps": (observed.get("e_clkb_rise", 0.0) - observed.get("e_clk_fall", 0.0)) * 1e12,
            "o_entry_ps": (observed.get("o_clk_rise", 0.0) - observed.get("o_clkb_fall", 0.0)) * 1e12,
            "o_exit_ps": (observed.get("o_clkb_rise", 0.0) - observed.get("o_clk_fall", 0.0)) * 1e12,
        }
        rails = all(observed.get(key, 0.0) >= vdd - RAIL_HEADROOM_V for key in
                    ("e_clk_high", "e_clkb_high", "o_clk_high", "o_clkb_high")) and all(
                        observed.get(key, vdd) <= RAIL_HEADROOM_V for key in
                        ("e_clk_low", "e_clkb_low", "o_clk_low", "o_clkb_low"))
        passed = (complete and rails and all(abs(value) <= 125.0 for value in skew.values())
                  and observed.get("e_q_diff", 0.0) >= 0.5
                  and observed.get("o_q_diff", 0.0) <= -0.5
                  and 0.0 < observed.get("supply_current", 0.0) <= 0.075)
        return {
            "case_id": f"{name}_pmosx{multiplier}", "environment": [corner, vdd, temp],
            "final_clk_pmos_multiplier": multiplier, "complete": complete,
            "observed": observed, "clock_skew_ps": skew,
            "result": "pass" if passed else "fail",
        }

    specs = [(environment, multiplier) for environment in ENVIRONMENTS
             for multiplier in PMOS_MULTIPLIERS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_case, specs))
    qualifying = [multiplier for multiplier in PMOS_MULTIPLIERS
                  if all(case["result"] == "pass" for case in cases
                         if case["final_clk_pmos_multiplier"] == multiplier)]
    output = {
        "schema_version": 1,
        "claim": "pcie_capture_clock_bridge_final_pmos_strength_screen",
        "result": "pass" if qualifying else "fail",
        "case_count": len(cases), "complete_case_count": sum(case["complete"] for case in cases),
        "qualifying_multipliers": qualifying,
        "scope": (
            "schematic bridge with exact extracted capture load and ideal 200-ps WRITE "
            "sources; isolates final pull-up strength only and cannot close the pulse producer"),
        "not_a_claim": [
            "physical_bridge_candidate", "pulse_bridge_lane_closure", "calibrated_pcie_clock_path",
            "routed_parent_closure", "pcie_compliance",
        ],
        "base_bridge_source_sha256": digest(bridge_path),
        "capture_pex_sha256": digest(args.capture_pex),
        "capture_physical_sha256": digest(args.capture_physical),
        "testbench_sha256": digest(template_path), "runner_sha256": digest(Path(__file__)),
        "cases": cases,
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": output["result"], "complete_case_count": output["complete_case_count"],
                      "qualifying_multipliers": qualifying}, sort_keys=True))


if __name__ == "__main__":
    main()
