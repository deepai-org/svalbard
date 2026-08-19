#!/usr/bin/env python3
"""Screen a physical split-tail-control VCO in the two open margin corners."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

MAIN_CONTROLS = (0.78, 0.88, 0.98, 1.08, 1.18, 1.30, 1.40, 1.50)
REGEN_CONTROLS = (1.20, 1.275, 1.35, 1.50, 1.65)
ENVIRONMENTS = (
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


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--lvs", type=Path, required=True)
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pex-subckt", required=True)
    parser.add_argument("--claim", required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "split_control_vco_tb.spice.in").read_text()
    specs = [
        (environment, main_control, regen_control)
        for environment in ENVIRONMENTS
        for regen_control in REGEN_CONTROLS
        for main_control in MAIN_CONTROLS
    ]

    def simulate(spec: tuple[tuple[str, str, float, int], float, float]) -> dict[str, object]:
        (mos, resistor, supply, temperature), main_control, regen_control = spec
        case_id = (
            f"{mos}_{resistor}_main_{main_control:.3f}_regen_{regen_control:.3f}"
            .replace(".", "p")
        )
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": mos,
            "RES_CORNER": resistor,
            "TEMP_C": str(temperature),
            "VDD_V": f"{supply:.2f}",
            "VCTRL_MAIN_V": f"{main_control:.3f}",
            "VCTRL_REGEN_V": f"{regen_control:.3f}",
            "BAND_PEX_PATH": str(args.pex),
            "BAND_PEX_SUBCKT": args.pex_subckt,
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=90, check=False,
            )
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(MEASURE_NAMES)
        frequency = 1.0 / observed["period"] if complete and observed["period"] > 0 else 0.0
        late = 1.0 / observed["period_late"] if complete and observed["period_late"] > 0 else 0.0
        drift = abs(frequency - late) / frequency if frequency else 1.0
        startup_delay = observed.get("startup_time", 0.0) - 1.30e-9
        passed = (
            complete and drift <= 0.01
            and observed["diff_high"] >= 0.20 and observed["diff_low"] <= -0.20
            and 0.003 <= observed["supply_current"] <= 0.040
            and 0 <= startup_delay <= 10e-9
        )
        return {
            "environment": [mos, resistor, supply, temperature],
            "main_control_v": main_control,
            "regen_control_v": regen_control,
            "frequency_hz": frequency,
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
        all_intervals: list[tuple[float, float]] = []
        regen_slices = []
        for regen_control in REGEN_CONTROLS:
            members = sorted(
                (case for case in cases
                 if tuple(case["environment"]) == environment
                 and case["regen_control_v"] == regen_control),
                key=lambda case: float(case["main_control_v"]),
            )
            intervals = []
            for lower, upper in zip(members, members[1:]):
                if lower["result"] == upper["result"] == "pass":
                    interval = tuple(sorted((float(lower["frequency_hz"]),
                                             float(upper["frequency_hz"]))))
                    intervals.append(list(interval))
                    all_intervals.append(interval)
            regen_slices.append({
                "regen_control_v": regen_control,
                "valid_control_count": sum(case["result"] == "pass" for case in members),
                "continuous_intervals_hz": intervals,
            })
        merged = merge(all_intervals)
        environments.append({
            "environment": list(environment),
            "continuous_intervals_hz": merged,
            "target_covered": any(lower <= 1.25e9 <= upper for lower, upper in merged),
            "two_percent_guardband_covered": any(
                lower <= 1.225e9 and upper >= 1.275e9 for lower, upper in merged
            ),
            "regen_slices": regen_slices,
        })

    drc = args.drc.read_text()
    lvs = args.lvs.read_text()
    pex = args.pex.read_text()
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
    physical = {
        "drc_error_count": int(count.group(1)) if count else -1,
        "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": digest(args.pex),
        "layout_image_sha256": digest(args.render),
    }
    physical_pass = (
        physical["drc_error_count"] == 0 and physical["lvs_unique"]
        and physical["pex_resistor_count"] >= 1000
        and physical["pex_capacitor_count"] >= 280
    )
    result = {
        "schema_version": 1,
        "claim": args.claim,
        "limitation": "candidate screen in two formerly open environments",
        "initial_condition": "none",
        "transient_uic": False,
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "target_environment_count": sum(item["target_covered"] for item in environments),
        "guardband_environment_count": sum(
            item["two_percent_guardband_covered"] for item in environments
        ),
        "physical": physical,
        "environments": environments,
        "cases": cases,
        "layout_source_sha256": digest(args.source / "layout.tcl"),
        "parent_layout_source_sha256": digest(args.source / "vco_band_layout.tcl"),
        "schematic_source_sha256": digest(args.source / "split_control_vco.spice"),
        "testbench_source_sha256": digest(args.source / "split_control_vco_tb.spice.in"),
        "result": "screen_complete" if physical_pass else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"split-control VCO: physical={'pass' if physical_pass else 'fail'}; "
        f"cases={result['passing_case_count']}/{result['case_count']}; "
        f"target={result['target_environment_count']}/{len(environments)}; "
        f"guardband={result['guardband_environment_count']}/{len(environments)}"
    )
    if not physical_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
