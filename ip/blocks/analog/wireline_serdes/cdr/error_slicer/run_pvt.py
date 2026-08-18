#!/usr/bin/env python3
"""Calibrate the CML error slicer's dead zone over representative GF180 PVT."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27, 0.80),
    ("ff", "res_ff", 2.97, -40, 0.70), ("ff", "res_ss", 2.97, 125, 0.88),
    ("ff", "res_typical", 3.63, -40, 0.88), ("ff", "res_ff", 3.63, 125, 0.70),
    ("ss", "res_ss", 2.97, -40, 0.88), ("ss", "res_ff", 2.97, 125, 0.70),
    ("ss", "res_typical", 3.63, -40, 0.70), ("ss", "res_ss", 3.63, 125, 0.88),
)
# The first 972-case exploration showed that codes below 0.90/0.65 V never
# improve the limiting slow-MOS/high-supply headroom corner, while that corner
# needs threshold codes above the original 0.95 V ceiling.  Keep the same
# 50 mV resolution and move the bounded search onto the useful hardware range.
MAIN_BIASES = tuple(round(0.90 + 0.05 * index, 2) for index in range(9))
THRESHOLD_BIASES = tuple(round(0.50 + 0.05 * index, 2) for index in range(12))
ERRORS = (0.0, 0.040, 0.150, 0.300, 0.0, -0.040, -0.150, -0.300)
BASE_NAMES = (
    "neutral0_up", "neutral0_down", "pos40_up", "pos40_down",
    "pos150_up", "pos150_down", "pos300_up", "pos300_down",
    "neutral1_up", "neutral1_down", "neg40_up", "neg40_down",
    "neg150_up", "neg150_down", "neg300_up", "neg300_down",
    "output_cm", "supply_current",
)
NAMES = BASE_NAMES + ("up_assert_delay", "down_assert_delay")
SCALAR = re.compile(r"^(" + "|".join(NAMES) + r")\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def error_pwl(positive: bool, common_mode: float) -> str:
    edge = 20e-12
    level = lambda error: common_mode + (error / 2 if positive else -error / 2)
    points = [(0.0, level(ERRORS[0]))]
    for index, error in enumerate(ERRORS[1:], start=1):
        if error == ERRORS[index - 1]:
            continue
        center = index * 2e-9
        points.extend(((center - edge / 2, level(ERRORS[index - 1])),
                       (center + edge / 2, level(error))))
    points.append((16e-9, level(ERRORS[-1])))
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
    dut = args.pex if args.pex else args.source / "error_slicer.spice"
    dut_hash = hashlib.sha256(dut.read_bytes()).hexdigest()
    template = (args.source / "transient_tb.spice.in").read_text()
    cases = []
    for mos, res, vdd, temp, cm_fraction in ENVIRONMENTS:
        common_mode = vdd * cm_fraction
        for main_bias in MAIN_BIASES:
            for threshold_bias in THRESHOLD_BIASES:
                case_id = (f"{mos}_{res}_{vdd:.2f}_{temp:+d}_cm{cm_fraction:.2f}_"
                           f"bm{main_bias:.2f}_bt{threshold_bias:.2f}")
                case_id = case_id.replace("+", "p").replace("-", "m").replace(".", "p")
                values = {
                    "DUT_SHA256": dut_hash, "DUT_PATH": str(dut),
                    "DUT_SUBCKT": "cml_error_slicer_pex" if args.pex else "cml_error_slicer",
                    "MOS_CORNER": mos, "RES_CORNER": res, "VDD_V": f"{vdd:.2f}",
                    "TEMP_C": str(temp), "MAIN_BIAS_V": f"{main_bias:.2f}",
                    "THRESHOLD_BIAS_V": f"{threshold_bias:.2f}",
                    "VREFP_V": f"{common_mode + 0.20:.6f}",
                    "VREFN_V": f"{common_mode - 0.20:.6f}",
                    "ERRP_PWL": error_pwl(True, common_mode),
                    "ERRN_PWL": error_pwl(False, common_mode),
                }
                cases.append((case_id, mos, res, vdd, temp, cm_fraction,
                              main_bias, threshold_bias, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        (case_id, mos, res, vdd, temp, cm_fraction, main_bias,
         threshold_bias, values) = specification
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
        # A legal but nonpassing trim code may never cross zero; ngspice then
        # omits its delay measure.  The run is still complete, while the
        # missing delay remains a deliberate 99 s sentinel and cannot pass.
        complete = return_code == 0 and all(name in observed for name in BASE_NAMES)
        neutral = max(observed.get(name, 99.0) for name in
                      ("neutral0_up", "neutral0_down", "neutral1_up", "neutral1_down",
                       "pos40_up", "pos40_down", "neg40_up", "neg40_down"))
        asserted = min(observed.get("pos150_up", -99.0),
                       observed.get("pos300_up", -99.0),
                       observed.get("neg150_down", -99.0),
                       observed.get("neg300_down", -99.0))
        rejected = max(observed.get("pos150_down", 99.0),
                       observed.get("pos300_down", 99.0),
                       observed.get("neg150_up", 99.0),
                       observed.get("neg300_up", 99.0))
        cm_value = observed.get("output_cm", 0.0)
        current = observed.get("supply_current", 0.0)
        worst_delay = max(observed.get("up_assert_delay", 99.0),
                          observed.get("down_assert_delay", 99.0))
        passed = (complete and neutral <= -0.020 and asserted >= 0.050
                  and rejected <= -0.050 and 0.35 <= cm_value <= vdd - 0.20
                  and 0.0001 <= current <= 0.020 and 0.0 <= worst_delay <= 0.30e-9)
        return {
            "id": case_id, "environment": [mos, res, vdd, temp, cm_fraction],
            "main_bias_v": main_bias, "threshold_bias_v": threshold_bias,
            "complete": complete, "maximum_dead_zone_output_v": neutral,
            "minimum_asserted_output_v": asserted,
            "maximum_rejected_output_v": rejected,
            "output_common_mode_v": cm_value, "supply_current_a": current,
            "worst_assert_delay_s": worst_delay,
            "measurements": observed, "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        results = list(executor.map(simulate, cases))
    groups = []
    for environment in (list(item) for item in ENVIRONMENTS):
        members = [case for case in results if case["environment"] == environment]
        passing = [case for case in members if case["result"] == "pass"]
        interior = [case for case in passing
                    if case["main_bias_v"] not in (MAIN_BIASES[0], MAIN_BIASES[-1])
                    and case["threshold_bias_v"] not in
                    (THRESHOLD_BIASES[0], THRESHOLD_BIASES[-1])]
        selected = max(interior or passing,
                       key=lambda case: min(case["minimum_asserted_output_v"],
                                            -case["maximum_dead_zone_output_v"]),
                       default=None)
        groups.append({
            "environment": environment,
            "passing_codes": [[case["main_bias_v"], case["threshold_bias_v"]]
                              for case in passing],
            "selected_main_bias_v": selected["main_bias_v"] if selected else None,
            "selected_threshold_bias_v": selected["threshold_bias_v"] if selected else None,
            "selected_minimum_asserted_output_v":
                selected["minimum_asserted_output_v"] if selected else None,
            "selected_maximum_dead_zone_output_v":
                selected["maximum_dead_zone_output_v"] if selected else None,
            "selected_worst_assert_delay_s": selected["worst_assert_delay_s"] if selected else None,
            "selected_is_interior": bool(selected and selected in interior),
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
    print(f"error slicer: {complete_count}/{len(results)} complete; "
          f"{passing_groups}/{len(groups)} environments calibrate")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
