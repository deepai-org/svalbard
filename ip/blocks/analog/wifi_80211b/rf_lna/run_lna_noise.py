#!/usr/bin/env python3
"""Measure a bounded 2.4 GHz PEX noise screen for the staged Wi-Fi LNA."""
from __future__ import annotations

import argparse
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
RF_CENTER_HZ = 2.4e9
SOURCE_RESISTANCE_OHM = 50.0
BOLTZMANN_J_PER_K = 1.380649e-23


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


def numeric_rows(path: Path) -> list[list[float]]:
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append([float(field) for field in line.split()])
        except ValueError:
            continue
    return rows


def nearest_complex(rows: list[list[float]], frequency_hz: float) -> tuple[float, float]:
    usable = [(row[0], abs(complex(row[1], row[2])))
              for row in rows if len(row) >= 3]
    if not usable:
        return math.nan, math.nan
    return min(usable, key=lambda item: abs(item[0] - frequency_hz))


def nearest_real(rows: list[list[float]], frequency_hz: float) -> tuple[float, float]:
    usable = [(row[0], abs(row[1])) for row in rows if len(row) >= 2]
    if not usable:
        return math.nan, math.nan
    return min(usable, key=lambda item: abs(item[0] - frequency_hz))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bias-v", type=float, default=1.50)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    if not 0.0 < args.bias_v < 3.3:
        parser.error("--bias-v must be between 0 and 3.3 V")
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "lna_noise_tb.spice.in"
    template = template_path.read_text()

    def run_case(environment: tuple[str, str, float, int]) -> dict[str, object]:
        name, corner, vdd, temperature_c = environment
        stem = f"{name}_b{args.bias_v:.2f}"
        deck = args.work / f"{stem}.spice"
        log = args.work / f"{stem}.log"
        ac_data = args.work / f"{stem}-ac.dat"
        noise_data = args.work / f"{stem}-noise.dat"
        deck.write_text(fill(template, {
            "MOS_CORNER": corner,
            "DUT_INCLUDE": str(args.pex),
            "DUT_SUBCKT": "wifi_lna_cs_core_pex",
            "TEMP_C": str(temperature_c),
            "VDD_V": f"{vdd:.2f}",
            "VBIAS_V": f"{args.bias_v:.2f}",
            "AC_DATA": str(ac_data),
            "NOISE_DATA": str(noise_data),
        }))
        try:
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=120,
                                     check=False)
            returncode = run.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
        ac_frequency, gain = nearest_complex(
            numeric_rows(ac_data) if ac_data.exists() else [], RF_CENTER_HZ)
        noise_frequency, output_noise = nearest_real(
            numeric_rows(noise_data) if noise_data.exists() else [], RF_CENTER_HZ)
        source_noise = math.sqrt(
            4.0 * BOLTZMANN_J_PER_K * (temperature_c + 273.15)
            * SOURCE_RESISTANCE_OHM)
        denominator = gain * source_noise
        noise_factor = ((output_noise / denominator) ** 2
                        if math.isfinite(denominator) and denominator > 0.0
                        else math.nan)
        noise_figure_db = (10.0 * math.log10(noise_factor)
                           if math.isfinite(noise_factor) and noise_factor > 0.0
                           else math.nan)
        complete = (returncode == 0 and math.isfinite(gain) and gain > 0.0
                    and math.isfinite(output_noise) and output_noise > 0.0
                    and math.isfinite(noise_figure_db))
        return {
            "case_id": stem,
            "environment": [corner, vdd, temperature_c],
            "bias_v": args.bias_v,
            "ac_frequency_hz": ac_frequency,
            "noise_frequency_hz": noise_frequency,
            "signal_gain_v_per_v": gain,
            "output_noise_density_v_per_sqrt_hz": output_noise,
            "source_thermal_noise_density_v_per_sqrt_hz": source_noise,
            "estimated_noise_factor": noise_factor,
            "estimated_noise_figure_db": noise_figure_db,
            "complete": complete,
            "result": "pass" if complete else "fail",
        }

    if args.jobs == 1:
        cases = [run_case(environment) for environment in ENVIRONMENTS]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            cases = list(pool.map(run_case, ENVIRONMENTS))
    result = {
        "schema_version": 1,
        "claim": "wifi_2p4g_external_passive_lna_core_full_rc_noise_screen",
        "result": "pass" if all(case["result"] == "pass" for case in cases) else "fail",
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "rf_center_hz": RF_CENTER_HZ,
        "external_common_bias_v": args.bias_v,
        "source_resistance_ohm": SOURCE_RESISTANCE_OHM,
        "measurement_status": (
            "lumped full-RC PEX compact-model narrowband screen; estimated noise "
            "figure is bench-relative and is not RF-model qualification or receiver sensitivity"
        ),
        "boundary": "external_50ohm_source_matching_degeneration_load_and_mixer_input",
        "unavailable_obligations": [
            "provider_qualified_rf_noise_model", "on_die_passive_q_and_inductance",
            "package_antenna_and_matching_s_parameters", "receiver_noise_figure",
            "blocker_tolerance", "linearity", "conversion_gain", "sensitivity",
        ],
        "cases": cases,
        "source_sha256": digest(args.source / "lna_cs_core.spice"),
        "pex_sha256": digest(args.pex),
        "testbench_sha256": digest(template_path),
        "runner_sha256": digest(Path(__file__)),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": result["result"],
        "worst_estimated_noise_figure_db": max(
            (case["estimated_noise_figure_db"] for case in cases
             if math.isfinite(case["estimated_noise_figure_db"])), default=None),
    }, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
