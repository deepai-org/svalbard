#!/usr/bin/env python3
"""Screen the half-rate serializer while it drives the real TX input devices."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

SERDES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERDES_ROOT))
from analog_evidence import environment_index, sha256_file  # noqa: E402

ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27),
    ("ff", "res_ff", 3.63, -40),
    ("ff", "res_ss", 2.97, 125),
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
)
SERIALIZER_BIASES_V = (
    0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30, 1.40, 1.50,
)
LOAD_LENGTHS_UM = (5.0, 7.5, 10.0, 12.5)
MEASUREMENTS = (
    "ser_high", "ser_low", "ser_cm_avg", "tx_high", "tx_low",
    "ser_period", "ser_high_time", "rise_delay", "fall_delay",
    "serializer_current", "tx_current",
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", template)))
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--rate", type=float, default=1.25e9)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    if args.rate not in (1.25e9, 2.5e9):
        parser.error("--rate must be 1.25e9 or 2.5e9")
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "serializer" / "composed_tb.spice.in"
    template = template_path.read_text()
    pattern = re.compile(
        rf"^({'|'.join(MEASUREMENTS)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
    )
    period = 2.0 / args.rate
    load_lengths = (7.5,) if args.pex else LOAD_LENGTHS_UM
    specifications = [
        (*environment, bias, load)
        for environment in ENVIRONMENTS
        for bias in SERIALIZER_BIASES_V
        for load in load_lengths
    ]

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        mos, resistor, supply, temperature, bias, load = specification
        case_id = (
            f"{mos}_{resistor}_{float(supply):.2f}_{int(temperature):+d}_"
            f"b{float(bias):.2f}_r{float(load):.1f}"
        ).replace("+", "p").replace("-", "m").replace(".", "p")
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
            "TEMP_C": str(temperature), "VDD_V": f"{float(supply):.2f}",
            "SER_BIAS_V": f"{float(bias):.2f}", "TX_BIAS_V": "1.10",
            "LOAD_L_UM": f"{float(load):.1f}",
            "HALF_PERIOD": f"{period / 2:.12g}", "PERIOD": f"{period:.12g}",
            "SERIALIZER_INCLUDE": str(args.pex) if args.pex else "/src/serializer/serializer.spice",
            "SERIALIZER_CELL": "cml_serializer_2to1_pex" if args.pex else "cml_serializer_2to1",
            "SERIALIZER_PARAMS": "" if args.pex else f"params: LOAD_L={float(load):.1f}u",
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=120, check=False,
            )
        observed = {name: float(value) for name, value in pattern.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(MEASUREMENTS)
        measured_period = observed.get("ser_period", 0.0)
        # ngspice returns a negative interval when the requested falling edge
        # precedes the selected rising edge in this 50% alternating pattern.
        duty = abs(observed.get("ser_high_time", 0.0)) / measured_period if measured_period > 0 else 0.0
        period_error = abs(measured_period - period) / period if measured_period > 0 else 1.0
        delay_skew = abs(observed.get("rise_delay", 0.0) - observed.get("fall_delay", 0.0))
        passed = (
            complete and period_error <= 0.02 and 0.45 <= duty <= 0.55
            and observed["ser_high"] >= 0.50 and observed["ser_low"] <= -0.50
            and observed["tx_high"] >= 0.30 and observed["tx_low"] <= -0.30
            and 0.8 <= observed["ser_cm_avg"] <= float(supply)
            and observed["rise_delay"] <= period / 4
            and observed["fall_delay"] <= period / 4
            and delay_skew <= period / 10
            and 0.0001 <= observed["serializer_current"] <= 0.020
            and 0.0001 <= observed["tx_current"] <= 0.020
        )
        return {
            "id": case_id, "environment": [mos, resistor, supply, temperature],
            "serializer_bias_v": bias, "load_length_um": load,
            "complete": complete, "observed": observed,
            "period_error_fraction": period_error, "duty_cycle": duty,
            "delay_skew_s": delay_skew, "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    candidates = []
    for load in load_lengths:
        calibration = []
        for environment in ENVIRONMENTS:
            members = [case for case in cases if tuple(case["environment"]) == environment and case["load_length_um"] == load]
            passing = [case for case in members if case["result"] == "pass"]
            selected = min(passing, key=lambda case: abs(case["serializer_bias_v"] - 0.9)) if passing else None
            calibration.append({
                "environment": list(environment),
                "passing_candidate_count": len(passing),
                "selected_bias_v": selected["serializer_bias_v"] if selected else None,
                "result": "pass" if selected else "fail",
            })
        environment_index(calibration)
        candidates.append({
            "load_length_um": load,
            "passing_environment_count": sum(item["result"] == "pass" for item in calibration),
            "calibration": calibration,
            "result": "pass" if all(item["result"] == "pass" for item in calibration) else "fail",
        })
    passing_candidates = [candidate for candidate in candidates if candidate["result"] == "pass"]
    # Prefer the central 7.5 um load over either rail-to-rail overdrive or the
    # smallest extracted swing.  Area is secondary at this integration gate.
    selected = min(passing_candidates, key=lambda candidate: abs(candidate["load_length_um"] - 7.5)) if passing_candidates else None
    result = {
        "schema_version": 1,
        "claim": ("extracted_half_rate_serializer_drives_transistor_level_tx"
                  if args.pex else "schematic_half_rate_serializer_drives_transistor_level_tx"),
        "extraction": "full_rc" if args.pex else "schematic",
        "serial_rate_hz": args.rate,
        "half_rate_clock_hz": args.rate / 2,
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "selected_load_length_um": selected["load_length_um"] if selected else None,
        "passing_environment_count": selected["passing_environment_count"] if selected else 0,
        "calibration": selected["calibration"] if selected else [],
        "load_candidates": candidates, "cases": cases,
        "serializer_source_sha256": sha256_file(args.source / "serializer" / "serializer.spice"),
        "pex_sha256": sha256_file(args.pex) if args.pex else None,
        "tx_source_sha256": sha256_file(args.source / "serdes_tx" / "serdes_tx.spice"),
        "testbench_source_sha256": sha256_file(template_path),
        "simulation_source_sha256": sha256_file(Path(__file__)),
        "result": "pass" if selected else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"Serializer+TX: {result['passing_case_count']}/{result['case_count']} cases; {result['passing_environment_count']}/5 env")
    if not selected:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
