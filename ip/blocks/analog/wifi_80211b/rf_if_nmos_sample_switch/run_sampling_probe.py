#!/usr/bin/env python3
"""Run the bounded full-RC accuracy probe for the Wi-Fi NMOS sample switch.

The result intentionally distinguishes a complete physical measurement from a
passing 12-bit sampling interface.  It contains no thermal-noise, mismatch,
clock-jitter, ADC, or IF-buffer claim; those require later dedicated evidence.
"""
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
SAMPLE_RATE_HZ = 320e6
SAMPLE_PERIOD_S = 1.0 / SAMPLE_RATE_HZ
TRACK_TIME_S = 1.45e-9
CLOCK_EDGE_S = 20e-12
IF_HZ = 100e6
INPUT_COMMON_MODE_V = 1.65
DIFFERENTIAL_FULL_SCALE_PEAK_V = 0.25
INPUT_HALF_PEAK_V = DIFFERENTIAL_FULL_SCALE_PEAK_V / 2.0
HOLD_CAPACITANCE_F = 5e-12
INPUT_SOURCE_RESISTANCE_OHM = 10.0
CLOCK_SOURCE_RESISTANCE_OHM = 10.0
MAX_STEP_S = 2e-12
STOP_TIME_S = 60e-9
FIRST_MEASURE_EDGE_S = 20e-9
TRACK_LOOKBACK_S = 0.20e-9
HOLD_MEASURE_DELAY_S = 0.10e-9
BITS = 12
LSB_V = 2.0 * DIFFERENTIAL_FULL_SCALE_PEAK_V / (2 ** BITS)
ACCURACY_LIMIT_V = LSB_V / 4.0


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
            values.append(row[1])
    return times, values


def interpolate(times: list[float], values: list[float], target: float) -> float:
    index = bisect.bisect_left(times, target)
    if index == 0 or index >= len(times):
        return math.nan
    t0, t1 = times[index - 1], times[index]
    v0, v1 = values[index - 1], values[index]
    if not (t1 > t0):
        return math.nan
    return v0 + (v1 - v0) * (target - t0) / (t1 - t0)


def falling_crossings(times: list[float], values: list[float], threshold: float) -> list[float]:
    crossings = []
    for t0, t1, v0, v1 in zip(times, times[1:], values, values[1:]):
        if v0 > threshold >= v1 and t1 > t0 and v0 > v1:
            crossings.append(t0 + (threshold - v0) * (t1 - t0) / (v1 - v0))
    return crossings


