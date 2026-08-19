#!/usr/bin/env python3
"""Qualify the extracted dual R-2R DAC as VCO main/regenerative bias source."""
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

from analog_evidence import sha256_file  # noqa: E402


ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27),
    ("ff", "res_ff", 3.63, -40),
    ("ff", "res_ss", 2.97, 125),
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
)
PORTS = tuple(
    f"{channel}{bit}{suffix}"
    for channel in "AB"
    for bit in range(4, -1, -1)
    for suffix in ("", "B")
)
DC_NAMES = ("vctrl_main", "vctrl_regen", "reference_power")
SETTLING_NAMES = (
    "main_before", "regen_before", "main_at_50n", "regen_at_50n",
    "main_final", "regen_final",
)
MAIN_TARGETS_V = (0.78, 0.88, 0.98, 1.08, 1.18, 1.30, 1.40, 1.50)
REGEN_TARGETS_V = (1.20, 1.275, 1.35, 1.50, 1.65)


def instantiate(template: str, values: dict[str, str]) -> str:
    for name, value in values.items():
        template = template.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", template)))
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def static_bit_sources(code_main: int, code_regen: int, vdd: float) -> str:
    lines = []
    for channel, code in (("A", code_main), ("B", code_regen)):
        for bit in range(4, -1, -1):
            value = (code >> bit) & 1
            lines.append(f"V{channel}{bit} {channel}{bit} 0 {vdd if value else 0:.3f}")
            lines.append(
                f"V{channel}{bit}B {channel}{bit}B 0 {0 if value else vdd:.3f}"
            )
    return "\n".join(lines)


def transition_bit_sources(vdd: float) -> str:
    lines = []
    for channel, initial, final in (("A", 15, 16), ("B", 16, 15)):
        for bit in range(4, -1, -1):
            before, after = (initial >> bit) & 1, (final >> bit) & 1
            for suffix, invert in (("", False), ("B", True)):
                first = before ^ invert
                second = after ^ invert
                lines.append(
                    f"V{channel}{bit}{suffix} {channel}{bit}{suffix} 0 "
                    f"PWL(0 0 500p {vdd * first:.3f} 2n {vdd * first:.3f} "
                    f"2.05n {vdd * second:.3f})"
                )
    return "\n".join(lines)


