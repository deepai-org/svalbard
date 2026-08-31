#!/usr/bin/env python3
"""Run the first closed-loop Wi-Fi IF-driver topology screen over public PVT."""

from __future__ import annotations

import argparse
import bisect
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
HOLD_CAPACITANCE_F = 4.2497400827571653e-10
PER_LEG_PEAK_V = 0.125
STEP_TIME_S = 10e-9
TRACK_TIME_S = 1.45e-9
MAX_STEP_S = 1e-12
STOP_TIME_S = 16e-9
ACCURACY_LIMIT_V = 3.0517578125e-05
COMMON_MODE_LIMIT_V = 0.150
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fill(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"@{key}@", value)
    missing = sorted(set(re.findall(r"@[A-Z0-9_]+@", rendered)))
    if missing:
        raise ValueError(f"unfilled testbench tokens: {missing}")
    return rendered


def waveform(path: Path) -> tuple[list[float], list[float]]:
    times: list[float] = []
    values: list[float] = []
    for line in path.read_text().splitlines():
        try:
            row = [float(field) for field in line.split()]
        except ValueError:
            continue
        if len(row) >= 2:
            times.append(row[0])
            values.append(row[-1])
    return times, values


def interpolate(times: list[float], values: list[float], target: float) -> float:
    index = bisect.bisect_left(times, target)
    if index == 0 or index >= len(times):
        return math.nan
    t0, t1 = times[index - 1], times[index]
    v0, v1 = values[index - 1], values[index]
    if not t1 > t0:
        return math.nan
    return v0 + (v1 - v0) * (target - t0) / (t1 - t0)


def tail(path: Path) -> list[str]:
    return path.read_text().splitlines()[-12:]


def measures(path: Path) -> dict[str, float]:
    return {name: float(value) for name, value in MEASURE.findall(path.read_text())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "step_tb.spice.in"
    template = template_path.read_text()
    source = args.source / "wifi_if_inverter_loop_driver.spice"

    def run_case(environment: tuple[str, str, float, int]) -> dict[str, object]:
        name, corner, vdd, temp = environment
        root = args.work / name
        root.mkdir(parents=True, exist_ok=True)
        paths = {node: root / f"{node}.dat" for node in ("inp", "inn", "outp", "outn")}
        deck = root / "driver.spice"
        log = root / "driver.log"
        cm = vdd / 2.0
        deck.write_text(fill(template, {
            "MOS_CORNER": corner, "DUT_INCLUDE": str(source), "TEMP_C": str(temp),
            "VDD_V": f"{vdd:.12g}",
            "INP_INITIAL_V": f"{cm - PER_LEG_PEAK_V:.12g}",
            "INP_FINAL_V": f"{cm + PER_LEG_PEAK_V:.12g}",
            "INN_INITIAL_V": f"{cm + PER_LEG_PEAK_V:.12g}",
            "INN_FINAL_V": f"{cm - PER_LEG_PEAK_V:.12g}",
            "HOLD_CAPACITANCE_F": f"{HOLD_CAPACITANCE_F:.16g}",
            "MAX_STEP_S": f"{MAX_STEP_S:.12g}", "STOP_TIME_S": f"{STOP_TIME_S:.12g}",
            "INP_DATA": str(paths["inp"]), "INN_DATA": str(paths["inn"]),
            "OUTP_DATA": str(paths["outp"]), "OUTN_DATA": str(paths["outn"]),
        }))
        try:
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=480, check=False)
            returncode = run.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
        waves = {node: waveform(path) if path.exists() else ([], [])
                 for node, path in paths.items()}
        measure_time = STEP_TIME_S + TRACK_TIME_S
        values = {node: interpolate(*wave, measure_time) for node, wave in waves.items()}
        input_diff = values["inp"] - values["inn"]
        output_diff = values["outp"] - values["outn"]
        output_cm = (values["outp"] + values["outn"]) / 2.0
        error = output_diff + input_diff
        complete = (returncode == 0 and all(len(wave[0]) >= 10_000
                                             for wave in waves.values())
                    and all(math.isfinite(value) for value in values.values()))
        supply_current_signed = measures(log).get("supply_current_a", math.nan)
        return {
            "case_id": name, "environment": [corner, vdd, temp],
            "returncode": returncode, "log_tail": tail(log),
            "sample_count": min((len(wave[0]) for wave in waves.values()), default=0),
            "measurement_time_s": measure_time,
            "input_differential_v": input_diff,
            "output_differential_v": output_diff,
            "inverting_closed_loop_error_v": error,
            "inverting_closed_loop_error_abs_v": abs(error),
            "output_common_mode_v": output_cm,
            "output_common_mode_error_from_vdd_half_v": abs(output_cm - cm),
            "average_supply_current_draw_a": -supply_current_signed,
            "average_supply_current_signed_a": supply_current_signed,
            "complete": complete,
            "result": ("pass" if complete and abs(error) <= ACCURACY_LIMIT_V
                       and abs(output_cm - cm) <= COMMON_MODE_LIMIT_V else "fail"),
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_case, ENVIRONMENTS))
    complete = all(case["complete"] for case in cases)
    passed = complete and all(case["result"] == "pass" for case in cases)
    output = {
        "schema_version": 1,
        "claim": "wifi_closed_loop_inverter_chain_if_driver_step_screen",
        "result": "pass" if passed else "fail",
        "case_count": len(cases),
        "complete_case_count": sum(case["complete"] for case in cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "declared_boundary": {
            "per_leg_hold_capacitance_f": HOLD_CAPACITANCE_F,
            "per_leg_full_scale_step_v": 2.0 * PER_LEG_PEAK_V,
            "track_time_s": TRACK_TIME_S,
            "inverting_differential_closed_loop_gain": -1.0,
            "accuracy_limit_v": ACCURACY_LIMIT_V,
            "external_input_common_mode": "VDD/2 in each PVT case",
        },
        "scope": (
            "first schematic closed-loop topology screen with discrete tapered CMOS "
            "stages and no extracted layout; direct feedback produces an inverting "
            "differential path"),
        "not_a_claim": [
            "implemented_cmfb", "output_bank_gate_distribution", "loop_stability",
            "physical_layout", "noise", "linearity", "adc_enob",
            "integrated_wifi_receiver",
        ],
        "source_sha256": digest(source), "testbench_sha256": digest(template_path),
        "runner_sha256": digest(Path(__file__)), "cases": cases,
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": output["result"], "complete_case_count": output["complete_case_count"],
        "passing_case_count": output["passing_case_count"],
        "worst_step_error_v": max((case["inverting_closed_loop_error_abs_v"]
                                    for case in cases if math.isfinite(case["inverting_closed_loop_error_abs_v"])), default=None),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
