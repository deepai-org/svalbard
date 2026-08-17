#!/usr/bin/env python3
"""Verify five phase codes across independent GF180 MOS/resistor PVT corners."""

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
MOS_CORNERS = ("typical", "ff", "ss")
RES_CORNERS = ("res_typical", "res_ff", "res_ss")
CONTROL_CANDIDATES = (
    (0, 1.30, 0.50), (1, 1.30, 0.75), (2, 1.30, 0.80),
    (3, 1.30, 0.85), (4, 1.30, 0.90), (5, 1.25, 1.00),
    (6, 1.20, 1.10), (7, 1.15, 1.15), (8, 1.10, 1.20),
    (9, 1.00, 1.25), (10, 0.90, 1.30), (11, 0.85, 1.30),
    (12, 0.80, 1.30), (13, 0.75, 1.30), (14, 0.50, 1.30),
)
TARGET_FRACTIONS = (0.00, 0.25, 0.50, 0.75, 1.00)


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
    for mos in MOS_CORNERS:
        for resistor in RES_CORNERS:
            for vdd in (2.97, 3.30, 3.63):
                for temp in (-40, 27, 125):
                    for cm_fraction in (0.45, 0.50, 0.55):
                        for code, ctrl_a, ctrl_b in CONTROL_CANDIDATES:
                            case_id = (f"{mos}_{resistor}_{vdd:.2f}_{temp:+d}_cm{cm_fraction:.2f}_c{code}"
                                       .replace("+", "p").replace("-", "m"))
                            values = {
                                "MOS_CORNER": mos, "RES_CORNER": resistor,
                                "DUT_INCLUDE": (f".include {args.pex}" if args.pex else
                                                ".include /src/phase_interpolator.spice"),
                                "DUT_SUBCKT": "phase_interpolator_pex" if args.pex else "phase_interpolator",
                                "TEMP_C": str(temp), "VDD_V": f"{vdd:.2f}",
                                "VCM_V": f"{vdd * cm_fraction:.6f}", "INPUT_PEAK_V": "0.20",
                                "FREQ_HZ": "1.25g", "CTRL_A_V": f"{ctrl_a:.2f}",
                                "CTRL_B_V": f"{ctrl_b:.2f}", "VBIAS_BUF_V": "1.15",
                                "CLOAD_F": "50f", "TSTEP_S": f"{period / 200:.9g}",
                                "TSTOP_S": f"{6 * period:.9g}",
                                "MEAS_START_S": f"{3 * period:.9g}",
                            }
                            deck = args.work / f"{case_id}.spice"
                            log = args.work / f"{case_id}.log"
                            deck.write_text(instantiate(template, values))
                            with log.open("w") as output:
                                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                                     stderr=subprocess.STDOUT, timeout=60, check=False)
                            observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
                            required = {"phase_delay", "b_delay", "diff_high", "diff_low", "output_cm",
                                        "supply_current", "duty_high"}
                            complete = run.returncode == 0 and required <= observed.keys()
                            electrical = (complete
                                          and observed["diff_high"] >= 0.20
                                          and observed["diff_low"] <= -0.20
                                          and abs(observed["diff_high"] + observed["diff_low"]) <= 0.020
                                          and 1.20 <= observed["output_cm"] <= vdd - 0.10
                                          and 0.001 <= observed["supply_current"] <= 0.010
                                          and abs(observed["duty_high"] - period / 2) <= 10e-12)
                            cases.append({"id": case_id, "mos_corner": mos, "res_corner": resistor,
                                          "supply_v": vdd, "temperature_c": temp,
                                          "common_mode_fraction": cm_fraction, "code": code,
                                          "ctrl_a_v": ctrl_a, "ctrl_b_v": ctrl_b,
                                          "observed": observed,
                                          "result": "pass" if electrical else "fail"})
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for case in cases:
        key = (case["mos_corner"], case["res_corner"], case["supply_v"],
               case["temperature_c"], case["common_mode_fraction"])
        groups.setdefault(key, []).append(case)
    evaluated = []
    for key, members in groups.items():
        members.sort(key=lambda case: int(case["code"]))
        valid = (len(members) == len(CONTROL_CANDIDATES)
                 and all(case["result"] == "pass" for case in members))
        metrics: dict[str, object] = {}
        if valid:
            delays = [float(case["observed"]["phase_delay"]) % period for case in members]
            span = delays[-1] - delays[0]
            selected = []
            for fraction in TARGET_FRACTIONS:
                target = delays[0] + fraction * span
                index = min(range(len(members)), key=lambda item: abs(delays[item] - target))
                selected.append((fraction, index, delays[index] - target))
            errors = [entry[2] for entry in selected]
            b_delay = sum(float(case["observed"]["b_delay"]) for case in members) / len(members)
            metrics = {"endpoint_latency_s": delays[0], "span_s": span,
                       "input_quadrature_s": b_delay,
                       "selected_codes": [members[index]["code"] for _, index, _ in selected],
                       "selected_controls_v": [[members[index]["ctrl_a_v"], members[index]["ctrl_b_v"]]
                                               for _, index, _ in selected],
                       "phase_errors_s": errors,
                       "maximum_phase_error_s": max(abs(error) for error in errors)}
            valid = (all(a < b for a, b in zip(delays, delays[1:]))
                     and 160e-12 <= span <= 240e-12
                     and 0 <= delays[0] <= 130e-12
                     and abs(span - b_delay) <= 15e-12
                     and all(a < b for a, b in zip(
                         [index for _, index, _ in selected],
                         [index for _, index, _ in selected][1:]))
                     and all(0 < index < len(members) - 1 for _, index, _ in selected[1:-1])
                     and max(abs(error) for error in errors) <= 8e-12)
        evaluated.append({"group": list(key), "observed": metrics,
                          "result": "pass" if valid else "fail"})
    complete_count = sum(len(case["observed"]) == 7 for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in evaluated)
    passed = complete_count == len(cases) and passing_groups == len(evaluated)
    result = {"schema_version": 1, "extraction": "full_rc" if args.pex else "schematic",
              "result": "pass" if passed else "fail", "case_count": len(cases),
              "complete_case_count": complete_count, "group_count": len(evaluated),
              "passing_group_count": passing_groups, "groups": evaluated, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"phase_interpolator PVT: {complete_count}/{len(cases)} complete; "
          f"{passing_groups}/{len(evaluated)} groups pass")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
