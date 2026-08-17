#!/usr/bin/env python3
"""Measure integrated differential receiver noise at nominal calibrated settings."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(r"^(onoise_total|inoise_total)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "noise_tb.spice.in").read_text()
    calibration = json.loads(args.calibration.read_text())
    cases = []
    for high_bw in (False, True):
        match = next((entry for entry in calibration["calibrated_groups"]
                      if entry["group"] == ["typical", "res_typical", 3.3, 27, 0.5, high_bw]), None)
        selected = match.get("selected_case") if match else None
        if not selected:
            cases.append({"high_bandwidth": high_bw, "result": "fail", "reason": "uncalibrated"})
            continue
        values = {
            "MOS_CORNER": "typical", "RES_CORNER": "res_typical",
            "DUT_INCLUDE": f".include {args.pex}" if args.pex else ".include /src/serdes_rx.spice",
            "DUT_SUBCKT": "serdes_rx_pex" if args.pex else "serdes_rx",
            "TEMP_C": "27", "VDD_V": "3.30", "VCM_V": "1.65",
            "VBIAS_V": f"{float(selected['bias_v']):.2f}",
            "BW_CODE_V": "0" if high_bw else "3.30",
        }
        case_id = f"nominal_bw{int(high_bw)}"
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, values))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=120, check=False)
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        passed = (run.returncode == 0 and {"onoise_total", "inoise_total"} <= observed.keys()
                  and 0 < observed["inoise_total"] <= 0.005)
        cases.append({"high_bandwidth": high_bw, "bias_v": selected["bias_v"],
                      "frequency_hz": [1e6, 20e9], "observed": observed,
                      "result": "pass" if passed else "fail"})
    passing = sum(case["result"] == "pass" for case in cases)
    result = {"schema_version": 1, "extraction": "full_rc" if args.pex else "schematic",
              "result": "pass" if passing == len(cases) else "fail",
              "case_count": len(cases), "passing_case_count": passing, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"serdes_rx noise: {passing}/{len(cases)} cases pass")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