def measurements(log: Path, names: tuple[str, ...]) -> dict[str, float]:
    pattern = re.compile(
        rf"^({'|'.join(names)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
    )
    return {name: float(value) for name, value in pattern.findall(log.read_text())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    dc_template = (args.source / "vco_bias_dac_dc_tb.spice.in").read_text()
    settling_template = (
        args.source / "vco_bias_dac_settling_tb.spice.in"
    ).read_text()
    common = {
        "PEX_PATH": str(args.pex),
        "DUT_PORTS": " ".join(PORTS),
    }
    dc_specs = [
        (environment, code)
        for environment in ENVIRONMENTS
        for code in range(32)
    ]

    def run_dc(spec: tuple[tuple[str, str, float, int], int]) -> dict[str, object]:
        (mos, resistor, supply, temperature), code = spec
        case_id = f"{mos}_{resistor}_{supply:.2f}_{temperature:+d}_c{code:02d}"
        case_id = case_id.replace("+", "p").replace("-", "m").replace(".", "p")
        deck = args.work / f"dc_{case_id}.spice"
        log = args.work / f"dc_{case_id}.log"
        deck.write_text(instantiate(dc_template, {
            **common,
            "MOS_CORNER": mos,
            "RES_CORNER": resistor,
            "VDD_V": f"{supply:.2f}",
            "TEMP_C": str(temperature),
            "BIT_SOURCES": static_bit_sources(code, 31 - code, supply),
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=60, check=False,
            )
        observed = measurements(log, DC_NAMES)
        complete = run.returncode == 0 and len(observed) == len(DC_NAMES)
        return {
            "environment": [mos, resistor, supply, temperature],
            "code": code,
            "vctrl_main_v": observed.get("vctrl_main", 0.0),
            "vctrl_regen_v": observed.get("vctrl_regen", 0.0),
            "reference_power_w": observed.get("reference_power", 0.0),
            "result": "complete" if complete else "incomplete",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        dc_cases = list(executor.map(run_dc, dc_specs))

    def run_settling(
        environment: tuple[str, str, float, int],
    ) -> dict[str, object]:
        mos, resistor, supply, temperature = environment
        case_id = f"{mos}_{resistor}_{supply:.2f}_{temperature:+d}"
        case_id = case_id.replace("+", "p").replace("-", "m").replace(".", "p")
        deck = args.work / f"settling_{case_id}.spice"
        log = args.work / f"settling_{case_id}.log"
        deck.write_text(instantiate(settling_template, {
            **common,
            "MOS_CORNER": mos,
            "RES_CORNER": resistor,
            "VDD_V": f"{supply:.2f}",
            "TEMP_C": str(temperature),
            "BIT_SOURCES": transition_bit_sources(supply),
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=90, check=False,
            )
        observed = measurements(log, SETTLING_NAMES)
        complete = run.returncode == 0 and len(observed) == len(SETTLING_NAMES)
        main_error = abs(
            observed.get("main_at_50n", 0.0) - observed.get("main_final", 1.0)
        )
        regen_error = abs(
            observed.get("regen_at_50n", 0.0) - observed.get("regen_final", 1.0)
        )
        passed = complete and main_error <= 0.005 and regen_error <= 0.005
        return {
            "environment": list(environment),
            **observed,
            "main_error_at_50ns_v": main_error,
            "regen_error_at_50ns_v": regen_error,
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        settling_cases = list(executor.map(run_settling, ENVIRONMENTS))

    groups = []
    for environment in ENVIRONMENTS:
        members = sorted(
            (case for case in dc_cases if tuple(case["environment"]) == environment),
            key=lambda case: int(case["code"]),
        )
        main_values = [float(case["vctrl_main_v"]) for case in members]
        regen_values = [float(case["vctrl_regen_v"]) for case in reversed(members)]
        main_steps = [upper - lower for lower, upper in zip(main_values, main_values[1:])]
        regen_steps = [upper - lower for lower, upper in zip(regen_values, regen_values[1:])]
        complement = [
            float(case["vctrl_main_v"]) + float(case["vctrl_regen_v"])
            for case in members
        ]
        power = [abs(float(case["reference_power_w"])) for case in members]
        target_map = []
        for control, targets, values in (
            ("main", MAIN_TARGETS_V, main_values),
            ("regen", REGEN_TARGETS_V, regen_values),
        ):
            for target in targets:
                code, actual = min(
                    enumerate(values), key=lambda member: abs(member[1] - target)
                )
                target_map.append({
                    "control": control,
                    "target_v": target,
                    "code": code,
                    "actual_v": actual,
                    "absolute_error_v": abs(actual - target),
                })
        passed = (
            len(members) == 32
            and all(case["result"] == "complete" for case in members)
            and min(main_steps) >= 0.020
            and min(regen_steps) >= 0.020
            and max(main_steps) <= 0.080
            and max(regen_steps) <= 0.080
            and max(main_values[0], regen_values[0]) <= 0.020
            and min(main_values[-1], regen_values[-1]) >= 1.70
            and max(item["absolute_error_v"] for item in target_map) <= 0.040
            and max(complement) - min(complement) <= 0.080
            and max(power) <= 0.002
        )
        groups.append({
            "environment": list(environment),
            "minimum_step_main_v": min(main_steps),
            "minimum_step_regen_v": min(regen_steps),
            "maximum_step_main_v": max(main_steps),
            "maximum_step_regen_v": max(regen_steps),
            "endpoint_low_v": max(main_values[0], regen_values[0]),
            "endpoint_high_v": min(main_values[-1], regen_values[-1]),
            "complement_sum_range_v": [min(complement), max(complement)],
            "maximum_reference_power_w": max(power),
            "target_code_map": target_map,
            "maximum_target_error_v": max(
                item["absolute_error_v"] for item in target_map
            ),
            "result": "pass" if passed else "fail",
        })

    passed = (
        all(group["result"] == "pass" for group in groups)
        and all(case["result"] == "pass" for case in settling_cases)
    )
    result = {
        "schema_version": 1,
        "claim": "extracted_dual_5bit_vco_bias_dac_range_and_settling",
        "reference_range_v": [0.0, 1.8],
        "output_load_f": 1e-12,
        "settling_deadline_s": 50e-9,
        "settling_error_limit_v": 0.005,
        "target_error_limit_v": 0.040,
        "dc_case_count": len(dc_cases),
        "passing_dc_environment_count": sum(
            group["result"] == "pass" for group in groups
        ),
        "settling_case_count": len(settling_cases),
        "passing_settling_case_count": sum(
            case["result"] == "pass" for case in settling_cases
        ),
        "pex_sha256": sha256_file(args.pex),
        "simulation_source_sha256": sha256_file(Path(__file__)),
        "shared_evidence_source_sha256": sha256_file(
            SERDES_ROOT / "analog_evidence.py"
        ),
        "dc_testbench_sha256": sha256_file(args.source / "vco_bias_dac_dc_tb.spice.in"),
        "settling_testbench_sha256": sha256_file(
            args.source / "vco_bias_dac_settling_tb.spice.in"
        ),
        "groups": groups,
        "settling_cases": settling_cases,
        "dc_cases": dc_cases,
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"VCO bias DAC: dc={result['passing_dc_environment_count']}/5; "
        f"settling={result['passing_settling_case_count']}/5"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
