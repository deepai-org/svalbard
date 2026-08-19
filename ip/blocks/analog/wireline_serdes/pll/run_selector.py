#!/usr/bin/env python3
"""Qualify the extracted phase interpolator as a break-before-make selector."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import statistics
import subprocess
from pathlib import Path

SCALAR = re.compile(
    r"^(diff_high|diff_low|output_cm|supply_current|pre_high|pre_low|gap_high|gap_low|"
    r"post_high|post_low|current_pre|current_gap|current_post|current_max)\s*=\s*"
    r"([-+0-9.eE]+)", re.MULTILINE,
)
ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27),
    ("ff", "res_ff", 3.63, -40),
    ("ff", "res_ss", 2.97, 125),
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
)
BIAS_CODES = (
    (1.20, 1.05), (1.25, 1.10), (1.30, 1.15), (1.35, 1.20),
    (1.40, 1.25), (1.45, 1.30), (1.50, 1.35),
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return template


def waveform(path: Path) -> tuple[list[float], list[float]]:
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                row = [float(field) for field in line.split()]
            except ValueError:
                continue
            if len(row) >= 2:
                rows.append(row)
    return [row[0] for row in rows], [row[1] for row in rows]


def rising_crossings(times: list[float], values: list[float], start: float, stop: float) -> list[float]:
    result = []
    for index in range(1, len(times)):
        if times[index] < start or times[index] > stop:
            continue
        if values[index - 1] < 0 <= values[index] and values[index] != values[index - 1]:
            fraction = -values[index - 1] / (values[index] - values[index - 1])
            result.append(times[index - 1] + fraction * (times[index] - times[index - 1]))
    return result


def clock_metrics(times: list[float], values: list[float], start: float, stop: float,
                  expected_hz: float) -> dict[str, float]:
    crossings = rising_crossings(times, values, start, stop)
    periods = [upper - lower for lower, upper in zip(crossings, crossings[1:])]
    mean_period = statistics.mean(periods) if periods else math.inf
    jitter = [period - mean_period for period in periods]
    return {
        "crossing_count": len(crossings),
        "frequency_hz": 1.0 / mean_period if math.isfinite(mean_period) else 0.0,
        "frequency_error_fraction": (abs(1.0 / mean_period - expected_hz) / expected_hz
                                     if math.isfinite(mean_period) else 1.0),
        "cycle_jitter_pp_s": max(jitter) - min(jitter) if jitter else math.inf,
        "cycle_jitter_rms_s": (math.sqrt(statistics.mean(value * value for value in jitter))
                               if jitter else math.inf),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    endpoint_template = (args.source / "selector_endpoint_tb.spice.in").read_text()
    specs = [(environment, code, active_bias, buffer_bias, cm_fraction, selected)
             for environment in ENVIRONMENTS
             for code, (active_bias, buffer_bias) in enumerate(BIAS_CODES)
             for cm_fraction in (0.55, 0.72, 0.86)
             for selected in ("a", "b")]

    def simulate(spec: tuple[tuple[str, str, float, int], int, float, float, float, str]) -> dict[str, object]:
        ((mos, resistor, supply, temperature), code, active_bias,
         buffer_bias, cm_fraction, selected) = spec
        case_id = (f"{mos}_{resistor}_{supply:.2f}_{temperature:+d}_cm{cm_fraction:.2f}_{selected}"
                   f"_code{code}"
                   .replace("+", "p").replace("-", "m").replace(".", "p"))
        deck, log, wave = (args.work / f"{case_id}.{suffix}"
                           for suffix in ("spice", "log", "dat"))
        deck.write_text(instantiate(endpoint_template, {
            "MOS_CORNER": mos, "RES_CORNER": resistor, "TEMP_C": str(temperature),
            "PEX_PATH": str(args.pex), "VDD_V": f"{supply:.2f}",
            "VCM_V": f"{supply * cm_fraction:.6f}", "INPUT_PEAK_V": "0.20",
            "A_FREQ_HZ": "2.5g" if selected == "a" else "2.0g",
            "B_FREQ_HZ": "2.5g" if selected == "b" else "2.0g",
            "CTRL_A_V": f"{active_bias:.2f}" if selected == "a" else "0",
            "CTRL_B_V": f"{active_bias:.2f}" if selected == "b" else "0",
            "VBIAS_BUF_V": f"{buffer_bias:.2f}", "WAVE_PATH": str(wave),
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=120, check=False)
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        times, values = waveform(wave)
        timing = clock_metrics(times, values, 15e-9, 25e-9, 2.5e9)
        complete = run.returncode == 0 and len(observed) == 4 and len(times) > 100
        passed = (complete and observed["diff_high"] >= 0.20
                  and observed["diff_low"] <= -0.20
                  and 0.001 <= observed["supply_current"] <= 0.015
                  and timing["frequency_error_fraction"] <= 0.005
                  and timing["cycle_jitter_pp_s"] <= 10e-12)
        return {
            "id": case_id, "environment": [mos, resistor, supply, temperature],
            "bias_code": code, "active_tail_bias_v": active_bias,
            "buffer_tail_bias_v": buffer_bias,
            "input_common_mode_fraction": cm_fraction, "selected_input": selected,
            "observed": observed, "timing": timing,
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        endpoint_cases = list(executor.map(simulate, specs))

    calibration = []
    for environment in ENVIRONMENTS:
        valid_codes = []
        for code in range(len(BIAS_CODES)):
            members = [case for case in endpoint_cases
                       if tuple(case["environment"]) == environment and case["bias_code"] == code]
            if len(members) == 6 and all(case["result"] == "pass" for case in members):
                valid_codes.append(code)
        selected_code = valid_codes[len(valid_codes) // 2] if valid_codes else None
        interior = selected_code is not None and 0 < selected_code < len(BIAS_CODES) - 1
        calibration.append({
            "environment": list(environment), "valid_bias_codes": valid_codes,
            "selected_bias_code": selected_code,
            "selected_active_tail_bias_v": (BIAS_CODES[selected_code][0]
                                            if selected_code is not None else None),
            "selected_buffer_tail_bias_v": (BIAS_CODES[selected_code][1]
                                            if selected_code is not None else None),
            "result": "pass" if interior else "fail",
        })

    handoff_template = (args.source / "selector_handoff_tb.spice.in").read_text()
    handoff_dir = args.work / "handoff"
    handoff_dir.mkdir(exist_ok=True)
    deck, log, wave = handoff_dir / "handoff.spice", handoff_dir / "handoff.log", handoff_dir / "handoff.dat"
    deck.write_text(instantiate(handoff_template, {"PEX_PATH": str(args.pex),
                                                    "WAVE_PATH": str(wave)}))
    with log.open("w") as output:
        run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                             stderr=subprocess.STDOUT, timeout=120, check=False)
    observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
    times, values = waveform(wave)
    before = clock_metrics(times, values, 4e-9, 7.5e-9, 2.4e9)
    after = clock_metrics(times, values, 12e-9, 20e-9, 2.6e9)
    complete = run.returncode == 0 and len(observed) == 10 and len(times) > 100
    gap_peak = max(abs(observed.get("gap_high", math.inf)),
                   abs(observed.get("gap_low", -math.inf)))
    handoff_pass = (complete and observed["pre_high"] >= 0.20 and observed["pre_low"] <= -0.20
                    and observed["post_high"] >= 0.20 and observed["post_low"] <= -0.20
                    and gap_peak <= 0.05 and observed["current_gap"] <= 0.0001
                    and observed["current_max"] <= 0.020
                    and before["frequency_error_fraction"] <= 0.005
                    and after["frequency_error_fraction"] <= 0.005
                    and before["cycle_jitter_pp_s"] <= 10e-12
                    and after["cycle_jitter_pp_s"] <= 10e-12)
    handoff = {
        "dead_time_s": 0.95e-9, "both_inputs_toggling": True,
        "controls_overlap": False, "observed": observed,
        "gap_differential_peak_v": gap_peak,
        "before": before, "after": after,
        "result": "pass" if handoff_pass else "fail",
    }

    passed = all(group["result"] == "pass" for group in calibration) and handoff_pass
    result = {
        "schema_version": 1,
        "role": "phase_interpolator_as_two_input_break_before_make_clock_selector",
        "pex_sha256": hashlib.sha256(args.pex.read_bytes()).hexdigest(),
        "endpoint_case_count": len(endpoint_cases),
        "passing_endpoint_case_count": sum(case["result"] == "pass" for case in endpoint_cases),
        "bias_codes": [{"code": code, "active_tail_bias_v": values[0],
                        "buffer_tail_bias_v": values[1]}
                       for code, values in enumerate(BIAS_CODES)],
        "calibration": calibration,
        "passing_calibration_group_count": sum(group["result"] == "pass" for group in calibration),
        "handoff": handoff, "cases": endpoint_cases,
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"extracted clock selector: {result['passing_endpoint_case_count']}/"
          f"{result['endpoint_case_count']} raw endpoints; "
          f"calibration={result['passing_calibration_group_count']}/{len(calibration)}; "
          f"handoff={handoff['result']}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
