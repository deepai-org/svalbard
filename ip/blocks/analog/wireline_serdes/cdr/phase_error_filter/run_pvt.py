#!/usr/bin/env python3
"""Calibrate the dual-interleave CML phase-error combiner over representative PVT."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27, 0.70),
    ("ff", "res_ff", 2.97, -40, 0.60), ("ff", "res_ss", 2.97, 125, 0.80),
    ("ff", "res_typical", 3.63, -40, 0.80), ("ff", "res_ff", 3.63, 125, 0.60),
    ("ss", "res_ss", 2.97, -40, 0.80), ("ss", "res_ff", 2.97, 125, 0.60),
    ("ss", "res_typical", 3.63, -40, 0.60), ("ss", "res_ss", 3.63, 125, 0.80),
)
BIAS_CODES = tuple(round(0.50 + 0.05 * index, 2) for index in range(12))
STATES = (
    (0, 0, 0, 0),  # neutral
    (1, 0, 0, 0),  # one early
    (1, 0, 1, 0),  # two early
    (1, 1, 1, 1),  # neutral
    (0, 1, 0, 0),  # one late
    (0, 1, 0, 1),  # two late
    (1, 0, 0, 1),  # mixed interleaves
)
SCALAR = re.compile(
    r"^(neutral0|early_one|early_two|neutral1|late_one|late_two|mixed|"
    r"output_cm|supply_current)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def logic_pwl(signal: int, positive: bool, common_mode: float, amplitude: float) -> str:
    edge = 20e-12
    values = [state[signal] for state in STATES]
    level = lambda bit: common_mode + (amplitude if bit == positive else -amplitude)
    points = [(0.0, level(values[0]))]
    for index, bit in enumerate(values[1:], start=1):
        if bit == values[index - 1]:
            continue
        center = index * 2e-9
        points.extend(((center - edge / 2, level(values[index - 1])),
                       (center + edge / 2, level(bit))))
    points.append((14e-9, level(values[-1])))
    return " ".join(f"{time:.12g} {voltage:.6f}" for time, voltage in points)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout-s", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    dut = args.pex if args.pex else args.source / "phase_error_filter.spice"
    dut_hash = hashlib.sha256(dut.read_bytes()).hexdigest()
    template = (args.source / "transient_tb.spice.in").read_text()
    cases = []
    for mos, res, vdd, temp, cm_fraction in ENVIRONMENTS:
        cm = vdd * cm_fraction
        for bias in BIAS_CODES:
            case_id = f"{mos}_{res}_{vdd:.2f}_{temp:+d}_cm{cm_fraction:.2f}_b{bias:.2f}"
            case_id = case_id.replace("+", "p").replace("-", "m").replace(".", "p")
            values = {
                "DUT_SHA256": dut_hash, "DUT_PATH": str(dut),
                "DUT_SUBCKT": "cml_phase_error_filter_pex" if args.pex else "cml_phase_error_filter",
                "MOS_CORNER": mos, "RES_CORNER": res, "VDD_V": f"{vdd:.2f}",
                "TEMP_C": str(temp), "VBIAS_V": f"{bias:.2f}",
            }
            for signal, name in enumerate(("E0", "L0", "E1", "L1")):
                values[f"{name}P_PWL"] = logic_pwl(signal, True, cm, 0.15)
                values[f"{name}N_PWL"] = logic_pwl(signal, False, cm, 0.15)
            cases.append((case_id, mos, res, vdd, temp, cm_fraction, bias, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        case_id, mos, res, vdd, temp, cm_fraction, bias, values = specification
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, values))
        with log.open("w") as output:
            try:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=args.timeout_s,
                                     check=False)
                return_code = run.returncode
            except subprocess.TimeoutExpired:
                return_code = 124
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        complete = return_code == 0 and len(observed) == 9
        one = min(observed.get("early_one", -99), -observed.get("late_one", 99))
        two = min(observed.get("early_two", -99), -observed.get("late_two", 99))
        neutral = max(abs(observed.get(name, 99)) for name in ("neutral0", "neutral1", "mixed"))
        cm_value = observed.get("output_cm", 0.0)
        current = observed.get("supply_current", 0.0)
        passed = (complete and one >= 0.075 and two >= 0.15 and neutral <= 0.025
                  and 0.35 <= cm_value <= vdd - 0.20 and 0.0001 <= current <= 0.015)
        return {
            "id": case_id, "environment": [mos, res, vdd, temp, cm_fraction],
            "bias_v": bias, "complete": complete, "one_error_margin_v": one,
            "two_error_margin_v": two, "neutral_error_v": neutral,
            "output_common_mode_v": cm_value, "supply_current_a": current,
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        results = list(executor.map(simulate, cases))
    groups = []
    for environment in (list(item) for item in ENVIRONMENTS):
        members = [case for case in results if case["environment"] == environment]
        passing = [case for case in members if case["result"] == "pass"]
        selected = max(passing, key=lambda case: min(case["one_error_margin_v"],
                                                       case["two_error_margin_v"] / 2),
                       default=None)
        groups.append({
            "environment": environment, "passing_bias_v": [case["bias_v"] for case in passing],
            "selected_bias_v": selected["bias_v"] if selected else None,
            "selected_one_error_margin_v": selected["one_error_margin_v"] if selected else None,
            "selected_two_error_margin_v": selected["two_error_margin_v"] if selected else None,
            "result": "pass" if selected else "fail",
        })
    complete_count = sum(case["complete"] for case in results)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    result = {
        "schema_version": 1, "dut_sha256": dut_hash,
        "mode": "extracted" if args.pex else "schematic",
        "result": "pass" if complete_count == len(results) and passing_groups == len(groups) else "fail",
        "case_count": len(results), "complete_case_count": complete_count,
        "group_count": len(groups), "passing_group_count": passing_groups,
        "cases": results, "groups": groups,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"phase-error filter: {complete_count}/{len(results)} complete; "
          f"{passing_groups}/{len(groups)} environments calibrate")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
