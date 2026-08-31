#!/usr/bin/env python3
"""Run a bounded PVT accuracy probe for a real-IF transmission gate."""
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
CLOCK_TRACK_FRACTION = TRACK_TIME_S / SAMPLE_PERIOD_S
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
    return v0 + (v1 - v0) * (target - t0) / (t1 - t0) if t1 > t0 else math.nan


def crossings(times: list[float], values: list[float], threshold: float,
              rising: bool) -> list[float]:
    result = []
    for t0, t1, v0, v1 in zip(times, times[1:], values, values[1:]):
        matches = v0 < threshold <= v1 if rising else v0 > threshold >= v1
        if matches and t1 > t0 and ((v1 > v0) if rising else (v1 < v0)):
            result.append(t0 + (threshold - v0) * (t1 - t0) / (v1 - v0))
    return result


def finite(*values: float) -> bool:
    return all(math.isfinite(value) for value in values)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dut", type=Path)
    parser.add_argument("--subckt", default="wifi_if_transmission_gate")
    parser.add_argument("--mode", choices=("schematic", "pex"), default="schematic")
    parser.add_argument("--width-scale", type=float, default=1.0)
    parser.add_argument("--sample-rate-hz", type=float, default=SAMPLE_RATE_HZ)
    parser.add_argument("--if-hz", type=float, default=IF_HZ)
    parser.add_argument("--hold-capacitance-f", type=float, default=HOLD_CAPACITANCE_F)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    if not math.isfinite(args.width_scale) or not 0.0 < args.width_scale <= 32.0:
        parser.error("--width-scale must be finite and in (0, 32]")
    if not (math.isfinite(args.sample_rate_hz) and math.isfinite(args.if_hz)
            and args.sample_rate_hz > 0.0 and 0.0 < args.if_hz < args.sample_rate_hz / 2.0):
        parser.error("--if-hz must be positive and below --sample-rate-hz / 2")
    if not math.isfinite(args.hold_capacitance_f) or not 1e-13 <= args.hold_capacitance_f <= 1e-9:
        parser.error("--hold-capacitance-f must be in [100 fF, 1 nF]")
    if args.mode == "pex" and args.width_scale != 1.0:
        parser.error("--width-scale applies only to the schematic source")
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "transmission_gate_tb.spice.in"
    template = template_path.read_text()
    dut = args.dut or args.source / "rf_if_transmission_gate.spice"
    dut_text = dut.read_text()
    sample_period_s = 1.0 / args.sample_rate_hz
    track_time_s = CLOCK_TRACK_FRACTION * sample_period_s
    first_measure_edge_s = max(2.0 * sample_period_s, FIRST_MEASURE_EDGE_S)
    stop_time_s = max(10.0 * sample_period_s, STOP_TIME_S)
    track_lookback_s = min(TRACK_LOOKBACK_S, track_time_s / 5.0)
    hold_measure_delay_s = min(HOLD_MEASURE_DELAY_S, (sample_period_s - track_time_s) / 3.0)
    if args.width_scale != 1.0:
        width = 4.0 * args.width_scale
        dut_text = dut_text.replace("w=4u", f"w={width:g}u")

    def run_case(environment: tuple[str, str, float, int]) -> dict[str, object]:
        name, corner, vdd_v, temperature_c = environment
        case_dir = args.work / name
        case_dir.mkdir(parents=True, exist_ok=True)
        paths = {name: case_dir / f"{name}.dat"
                 for name in ("inp", "inn", "holdp", "holdn", "clk", "clkb")}
        deck = case_dir / "transmission_gate.spice"
        log = case_dir / "transmission_gate.log"
        rendered_dut = case_dir / "dut.spice"
        rendered_dut.write_text(dut_text)
        deck.write_text(fill(template, {
            "MOS_CORNER": corner,
            "DUT_INCLUDE": str(rendered_dut), "DUT_SUBCKT": args.subckt,
            "TEMP_C": str(temperature_c), "VDD_V": f"{vdd_v:.3f}",
            "INPUT_COMMON_MODE_V": f"{INPUT_COMMON_MODE_V:.9g}",
            "INPUT_HALF_PEAK_V": f"{INPUT_HALF_PEAK_V:.9g}", "IF_HZ": f"{args.if_hz:.9g}",
            "INPUT_SOURCE_RESISTANCE_OHM": f"{INPUT_SOURCE_RESISTANCE_OHM:.9g}",
            "CLOCK_SOURCE_RESISTANCE_OHM": f"{CLOCK_SOURCE_RESISTANCE_OHM:.9g}",
            "CLOCK_EDGE_S": f"{CLOCK_EDGE_S:.9g}", "TRACK_TIME_S": f"{track_time_s:.9g}",
            "SAMPLE_PERIOD_S": f"{sample_period_s:.12g}",
            "HOLD_CAPACITANCE_F": f"{args.hold_capacitance_f:.9g}",
            "MAX_STEP_S": f"{MAX_STEP_S:.9g}", "STOP_TIME_S": f"{stop_time_s:.9g}",
            "INP_DATA": str(paths["inp"]), "INN_DATA": str(paths["inn"]),
            "HOLDP_DATA": str(paths["holdp"]), "HOLDN_DATA": str(paths["holdn"]),
            "CLK_DATA": str(paths["clk"]), "CLKB_DATA": str(paths["clkb"]),
        }))
        try:
            with log.open("w") as output:
                process = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                         stderr=subprocess.STDOUT, timeout=480, check=False)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
        waves = {key: waveform(path) if path.exists() else ([], [])
                 for key, path in paths.items()}
        nmos_falls = [time for time in crossings(*waves["clk"], vdd_v / 2.0, False)
                      if time >= first_measure_edge_s]
        pmos_rises = [time for time in crossings(*waves["clkb"], vdd_v / 2.0, True)
                      if time >= first_measure_edge_s]
        observations = []
        for nmos_fall, pmos_rise in zip(nmos_falls, pmos_rises):
            edge = (nmos_fall + pmos_rise) / 2.0
            before, after = edge - track_lookback_s, edge + hold_measure_delay_s
            values = (
                interpolate(*waves["inp"], before), interpolate(*waves["inn"], before),
                interpolate(*waves["holdp"], before), interpolate(*waves["holdn"], before),
                interpolate(*waves["inp"], edge), interpolate(*waves["inn"], edge),
                interpolate(*waves["holdp"], after), interpolate(*waves["holdn"], after),
            )
            if not finite(*values):
                continue
            inp_before, inn_before, holdp_before, holdn_before, inp_edge, inn_edge, holdp_after, holdn_after = values
            track_error = (holdp_before - holdn_before) - (inp_before - inn_before)
            aperture_error = (holdp_after - holdn_after) - (inp_edge - inn_edge)
            observations.append({
                "nmos_clock_fall_s": nmos_fall, "pmos_clock_rise_s": pmos_rise,
                "control_midpoint_skew_s": pmos_rise - nmos_fall,
                "track_error_abs_v": abs(track_error),
                "aperture_and_hold_error_abs_v": abs(aperture_error),
            })
        complete = returncode == 0 and len(waves["clk"][0]) >= 10_000 and len(observations) >= 6
        worst_track = max((item["track_error_abs_v"] for item in observations), default=math.nan)
        worst_hold = max((item["aperture_and_hold_error_abs_v"] for item in observations), default=math.nan)
        worst_skew = max((abs(item["control_midpoint_skew_s"]) for item in observations), default=math.nan)
        return {
            "case_id": name, "environment": [corner, vdd_v, temperature_c],
            "returncode": returncode, "wave_sample_count": len(waves["clk"][0]),
            "measurement_count": len(observations), "complete": complete,
            "worst_track_error_abs_v": worst_track,
            "worst_aperture_and_hold_error_abs_v": worst_hold,
            "worst_control_midpoint_skew_s": worst_skew,
            "result": "pass" if complete and worst_track <= ACCURACY_LIMIT_V and worst_hold <= ACCURACY_LIMIT_V else "fail",
            "observations": observations,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        cases = list(pool.map(run_case, ENVIRONMENTS))
    complete = all(case["complete"] is True for case in cases)
    passed = complete and all(case["result"] == "pass" for case in cases)
    output = {
        "schema_version": 1,
        "claim": "wifi_real_if_transmission_gate_12bit_accuracy_probe",
        "simulation_boundary": args.mode, "result": "pass" if passed else "fail",
        "device_width_scale": args.width_scale,
        "probe_complete": complete, "case_count": len(cases),
        "complete_case_count": sum(case["complete"] is True for case in cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "declared_boundary": {
            "differential_full_scale_peak_v": DIFFERENTIAL_FULL_SCALE_PEAK_V,
            "input_common_mode_v": INPUT_COMMON_MODE_V, "if_hz": args.if_hz,
            "sample_rate_hz": args.sample_rate_hz, "track_time_s": track_time_s,
            "hold_capacitance_per_leg_f": args.hold_capacitance_f,
            "input_source_resistance_ohm": INPUT_SOURCE_RESISTANCE_OHM,
            "clock_source_resistance_ohm": CLOCK_SOURCE_RESISTANCE_OHM,
            "bits": BITS, "lsb_v": LSB_V, "accuracy_limit_v": ACCURACY_LIMIT_V,
            "measurement": "differential tracking 200 ps before and aperture/hold 100 ps after the mean NMOS-off/PMOS-off extracted clock midpoint",
        },
        "measurement_status": "five-corner deterministic transient topology probe; noise, mismatch, jitter, IF buffer, ADC and ENOB are not included",
        "not_claimed": ["adc_enob", "thermal_noise", "mismatch_yield", "clock_jitter_tolerance", "implemented_if_buffer", "integrated_wifi_receiver"],
        "dut_sha256": digest(dut), "scaled_dut_sha256": hashlib.sha256(dut_text.encode()).hexdigest(),
        "schematic_source_sha256": digest(args.source / "rf_if_transmission_gate.spice"),
        "testbench_sha256": digest(template_path), "runner_sha256": digest(Path(__file__)), "cases": cases,
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": output["result"], "complete_case_count": output["complete_case_count"], "passing_case_count": output["passing_case_count"], "worst_aperture_and_hold_error_v": max((case["worst_aperture_and_hold_error_abs_v"] for case in cases if math.isfinite(case["worst_aperture_and_hold_error_abs_v"])), default=None)}, sort_keys=True))
    if not complete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
