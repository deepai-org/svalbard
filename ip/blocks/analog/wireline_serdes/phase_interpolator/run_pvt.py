#!/usr/bin/env python3
"""Verify five phase codes across independent GF180 MOS/resistor PVT corners."""

from __future__ import annotations

import argparse
import concurrent.futures
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
CONTROL_CANDIDATES = tuple((code, *pair) for code, pair in enumerate(CONTROL_PAIRS))
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
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--only-mos", choices=MOS_CORNERS)
    parser.add_argument("--only-resistor", choices=RES_CORNERS)
    parser.add_argument("--only-supply", type=float)
    parser.add_argument("--only-temperature", type=int)
    parser.add_argument("--only-common-mode", type=float)
    parser.add_argument("--reuse-complete", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "transient_tb.spice.in").read_text()
    period = 1 / 1.25e9
    specifications = []
    mos_values = (args.only_mos,) if args.only_mos else MOS_CORNERS
    resistor_values = (args.only_resistor,) if args.only_resistor else RES_CORNERS
    supply_values = (args.only_supply,) if args.only_supply is not None else (2.97, 3.30, 3.63)
    temperature_values = ((args.only_temperature,) if args.only_temperature is not None
                          else (-40, 27, 125))
    common_mode_values = ((args.only_common_mode,) if args.only_common_mode is not None
                          else (0.45, 0.50, 0.55))
    for mos in mos_values:
        for resistor in resistor_values:
            for vdd in supply_values:
                for temp in temperature_values:
                    for cm_fraction in common_mode_values:
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
                                "B_P_PHASE_DEG": "270", "B_N_PHASE_DEG": "90",
                                "FREQ_HZ": "1.25g", "CTRL_A_V": f"{ctrl_a:.3f}",
                                "CTRL_B_V": f"{ctrl_b:.3f}", "VBIAS_BUF_V": "1.15",
                                "CLOAD_F": "50f", "TSTEP_S": f"{period / 200:.9g}",
                                "TSTOP_S": f"{6 * period:.9g}",
                                "MEAS_START_S": f"{3 * period:.9g}",
                            }
                            specifications.append((case_id, mos, resistor, vdd, temp,
                                                   cm_fraction, code, ctrl_a, ctrl_b, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        case_id, mos, resistor, vdd, temp, cm_fraction, code, ctrl_a, ctrl_b, values = specification
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        deck_text = instantiate(template, values)
        reusable = (args.reuse_complete and deck.exists() and log.exists()
                    and deck.read_text() == deck_text)
        deck.write_text(deck_text)
        required = {"phase_delay", "b_delay", "diff_high", "diff_low", "output_cm",
                    "supply_current", "duty_high"}
        observed = ({name: float(value) for name, value in MEASURE.findall(log.read_text())}
                    if reusable else {})
        returncode = 0
        if not required <= observed.keys():
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=60, check=False)
            returncode = run.returncode
            observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        complete = returncode == 0 and required <= observed.keys()
        output_peak = max(observed.get("diff_high", 0), -observed.get("diff_low", 0)) / 2
        electrical = (complete
                      and observed["diff_high"] >= 0.20
                      and observed["diff_low"] <= -0.20
                      and abs(observed["diff_high"] + observed["diff_low"]) <= 0.020
                      and observed["output_cm"] - output_peak >= 0.25
                      and observed["output_cm"] + output_peak <= float(vdd) - 0.10
                      and 0.001 <= observed["supply_current"] <= 0.010
                      and abs((observed["duty_high"] % period) - period / 2) <= 10e-12)
        return {"id": case_id, "mos_corner": mos, "res_corner": resistor,
                "supply_v": vdd, "temperature_c": temp,
                "common_mode_fraction": cm_fraction, "code": code,
                "ctrl_a_v": ctrl_a, "ctrl_b_v": ctrl_b, "observed": observed,
                "result": "pass" if electrical else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
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
            selected_indices = [index for _, index, _ in selected]
            valid = (all(a < b for a, b in zip(delays, delays[1:]))
                     and 160e-12 <= span <= 240e-12
                     and 0 <= delays[0] <= 130e-12
                     and abs(span - b_delay) <= 15e-12
                     and all(a < b for a, b in zip(selected_indices, selected_indices[1:]))
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
