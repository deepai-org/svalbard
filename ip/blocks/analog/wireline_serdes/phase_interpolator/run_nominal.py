#!/usr/bin/env python3
"""Sweep phase-interpolator current weights at the nominal process point."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(
    r"^(phase_delay|b_delay|diff_high|diff_low|output_cm|supply_current|duty_high)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)
CONTROL_PAIRS = (
    (1.30, 0.30), (1.30, 0.50), (1.30, 0.65), (1.30, 0.69),
    (1.30, 0.72), (1.30, 0.75), (1.30, 0.775), (1.30, 0.80), (1.30, 0.85),
    (1.30, 0.88), (1.30, 0.90),
    (1.29, 0.93),
    (1.265, 0.975),
    (1.25, 1.00), (1.20, 1.10), (1.15, 1.15), (1.10, 1.20), (1.00, 1.25),
    (0.975, 1.265),
    (0.93, 1.29),
    (0.90, 1.30), (0.88, 1.30), (0.85, 1.30), (0.80, 1.30),
    (0.775, 1.30), (0.75, 1.30), (0.72, 1.30), (0.69, 1.30), (0.65, 1.30),
    (0.50, 1.30), (0.30, 1.30),
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
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "transient_tb.spice.in").read_text()
    period = 1 / 1.25e9
    cases = []
    for index, (ctrl_a, ctrl_b) in enumerate(CONTROL_PAIRS):
        values = {
            "MOS_CORNER": "typical", "RES_CORNER": "res_typical",
            "DUT_INCLUDE": (f".include {args.pex}" if args.pex else
                            ".include /src/phase_interpolator.spice"),
            "DUT_SUBCKT": "phase_interpolator_pex" if args.pex else "phase_interpolator",
            "TEMP_C": "27",
            "VDD_V": "3.30", "VCM_V": "1.65", "INPUT_PEAK_V": "0.20",
            "B_P_PHASE_DEG": "270", "B_N_PHASE_DEG": "90",
            "FREQ_HZ": "1.25g", "CTRL_A_V": f"{ctrl_a:.3f}",
            "CTRL_B_V": f"{ctrl_b:.3f}", "VBIAS_BUF_V": "1.15",
            "CLOAD_F": "50f", "TSTEP_S": f"{period / 200:.9g}",
            "TSTOP_S": f"{6 * period:.9g}", "MEAS_START_S": f"{3 * period:.9g}",
        }
        deck, log = args.work / f"code{index}.spice", args.work / f"code{index}.log"
        deck.write_text(instantiate(template, values))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=60, check=False)
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        required = {"phase_delay", "b_delay", "diff_high", "diff_low", "output_cm",
                    "supply_current", "duty_high"}
        complete = run.returncode == 0 and required <= observed.keys()
        cases.append({"code": index, "ctrl_a_v": ctrl_a, "ctrl_b_v": ctrl_b,
                      "observed": observed, "result": "pass" if complete else "fail"})
    complete_count = sum(case["result"] == "pass" for case in cases)
    result = {"schema_version": 1, "extraction": "full_rc" if args.pex else "schematic",
              "result": "pass" if complete_count == len(cases) else "fail",
              "case_count": len(cases), "complete_case_count": complete_count, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"phase_interpolator nominal: {complete_count}/{len(cases)} complete")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
