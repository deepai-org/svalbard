#!/usr/bin/env python3
"""Run a bounded two-tone diagnostic on the extracted Wi-Fi receive parent.

It deliberately reports, rather than promises, the response to one fixed
25-MHz-offset 40-dB-amplitude aggressor.  The GF180 public compact model,
lumped PEX, external match and external LO make this a reproducible diagnostic
only; calibrated RF data is still required before calling it blocker tolerance.
"""
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
RF_DESIRED_HZ = 2.4e9
RF_BLOCKER_HZ = 2.425e9
LO_HZ = 2.3e9
IF_DESIRED_HZ = RF_DESIRED_HZ - LO_HZ
IF_BLOCKER_HZ = RF_BLOCKER_HZ - LO_HZ
DESIRED_PEAK_V = 1e-3
BLOCKER_PEAK_V = 100e-3
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


def db_ratio(numerator: float, denominator: float) -> float:
    if not (math.isfinite(numerator) and math.isfinite(denominator)
            and numerator > 0.0 and denominator > 0.0):
        return math.nan
    return 20.0 * math.log10(numerator / denominator)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "parent_blocker_tb.spice.in"
    template = template_path.read_text()

    def run_tone(environment: tuple[str, str, float, int], label: str,
                 blocker_peak_v: float) -> dict[str, object]:
        name, corner, vdd_v, temperature_c = environment
        deck = args.work / f"{name}-{label}.spice"
        log = args.work / f"{name}-{label}.log"
        data = args.work / f"{name}-{label}.dat"
        deck.write_text(fill(template, {
            "MOS_CORNER": corner,
            "DUT_INCLUDE": str(args.pex),
            "DUT_SUBCKT": "wifi_rx_external_lo_parent_pex",
            "TEMP_C": str(temperature_c),
            "VDD_V": f"{vdd_v:.2f}",
            "LO_HIGH_V": f"{vdd_v:.2f}",
            "DESIRED_PEAK_V": f"{DESIRED_PEAK_V:.9g}",
            "BLOCKER_PEAK_V": f"{blocker_peak_v:.9g}",
            "WAVE_DATA": str(data),
        }))
        try:
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=600,
                                     check=False)
            returncode = run.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
        samples = waveform(data) if data.exists() else []
        desired_peak_v = sinusoid_peak(samples, IF_DESIRED_HZ)
        blocker_if_peak_v = sinusoid_peak(samples, IF_BLOCKER_HZ)
        complete = (returncode == 0 and len(samples) >= 1_000
                    and math.isfinite(desired_peak_v) and desired_peak_v > 0.0
                    and math.isfinite(blocker_if_peak_v))
        return {
            "sample_count": len(samples),
            "desired_if_peak_v": desired_peak_v,
            "blocker_if_peak_v": blocker_if_peak_v,
            "complete": complete,
            "result": "pass" if complete else "fail",
        }

    def run_case(environment: tuple[str, str, float, int]) -> dict[str, object]:
        reference = run_tone(environment, "reference", 0.0)
        with_blocker = run_tone(environment, "blocker", BLOCKER_PEAK_V)
        desired_retention_db = db_ratio(with_blocker["desired_if_peak_v"],
                                        reference["desired_if_peak_v"])
        blocker_to_desired_db = db_ratio(with_blocker["blocker_if_peak_v"],
                                         with_blocker["desired_if_peak_v"])
        name, corner, vdd_v, temperature_c = environment
        complete = (reference["complete"] is True and with_blocker["complete"] is True
                    and math.isfinite(desired_retention_db)
                    and math.isfinite(blocker_to_desired_db))
        return {
            "case_id": name,
            "environment": [corner, vdd_v, temperature_c],
            "reference": reference,
            "with_blocker": with_blocker,
            "desired_retention_db": desired_retention_db,
            "blocker_to_desired_if_ratio_db": blocker_to_desired_db,
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
        "claim": "wifi_2p4g_routed_parent_fixed_two_tone_diagnostic",
        "result": "pass" if all(case["result"] == "pass" for case in cases) else "fail",
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "rf_desired_hz": RF_DESIRED_HZ,
        "rf_blocker_hz": RF_BLOCKER_HZ,
        "external_lo_hz": LO_HZ,
        "if_desired_hz": IF_DESIRED_HZ,
        "if_blocker_hz": IF_BLOCKER_HZ,
        "desired_input_peak_v": DESIRED_PEAK_V,
        "blocker_input_peak_v": BLOCKER_PEAK_V,
        "blocker_to_desired_input_ratio_db": 40.0,
        "external_common_lna_bias_v": 1.5,
        "measurement_status": (
            "fixed two-tone full-RC PEX compact-model diagnostic with external passive "
            "and LO boundary; reports response change only, not blocker tolerance"
        ),
        "boundary": "external_50ohm_source_bias_drain_load_lo_and_differential_if_load",
        "not_claimed": [
            "80211_blocker_requirement", "receiver_noise_figure", "iip3_and_compression",
            "lo_rf_if_isolation", "i_q_balance", "rf_model_qualification",
            "package_antenna_and_matching_s_parameters", "receiver_sensitivity",
        ],
        "cases": cases,
        "source_sha256": {
            "parent": digest(args.source / "rf_rx_external_lo_parent.spice"),
            "lna": digest(args.source.parent / "rf_lna" / "lna_cs_core.spice"),
            "mixer": digest(args.source.parent / "rf_switch_mixer" / "mixer.spice"),
        },
        "testbench_sha256": digest(template_path),
        "runner_sha256": digest(Path(__file__)),
        "pex_sha256": digest(args.pex),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": result["result"],
        "worst_desired_retention_db": min(
            (case["desired_retention_db"] for case in cases
             if math.isfinite(case["desired_retention_db"])), default=None),
    }, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