def finite(*values: float) -> bool:
    return all(math.isfinite(value) for value in values)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--physical", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--mode", choices=("schematic", "pex"), default="pex")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "sample_switch_tb.spice.in"
    template = template_path.read_text()
    physical = json.loads(args.physical.read_text())
    dut = (args.source / "rf_if_nmos_sample_switch.spice"
           if args.mode == "schematic" else args.pex)
    dut_subckt = ("wifi_if_nmos_sample_switch" if args.mode == "schematic"
                  else "wifi_if_nmos_sample_switch_pex")

    def run_case(environment: tuple[str, str, float, int]) -> dict[str, object]:
        name, corner, vdd_v, temperature_c = environment
        case_dir = args.work / name
        case_dir.mkdir(parents=True, exist_ok=True)
        data_paths = {key: case_dir / f"{key}.dat"
                      for key in ("inp", "inn", "holdp", "holdn", "clk")}
        deck = case_dir / "sample_switch.spice"
        log = case_dir / "sample_switch.log"
        deck.write_text(fill(template, {
            "MOS_CORNER": corner,
            "DUT_INCLUDE": str(dut),
            "DUT_SUBCKT": dut_subckt,
            "TEMP_C": str(temperature_c),
            "VDD_V": f"{vdd_v:.3f}",
            "INPUT_COMMON_MODE_V": f"{INPUT_COMMON_MODE_V:.9g}",
            "INPUT_HALF_PEAK_V": f"{INPUT_HALF_PEAK_V:.9g}",
            "IF_HZ": f"{IF_HZ:.9g}",
            "INPUT_SOURCE_RESISTANCE_OHM": f"{INPUT_SOURCE_RESISTANCE_OHM:.9g}",
            "CLOCK_SOURCE_RESISTANCE_OHM": f"{CLOCK_SOURCE_RESISTANCE_OHM:.9g}",
            "CLOCK_EDGE_S": f"{CLOCK_EDGE_S:.9g}",
            "TRACK_TIME_S": f"{TRACK_TIME_S:.9g}",
            "SAMPLE_PERIOD_S": f"{SAMPLE_PERIOD_S:.12g}",
            "HOLD_CAPACITANCE_F": f"{HOLD_CAPACITANCE_F:.9g}",
            "MAX_STEP_S": f"{MAX_STEP_S:.9g}",
            "STOP_TIME_S": f"{STOP_TIME_S:.9g}",
            "INP_DATA": str(data_paths["inp"]),
            "INN_DATA": str(data_paths["inn"]),
            "HOLDP_DATA": str(data_paths["holdp"]),
            "HOLDN_DATA": str(data_paths["holdn"]),
            "CLK_DATA": str(data_paths["clk"]),
        }))
        try:
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=480,
                                     check=False)
            returncode = run.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
        waves = {key: waveform(path) if path.exists() else ([], [])
                 for key, path in data_paths.items()}
        clk_t, clk_v = waves["clk"]
        edges = [edge for edge in falling_crossings(clk_t, clk_v, vdd_v / 2.0)
                 if edge >= FIRST_MEASURE_EDGE_S]
        observations = []
        for edge in edges:
            before = edge - TRACK_LOOKBACK_S
            after = edge + HOLD_MEASURE_DELAY_S
            inp_before = interpolate(*waves["inp"], before)
            inn_before = interpolate(*waves["inn"], before)
            holdp_before = interpolate(*waves["holdp"], before)
            holdn_before = interpolate(*waves["holdn"], before)
            inp_edge = interpolate(*waves["inp"], edge)
            inn_edge = interpolate(*waves["inn"], edge)
            holdp_after = interpolate(*waves["holdp"], after)
            holdn_after = interpolate(*waves["holdn"], after)
            values = (inp_before, inn_before, holdp_before, holdn_before,
                      inp_edge, inn_edge, holdp_after, holdn_after)
            if not finite(*values):
                continue
            track_error = ((holdp_before - holdn_before)
                           - (inp_before - inn_before))
            aperture_and_hold_error = ((holdp_after - holdn_after)
                                       - (inp_edge - inn_edge))
            observations.append({
                "clock_fall_s": edge,
                "track_error_v": track_error,
                "aperture_and_hold_error_v": aperture_and_hold_error,
                "track_error_abs_v": abs(track_error),
                "aperture_and_hold_error_abs_v": abs(aperture_and_hold_error),
            })
        complete = (returncode == 0 and len(clk_t) >= 10_000
                    and len(observations) >= 6)
        worst_track = max((item["track_error_abs_v"] for item in observations),
                          default=math.nan)
        worst_hold = max((item["aperture_and_hold_error_abs_v"]
                          for item in observations), default=math.nan)
        result = "pass" if (complete and worst_track <= ACCURACY_LIMIT_V
                             and worst_hold <= ACCURACY_LIMIT_V) else "fail"
        return {
            "case_id": name,
            "environment": [corner, vdd_v, temperature_c],
            "returncode": returncode,
            "wave_sample_count": len(clk_t),
            "falling_clock_edge_count": len(edges),
            "measurement_count": len(observations),
            "worst_track_error_abs_v": worst_track,
            "worst_aperture_and_hold_error_abs_v": worst_hold,
            "complete": complete,
            "result": result,
            "observations": observations,
        }

    if args.jobs == 1:
        cases = [run_case(environment) for environment in ENVIRONMENTS]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            cases = list(pool.map(run_case, ENVIRONMENTS))
    complete = all(case["complete"] is True for case in cases)
    passed = complete and all(case["result"] == "pass" for case in cases)
    result = {
        "schema_version": 1,
        "claim": "wifi_real_if_differential_nmos_sampling_switch_12bit_accuracy_probe",
        "simulation_boundary": args.mode,
        "result": "pass" if passed else "fail",
        "probe_complete": complete,
        "case_count": len(cases),
        "complete_case_count": sum(case["complete"] is True for case in cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "declared_boundary": {
            "differential_full_scale_peak_v": DIFFERENTIAL_FULL_SCALE_PEAK_V,
            "input_common_mode_v": INPUT_COMMON_MODE_V,
            "if_hz": IF_HZ,
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "track_time_s": TRACK_TIME_S,
            "hold_capacitance_per_leg_f": HOLD_CAPACITANCE_F,
            "input_source_resistance_ohm": INPUT_SOURCE_RESISTANCE_OHM,
            "clock_source_resistance_ohm": CLOCK_SOURCE_RESISTANCE_OHM,
            "bits": BITS,
            "lsb_v": LSB_V,
            "accuracy_limit_v": ACCURACY_LIMIT_V,
            "measurement": (
                "absolute differential tracking error 200 ps before actual extracted "
                "clock-midpoint fall and absolute aperture/hold error 100 ps after it"),
        },
        "measurement_status": (
            "five-corner deterministic full-RC extracted NMOS-switch transient probe; "
            "not thermal-noise, mismatch, clock-jitter, IF-buffer, ADC, or ENOB evidence"),
        "not_claimed": [
            "12bit_sampling_accuracy", "adc_enob", "thermal_noise", "mismatch_yield",
            "clock_jitter_tolerance", "implemented_if_buffer", "integrated_wifi_receiver",
        ],
        "physical_result_sha256": digest(args.physical),
        "dut_sha256": digest(dut),
        "schematic_source_sha256": digest(args.source / "rf_if_nmos_sample_switch.spice"),
        "testbench_sha256": digest(template_path),
        "runner_sha256": digest(Path(__file__)),
        "cases": cases,
    }
    if args.mode == "pex":
        result["pex_sha256"] = digest(args.pex)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    summary = {
        "result": result["result"],
        "complete_case_count": result["complete_case_count"],
        "passing_case_count": result["passing_case_count"],
        "worst_aperture_and_hold_error_v": max(
            (case["worst_aperture_and_hold_error_abs_v"] for case in cases
             if math.isfinite(case["worst_aperture_and_hold_error_abs_v"])),
            default=None),
    }
    print(json.dumps(summary, sort_keys=True))
    if not complete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
