#!/usr/bin/env python3
"""Calibrate complete full-RC VCO-band parents across five environments."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

VARIANTS = (
    "center", "fast", "ultra_fast", "slow", "high_gain", "ss_ff", "ss_ss",
    "margin_slow", "margin_fast", "typ_margin_slow", "ss_ff_margin_slow",
    "ss_ff_margin_fast",
)
CONTROLS = (0.78, 0.88, 0.98, 1.08, 1.18, 1.30, 1.40, 1.50)
ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27),
    ("ff", "res_ff", 3.63, -40),
    ("ff", "res_ss", 2.97, 125),
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
)
MEASURE_NAMES = (
    "startup_time", "period", "period_late", "diff_high", "diff_low",
    "output_cm", "supply_current",
)
MEASURE = re.compile(
    rf"^({'|'.join(MEASURE_NAMES)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
)
KICK_RELEASE_S = 1.30e-9


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def merge_intervals(intervals: list[tuple[float, float]]) -> list[list[float]]:
    merged: list[list[float]] = []
    for lower, upper in sorted(intervals):
        if not merged or lower > merged[-1][1]:
            merged.append([lower, upper])
        else:
            merged[-1][1] = max(merged[-1][1], upper)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex-dir", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS))
    parser.add_argument("--target-hz", type=float, default=2.50e9)
    parser.add_argument("--guardband-fraction", type=float, default=0.02)
    parser.add_argument("--claim", default="complete_parent_pex_vco_bank_range_screen")
    parser.add_argument(
        "--qualification", choices=("required_target", "design_guardband"),
        default="design_guardband",
    )
    args = parser.parse_args()
    variants = tuple(args.variants)
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "vco_band_bank_tb.spice.in").read_text()
    specs = [
        (variant, environment, control)
        for variant in variants for environment in ENVIRONMENTS for control in CONTROLS
    ]

    def simulate(spec: tuple[str, tuple[str, str, float, int], float]) -> dict[str, object]:
        variant, (mos, resistor, supply, temperature), control = spec
        cell = f"cml_vco_band_{variant}"
        pex = args.pex_dir / f"{cell}.pex.spice"
        case_id = (
            f"{variant}_{mos}_{resistor}_{supply:.2f}_{temperature:+d}_{control:.2f}"
            .replace("+", "p").replace("-", "m")
        )
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": mos,
            "RES_CORNER": resistor,
            "TEMP_C": str(temperature),
            "VDD_V": f"{supply:.2f}",
            "VCTRL_V": f"{control:.2f}",
            "BAND_PEX_PATH": str(pex),
            "BAND_PEX_SUBCKT": f"{cell}_pex",
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=90, check=False,
            )
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(MEASURE_NAMES)
        frequency = 1.0 / observed["period"] if complete and observed["period"] > 0 else 0.0
        late_frequency = (
            1.0 / observed["period_late"]
            if complete and observed["period_late"] > 0 else 0.0
        )
        drift = abs(frequency - late_frequency) / frequency if frequency else 1.0
        startup_delay = observed.get("startup_time", 0.0) - KICK_RELEASE_S
        passed = (
            complete and drift <= 0.01
            and observed["diff_high"] >= 0.20 and observed["diff_low"] <= -0.20
            and 0.003 <= observed["supply_current"] <= 0.040
            and 0 <= startup_delay <= 10e-9
        )
        return {
            "id": case_id,
            "variant": variant,
            "environment": [mos, resistor, supply, temperature],
            "control_v": control,
            "frequency_hz": frequency,
            "late_frequency_hz": late_frequency,
            "period_drift_fraction": drift,
            "startup_delay_s": startup_delay,
            "differential_high_v": observed.get("diff_high", 0.0),
            "differential_low_v": observed.get("diff_low", 0.0),
            "supply_current_a": observed.get("supply_current", 0.0),
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))

    environments = []
    for environment in ENVIRONMENTS:
        intervals: list[tuple[float, float]] = []
        members = []
        for variant in variants:
            member_cases = sorted(
                (case for case in cases if case["variant"] == variant
                 and tuple(case["environment"]) == environment),
                key=lambda case: float(case["control_v"]),
            )
            valid = [case for case in member_cases if case["result"] == "pass"]
            member_intervals = []
            for lower, upper in zip(member_cases, member_cases[1:]):
                if lower["result"] != "pass" or upper["result"] != "pass":
                    continue
                lower_hz, upper_hz = float(lower["frequency_hz"]), float(upper["frequency_hz"])
                interval = (min(lower_hz, upper_hz), max(lower_hz, upper_hz))
                intervals.append(interval)
                member_intervals.append(list(interval))
            members.append({
                "variant": variant,
                "valid_control_count": len(valid),
                "minimum_hz": min((float(case["frequency_hz"]) for case in valid), default=0.0),
                "maximum_hz": max((float(case["frequency_hz"]) for case in valid), default=0.0),
                "continuous_intervals_hz": member_intervals,
            })
        merged = merge_intervals(intervals)
        target = any(lower <= args.target_hz <= upper for lower, upper in merged)
        guardband_lower = args.target_hz * (1.0 - args.guardband_fraction)
        guardband_upper = args.target_hz * (1.0 + args.guardband_fraction)
        guardband = any(
            lower <= guardband_lower and upper >= guardband_upper
            for lower, upper in merged
        )
        environments.append({
            "environment": list(environment),
            "continuous_bank_intervals_hz": merged,
            "target_covered": target,
            "two_percent_guardband_covered": guardband,
            "members": members,
            "result": "pass" if target else "fail",
        })

    target_count = sum(environment["target_covered"] for environment in environments)
    guardband_count = sum(
        environment["two_percent_guardband_covered"] for environment in environments
    )
    required_target_pass = target_count == len(environments)
    design_guardband_pass = guardband_count == len(environments)
    qualification_pass = (
        required_target_pass if args.qualification == "required_target"
        else required_target_pass and design_guardband_pass
    )
    result = {
        "schema_version": 1,
        "claim": args.claim,
        "initial_condition": "none",
        "transient_uic": False,
        "startup_kick_polarity": "p",
        "supply_ramp_s": 0.5e-9,
        "controls_v": list(CONTROLS),
        "target_hz": args.target_hz,
        "guardband_fraction": args.guardband_fraction,
        "design_band_hz": [
            args.target_hz * (1.0 - args.guardband_fraction),
            args.target_hz * (1.0 + args.guardband_fraction),
        ],
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "environment_count": len(environments),
        "target_environment_count": target_count,
        "guardband_environment_count": guardband_count,
        "required_target_result": "pass" if required_target_pass else "fail",
        "design_guardband_result": "pass" if design_guardband_pass else "fail",
        "qualification": args.qualification,
        "band_pex_sha256": {
            variant: digest(args.pex_dir / f"cml_vco_band_{variant}.pex.spice")
            for variant in variants
        },
        "simulation_source_sha256": digest(args.source / "run_vco_band_bank.py"),
        "testbench_template_sha256": digest(args.source / "vco_band_bank_tb.spice.in"),
        "environments": environments,
        "cases": cases,
        "result": "pass" if qualification_pass else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"physical VCO-band bank: {result['passing_case_count']}/{result['case_count']} "
          f"cases; target={target_count}/{len(environments)}; "
          f"guardband={guardband_count}/{len(environments)}")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
