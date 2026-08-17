#!/usr/bin/env python3
"""Run minimum-input transient checks at every calibrated receiver corner."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(
    r"^(diff_high|diff_low|output_cm|supply_current|delay_rise|delay_fall)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


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
    template = (args.source / "transient_tb.spice.in").read_text()
    calibration = json.loads(args.calibration.read_text())
    cases = []
    for entry in calibration["calibrated_groups"]:
        selected = entry.get("selected_case")
        if not selected:
            cases.append({"group": entry["group"], "result": "fail", "reason": "uncalibrated"})
            continue
        mos, resistor, vdd, temp, cm_fraction, high_bw = entry["group"]
        vcm = float(vdd) * float(cm_fraction)
        period = 0.8e-9 if high_bw else 1.6e-9
        edge = 20e-12
        tstop = 5 * period
        input_peak = 0.10
        values = {"MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
                  "DUT_INCLUDE": (f".include {args.pex}" if args.pex else
                                  ".include /src/serdes_rx.spice"),
                  "DUT_SUBCKT": "serdes_rx_pex" if args.pex else "serdes_rx",
                  "TEMP_C": str(int(temp)), "VDD_V": f"{float(vdd):.2f}",
                  "VCM_V": f"{vcm:.9g}", "INP_LOW": f"{vcm - input_peak / 2:.9g}",
                  "INP_HIGH": f"{vcm + input_peak / 2:.9g}",
                  "VBIAS_V": f"{float(selected['bias_v']):.2f}",
                  "BW_CODE_V": "0" if high_bw else f"{float(vdd):.2f}", "CLOAD_F": "50f",
                  "EDGE_S": f"{edge:.9g}", "HALF_HIGH_S": f"{period / 2 - edge:.9g}",
                  "PERIOD_S": f"{period:.9g}", "TSTEP_S": f"{period / 250:.9g}",
                  "TSTOP_S": f"{tstop:.9g}", "MEAS_START_S": f"{2 * period:.9g}",
                  "HIGH_START_S": f"{4 * period + 0.18 * period:.9g}",
                  "HIGH_END_S": f"{4 * period + 0.32 * period:.9g}",
                  "LOW_START_S": f"{4 * period + 0.68 * period:.9g}",
                  "LOW_END_S": f"{4 * period + 0.82 * period:.9g}"}
        case_id = (f"{mos}_{resistor}_{float(vdd):.2f}_{int(temp):+d}_cm{float(cm_fraction):.2f}_"
                   f"bw{int(bool(high_bw))}_b{float(selected['bias_v']):.2f}")
        case_id = case_id.replace("+", "p").replace("-", "m")
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, values))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=60, check=False)
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        required = {"diff_high", "diff_low", "output_cm", "supply_current", "delay_rise", "delay_fall"}
        passed = (run.returncode == 0 and required <= observed.keys()
                  and observed.get("diff_high", 0.0) >= 0.040
                  and observed.get("diff_low", 0.0) <= -0.040
                  and abs(abs(observed.get("diff_high", 0.0)) - abs(observed.get("diff_low", 0.0))) <= 0.015
                  and max(observed.get("delay_rise", 1.0), observed.get("delay_fall", 1.0)) <= 150e-12)
        cases.append({"group": entry["group"], "bias_v": selected["bias_v"],
                      "input_differential_peak_v": input_peak, "observed": observed,
                      "result": "pass" if passed else "fail"})
    passing = sum(case["result"] == "pass" for case in cases)
    result = {"schema_version": 1, "extraction": "full_rc" if args.pex else "schematic",
              "result": "pass" if passing == len(cases) else "fail",
              "case_count": len(cases), "passing_case_count": passing, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"serdes_rx transient PVT: {passing}/{len(cases)} cases pass")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
