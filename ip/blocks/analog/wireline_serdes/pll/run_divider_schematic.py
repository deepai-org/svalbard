#!/usr/bin/env python3
"""Screen the static-CML divide-by-two across PVT and realizable bias values."""
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
BIASES_V = (0.70, 0.80, 0.90, 1.00, 1.10)
LOAD_LENGTHS_UM = (5.0, 7.5, 10.0, 12.5)
MEASUREMENTS = (
    "startup_time", "period_early", "period_late", "high_time",
    "diff_high", "diff_low", "output_cm", "supply_current",
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
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / (
        "divider_extracted_tb.spice.in" if args.pex else "divider_tb.spice.in"
    )
    schematic_path = args.source / "divider.spice"
    template = template_path.read_text()
    pattern = re.compile(
        rf"^({'|'.join(MEASUREMENTS)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
    )
    load_lengths = (7.5,) if args.pex else LOAD_LENGTHS_UM
    specifications = [
        (mos, resistor, supply, temperature, bias, load_length)
        for mos, resistor, supply, temperature in ENVIRONMENTS
        for bias in BIASES_V
        for load_length in load_lengths
    ]

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        mos, resistor, supply, temperature, bias, load_length = specification
        case_id = (
            f"{mos}_{resistor}_{float(supply):.2f}_{int(temperature):+d}_"
            f"b{float(bias):.2f}_r{float(load_length):.1f}"
        ).replace("+", "p").replace("-", "m").replace(".", "p")
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
            "TEMP_C": str(temperature), "VDD_V": f"{float(supply):.2f}",
            "VBIAS_V": f"{float(bias):.2f}",
            "CLOCK_CM_V": f"{0.70 * float(supply):.6f}",
            "CLOCK_PEAK_V": "0.45",
            "LOAD_L_UM": f"{float(load_length):.1f}",
            "PEX_PATH": str(args.pex) if args.pex else "",
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=120, check=False,
            )
        observed = {name: float(value) for name, value in pattern.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(MEASUREMENTS)
        period = observed.get("period_late", 0.0)
        frequency = 1.0 / period if period > 0 else 0.0
        drift = (
            abs(period - observed.get("period_early", 0.0)) / period
            if period > 0 and observed.get("period_early", 0.0) > 0 else 1.0
        )
        duty = abs(observed.get("high_time", 0.0)) / period if period > 0 else 0.0
        passed = (
            complete and 600e6 <= frequency <= 650e6 and drift <= 0.01
            and 0.45 <= duty <= 0.55
            and observed["startup_time"] <= 6e-9
            and observed["diff_high"] >= 0.15 and observed["diff_low"] <= -0.15
            and 0.4 <= observed["output_cm"] <= float(supply)
            and 0.0001 <= observed["supply_current"] <= 0.025
        )
        return {
            "id": case_id,
            "environment": [mos, resistor, supply, temperature],
            "bias_v": bias,
            "load_length_um": load_length,
            "complete": complete,
            "observed": observed,
            "frequency_hz": frequency,
            "period_drift_fraction": drift,
            "duty_cycle": duty,
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    load_candidates = []
    for load_length in load_lengths:
        calibration = []
        for environment in ENVIRONMENTS:
            members = [
                case for case in cases
                if tuple(case["environment"]) == environment
                and float(case["load_length_um"]) == load_length
            ]
            passing = [case for case in members if case["result"] == "pass"]
            selected = min(
                passing,
                key=lambda case: (abs(float(case["bias_v"]) - 0.90),
                                  abs(float(case["frequency_hz"]) - 625e6)),
            ) if passing else None
            calibration.append({
                "environment": list(environment),
                "candidate_count": len(members),
                "passing_candidate_count": len(passing),
                "selected_bias_v": selected["bias_v"] if selected else None,
                "selected_frequency_hz": selected["frequency_hz"] if selected else None,
                "result": "pass" if selected else "fail",
            })
        environment_index(calibration)
        load_candidates.append({
            "load_length_um": load_length,
            "passing_environment_count": sum(
                item["result"] == "pass" for item in calibration
            ),
            "calibration": calibration,
            "result": "pass" if all(item["result"] == "pass" for item in calibration)
            else "fail",
        })
    passing_loads = [item for item in load_candidates if item["result"] == "pass"]
    selected_load = min(passing_loads, key=lambda item: item["load_length_um"]) \
        if passing_loads else None
    passed = selected_load is not None
    result = {
        "schema_version": 1,
        "claim": (
            "extracted_static_cml_divide_by_two_pvt_bias_screen"
            if args.pex else "schematic_static_cml_divide_by_two_pvt_bias_screen"
        ),
        "extraction": "full_rc" if args.pex else "schematic",
        "input_frequency_hz": 1.25e9,
        "output_frequency_band_hz": [600e6, 650e6],
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "selected_load_length_um": selected_load["load_length_um"] if selected_load else None,
        "passing_environment_count": selected_load["passing_environment_count"]
        if selected_load else 0,
        "calibration": selected_load["calibration"] if selected_load else [],
        "load_candidates": load_candidates,
        "cases": cases,
        "schematic_source_sha256": sha256_file(schematic_path),
        "pex_sha256": sha256_file(args.pex) if args.pex else None,
        "testbench_source_sha256": sha256_file(template_path),
        "simulation_source_sha256": sha256_file(Path(__file__)),
        "shared_evidence_source_sha256": sha256_file(SERDES_ROOT / "analog_evidence.py"),
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"CML divider schematic: {result['passing_case_count']}/{result['case_count']} cases; "
        f"{result['passing_environment_count']}/5 env"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
