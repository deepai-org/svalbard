#!/usr/bin/env python3
"""Screen deliberate delay-cap geometries for a 1.25 GHz folded VCO bank."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

CAP_LENGTHS_UM = (0.50, 0.80, 1.20, 1.80, 2.60, 3.80, 5.50, 8.00)
CONTROLS_V = (0.78, 0.88, 0.98, 1.08, 1.18, 1.30, 1.40, 1.50)
ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27),
    ("ff", "res_ff", 3.63, -40),
    ("ff", "res_ss", 2.97, 125),
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
)
CAP_DEVICE = re.compile(
    r"^(X\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+nfet_03v3\s+.*"
    r"\bw=3\.2u\s+.*\bl=)0\.37(u\b.*)$"
)
MEASURE_NAMES = (
    "startup_time", "period", "period_late", "diff_high", "diff_low",
    "output_cm", "supply_current",
)
MEASURE = re.compile(
    rf"^({'|'.join(MEASURE_NAMES)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
)


def mutate(base: str, cap_length_um: float) -> str:
    output = []
    count = 0
    for line in base.splitlines():
        match = CAP_DEVICE.match(line)
        if match:
            line = f"{match.group(1)}{cap_length_um:g}{match.group(2)}"
            count += 1
        output.append(line)
    if count != 8:
        raise ValueError(f"classified {count} delay capacitors, expected 8")
    return "\n".join(output) + "\n"


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def merge(intervals: list[tuple[float, float]]) -> list[list[float]]:
    output: list[list[float]] = []
    for lower, upper in sorted(intervals):
        if not output or lower > output[-1][1]:
            output.append([lower, upper])
        else:
            output[-1][1] = max(output[-1][1], upper)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    base = args.pex.read_text()
    template = (args.source / "vco_band_bank_tb.spice.in").read_text()
    pex_paths = {}
    for cap_length in CAP_LENGTHS_UM:
        path = args.work / f"cap_{cap_length:.2f}.pex.spice"
        path.write_text(mutate(base, cap_length))
        pex_paths[cap_length] = path

    specs = [
        (cap_length, environment, control)
        for cap_length in CAP_LENGTHS_UM
        for environment in ENVIRONMENTS
        for control in CONTROLS_V
    ]

    def simulate(spec: tuple[float, tuple[str, str, float, int], float]) -> dict[str, object]:
        cap_length, (mos, resistor, supply, temperature), control = spec
        case_id = (
            f"cap_{cap_length:.2f}_{mos}_{resistor}_{control:.2f}"
            .replace(".", "p")
        )
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": mos,
            "RES_CORNER": resistor,
            "TEMP_C": str(temperature),
            "VDD_V": f"{supply:.2f}",
            "VCTRL_V": f"{control:.2f}",
            "BAND_PEX_PATH": str(pex_paths[cap_length]),
            "BAND_PEX_SUBCKT": "cml_vco_band_pex",
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=90, check=False,
            )
        observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(MEASURE_NAMES)
        frequency = 1 / observed["period"] if complete and observed["period"] > 0 else 0.0
        late = 1 / observed["period_late"] if complete and observed["period_late"] > 0 else 0.0
        drift = abs(frequency - late) / frequency if frequency else 1.0
        startup_delay = observed.get("startup_time", 0.0) - 1.30e-9
        passed = (
            complete and drift <= 0.01
            and observed["diff_high"] >= 0.20 and observed["diff_low"] <= -0.20
            and 0.003 <= observed["supply_current"] <= 0.040
            and 0 <= startup_delay <= 10e-9
        )
        return {
            "cap_length_um": cap_length,
            "environment": [mos, resistor, supply, temperature],
            "control_v": control,
            "frequency_hz": frequency,
            "startup_delay_s": startup_delay,
            "period_drift_fraction": drift,
            "differential_high_v": observed.get("diff_high", 0.0),
            "differential_low_v": observed.get("diff_low", 0.0),
            "supply_current_a": observed.get("supply_current", 0.0),
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))

    groups = []
    for environment in ENVIRONMENTS:
        bank_intervals: list[tuple[float, float]] = []
        candidates = []
        for cap_length in CAP_LENGTHS_UM:
            member = sorted(
                (case for case in cases
                 if case["cap_length_um"] == cap_length
                 and tuple(case["environment"]) == environment),
                key=lambda case: float(case["control_v"]),
            )
            intervals = []
            for lower, upper in zip(member, member[1:]):
                if lower["result"] == upper["result"] == "pass":
                    interval = sorted((float(lower["frequency_hz"]),
                                       float(upper["frequency_hz"])))
                    intervals.append(interval)
                    bank_intervals.append(tuple(interval))
            valid = [case for case in member if case["result"] == "pass"]
            candidates.append({
                "cap_length_um": cap_length,
                "valid_control_count": len(valid),
                "minimum_hz": min((float(case["frequency_hz"]) for case in valid), default=0.0),
                "maximum_hz": max((float(case["frequency_hz"]) for case in valid), default=0.0),
                "continuous_intervals_hz": intervals,
            })
        merged = merge(bank_intervals)
        groups.append({
            "environment": list(environment),
            "continuous_bank_intervals_hz": merged,
            "target_covered": any(lower <= 1.25e9 <= upper for lower, upper in merged),
            "two_percent_guardband_covered": any(
                lower <= 1.225e9 and upper >= 1.275e9 for lower, upper in merged
            ),
            "candidates": candidates,
        })

    result = {
        "schema_version": 1,
        "claim": "folded_parent_half_rate_delay_cap_screen",
        "limitation": "screen only; selected dimensions require regenerated DRC/LVS/PEX",
        "base_pex_sha256": hashlib.sha256(args.pex.read_bytes()).hexdigest(),
        "target_hz": 1.25e9,
        "design_band_hz": [1.225e9, 1.275e9],
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "target_environment_count": sum(group["target_covered"] for group in groups),
        "guardband_environment_count": sum(
            group["two_percent_guardband_covered"] for group in groups
        ),
        "groups": groups,
        "cases": cases,
        "result": "screen_complete",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"half-rate VCO screen: {result['passing_case_count']}/{result['case_count']} valid; "
        f"target={result['target_environment_count']}/{len(groups)}; "
        f"guardband={result['guardband_environment_count']}/{len(groups)}"
    )


if __name__ == "__main__":
    main()
