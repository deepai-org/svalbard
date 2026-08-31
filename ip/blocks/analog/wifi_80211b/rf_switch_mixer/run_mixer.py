#!/usr/bin/env python3
"""Screen physical or schematic external-LO mixer conversion at 2.4 GHz."""
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
RF_HZ = 2.4e9
LO_HZ = 2.3e9
IF_HZ = RF_HZ - LO_HZ
INPUT_PEAK_V = 10e-3
WINDOW_START_S = 40e-9
WINDOW_END_S = 80e-9


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


def waveform(path: Path) -> list[tuple[float, float]]:
    rows = []
    for line in path.read_text().splitlines():
        try:
            values = [float(field) for field in line.split()]
        except ValueError:
            continue
        if len(values) >= 2:
            rows.append((values[0], values[1]))
    return rows


def sinusoid_peak(samples: list[tuple[float, float]], frequency_hz: float) -> float:
    points = [(time_s, value) for time_s, value in samples
              if WINDOW_START_S <= time_s <= WINDOW_END_S]
    if len(points) < 3:
        return math.nan
    integral = 0j
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        e0 = complex(math.cos(-2.0 * math.pi * frequency_hz * t0),
                     math.sin(-2.0 * math.pi * frequency_hz * t0))
        e1 = complex(math.cos(-2.0 * math.pi * frequency_hz * t1),
                     math.sin(-2.0 * math.pi * frequency_hz * t1))
        integral += 0.5 * (v0 * e0 + v1 * e1) * (t1 - t0)
    return 2.0 * abs(integral) / (WINDOW_END_S - WINDOW_START_S)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "mixer_tb.spice.in"
    template = template_path.read_text()
    dut = args.pex or args.source / "mixer.spice"
    subckt = "wifi_rf_switch_mixer_pex" if args.pex else "wifi_rf_switch_mixer"

    def run_case(environment: tuple[str, str, float, int]) -> dict[str, object]:
        name, corner, lo_high_v, temperature_c = environment
        deck = args.work / f"{name}.spice"
        log = args.work / f"{name}.log"
        data = args.work / f"{name}.dat"
        deck.write_text(fill(template, {
            "MOS_CORNER": corner,
            "DUT_INCLUDE": str(dut),
            "DUT_SUBCKT": subckt,
            "TEMP_C": str(temperature_c),
            "LO_HIGH_V": f"{lo_high_v:.2f}",
            "WAVE_DATA": str(data),
        }))
        try:
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=300,
                                     check=False)
            returncode = run.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
        samples = waveform(data) if data.exists() else []
        if_peak_v = sinusoid_peak(samples, IF_HZ)
        conversion_gain = (if_peak_v / INPUT_PEAK_V
                           if math.isfinite(if_peak_v) else math.nan)
        complete = (returncode == 0 and len(samples) >= 1_000
                    and math.isfinite(if_peak_v) and if_peak_v > 0.0
                    and math.isfinite(conversion_gain) and conversion_gain > 0.0)
        return {
            "case_id": name,
            "environment": [corner, lo_high_v, temperature_c],
            "sample_count": len(samples),
            "if_peak_v": if_peak_v,
            "conversion_gain_v_per_v": conversion_gain,
            "conversion_gain_db": (20.0 * math.log10(conversion_gain)
                                   if conversion_gain > 0.0 else math.nan),
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
        "claim": ("wifi_2p4g_external_lo_switch_mixer_full_rc_conversion_screen"
                  if args.pex else "wifi_2p4g_external_lo_switch_mixer_schematic_conversion_screen"),
        "result": "pass" if all(case["result"] == "pass" for case in cases) else "fail",
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "rf_hz": RF_HZ,
        "external_lo_hz": LO_HZ,
        "intermediate_frequency_hz": IF_HZ,
        "rf_input_peak_v": INPUT_PEAK_V,
        "measurement_status": (
            "external-LO compact-model transient conversion screen; not a qualified "
            "mixer noise, linearity, isolation, I/Q, or receiver performance claim"
        ),
        "boundary": "external_50ohm_rf_source_complementary_lo_and_differential_if_load",
        "unavailable_obligations": [
            "rf_model_qualification", "mixer_noise_figure", "iip3_and_compression",
            "lo_rf_if_isolation", "i_q_balance", "on_die_lo_generation",
            "if_filter_and_baseband", "package_antenna_and_matching_s_parameters",
        ],
        "cases": cases,
        "source_sha256": digest(args.source / "mixer.spice"),
        "testbench_sha256": digest(template_path),
        "runner_sha256": digest(Path(__file__)),
    }
    if args.pex:
        result["pex_sha256"] = digest(args.pex)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": result["result"],
        "worst_conversion_gain_db": min(
            (case["conversion_gain_db"] for case in cases
             if math.isfinite(case["conversion_gain_db"])), default=None),
    }, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
