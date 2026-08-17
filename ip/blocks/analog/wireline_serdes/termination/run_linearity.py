#!/usr/bin/env python3
"""Check extracted termination large-signal resistance at calibrated PVT codes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(r"^rdiff_dc\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
SWINGS = (-0.6, -0.3, 0.1, 0.3, 0.6)


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
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "linearity_tb.spice.in").read_text()
    calibration = json.loads(args.calibration.read_text())
    cases = []
    for group in calibration["calibrated_groups"]:
        selected = group.get("selected_case")
        if not selected:
            cases.append({"group": group["group"], "result": "fail", "reason": "uncalibrated"})
            continue
        mos, resistor, vdd, temp, cm_fraction = group["group"]
        enabled = int(selected["enabled_branches"])
        observed = {}
        complete = True
        for swing in SWINGS:
            case_id = (f"{mos}_{resistor}_{float(vdd):.2f}_{int(temp):+d}_"
                       f"cm{float(cm_fraction):.2f}_c{enabled}_v{swing:+.1f}")
            case_id = case_id.replace("+", "p").replace("-", "m")
            values = {"MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
                      "PEX_FILE": str(args.pex.resolve()), "VDD_V": f"{float(vdd):.2f}",
                      "TEMP_C": str(int(temp)), "VCM_V": f"{float(vdd) * float(cm_fraction):.6f}",
                      "VTEST_V": f"{swing:.3f}",
                      **{f"B{index}_V": "0" if index < enabled else f"{float(vdd):.2f}"
                         for index in range(7)}}
            deck = args.work / f"{case_id}.spice"
            log = args.work / f"{case_id}.log"
            deck.write_text(instantiate(template, values))
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=60, check=False)
            match = MEASURE.search(log.read_text())
            if run.returncode != 0 or not match:
                complete = False
            else:
                observed[f"{swing:+.1f}"] = float(match.group(1))
        resistances = list(observed.values())
        spread = ((max(resistances) - min(resistances)) / resistances[SWINGS.index(0.1)]
                  if complete else float("inf"))
        passed = complete and spread <= 0.10
        cases.append({"group": group["group"], "enabled_branches": enabled,
                      "observed_ohm": observed, "relative_spread": spread,
                      "result": "pass" if passed else "fail"})
    passed_count = sum(case["result"] == "pass" for case in cases)
    result = {"schema_version": 1, "extraction": "full_rc", "swings_v": list(SWINGS),
              "maximum_relative_spread": 0.10, "case_count": len(cases),
              "passing_case_count": passed_count,
              "result": "pass" if passed_count == len(cases) else "fail", "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"termination extracted linearity: {passed_count}/{len(cases)} groups pass")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
