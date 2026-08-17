#!/usr/bin/env python3
"""Search load code and bias over the public-model PVT combinations."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path

MOS_CORNERS = ("typical", "ff", "ss", "fs", "sf")
RES_CORNERS = ("res_typical", "res_ff", "res_ss")
TEMPERATURES_C = (-40, 27, 125)
SUPPLIES_V = (2.97, 3.30, 3.63)
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    return parser.parse_args()


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled SPICE tokens: {remaining}")
    return result


def simulate(deck: Path, log: Path) -> None:
    with log.open("w") as output:
        run = subprocess.run(
            ["ngspice", "-b", str(deck)],
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
    if run.returncode:
        raise RuntimeError(f"ngspice failed for {deck.name}")


def rows(path: Path, enabled: int) -> list[dict[str, float | int]]:
    result = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) != 5 or not fields[0][0].isdigit():
            continue
        _, bias, outp, outn, current = map(float, fields)
        result.append(
            {
                "enabled_branches": enabled,
                "vbias_v": bias,
                "outp_v": outp,
                "outn_v": outn,
                "current_a": current,
                "static_diff_v": outn - outp,
            }
        )
    return result


def control_values(enabled: int, supply: float) -> dict[str, str]:
    return {
        f"B{index}_V": "0" if index < enabled else f"{supply:.2f}"
        for index in range(4)
    }


def choose(candidates: list[dict[str, float | int]], supply: float) -> dict[str, float | int] | None:
    safe = [
        row
        for row in candidates
        if 0.55 <= float(row["vbias_v"]) <= 1.75
        and 0.001 <= float(row["current_a"]) <= 0.008
        and min(float(row["outp_v"]), float(row["outn_v"])) >= 1.8
        and max(float(row["outp_v"]), float(row["outn_v"])) <= supply + 0.02
    ]
    if not safe:
        return None
    # Several load-code/bias pairs can produce the same DC swing.  Prefer the
    # lower-resistance (therefore higher-current) solution for bandwidth while
    # remaining inside the explicit current clamp and static-swing window.
    in_window = [row for row in safe if 0.60 <= float(row["static_diff_v"]) <= 0.64]
    if in_window:
        return max(in_window, key=lambda row: float(row["current_a"]))
    return min(safe, key=lambda row: abs(float(row["static_diff_v"]) - 0.62))


def measured(path: Path) -> dict[str, float]:
    return {name: float(value) for name, value in MEASURE.findall(path.read_text())}


def checks(values: dict[str, float], supply: float) -> tuple[dict[str, bool], dict[str, bool]]:
    required = {
        "diff_high", "diff_low", "supply_current_avg", "output_floor",
        "output_floor_n", "output_ceiling", "output_ceiling_n",
        "common_mode_avg", "diff_rise", "diff_fall",
    }
    if not required <= values.keys():
        return {"measurements_complete": False}, {"output_ceiling": False}
    core = {
        "measurements_complete": True,
        "finite": all(math.isfinite(values[name]) for name in required),
        "swing_min": values["diff_high"] <= -0.40 and values["diff_low"] >= 0.40,
        "swing_max": values["diff_high"] >= -0.65 and values["diff_low"] <= 0.65,
        "symmetry": abs(abs(values["diff_high"]) - abs(values["diff_low"])) <= 0.010,
        "crossing_time": max(values["diff_rise"], values["diff_fall"]) <= 80e-12,
        "current_clamp": 0.001 <= values["supply_current_avg"] <= 0.008,
        "output_floor": min(values["output_floor"], values["output_floor_n"]) >= 1.8,
        "common_mode": 1.8 <= values["common_mode_avg"] <= supply - 0.10,
    }
    boundary = {
        "output_ceiling": max(values["output_ceiling"], values["output_ceiling_n"]) <= supply + 0.05,
    }
    return core, boundary


def main() -> None:
    args = arguments()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.pex:
        cal_template = (args.source / "extracted_calibration_tb.spice.in").read_text()
        tran_template = (args.source / "extracted_transient_tb.spice.in").read_text()
    else:
        cal_template = (args.source / "programmable_calibration_tb.spice.in").read_text()
        tran_template = (args.source / "programmable_transient_tb.spice.in").read_text()
    cases = []

    for mos in MOS_CORNERS:
        for resistor in RES_CORNERS:
            for temperature in TEMPERATURES_C:
                for supply in SUPPLIES_V:
                    case_id = f"{mos}_{resistor}_{temperature:+d}c_{supply:.2f}v".replace("+", "p").replace("-", "m")
                    common = {
                        "MOS_CORNER": mos,
                        "RES_CORNER": resistor,
                        "TEMP_C": str(temperature),
                        "VDD_V": f"{supply:.2f}",
                    }
                    if args.pex:
                        common["PEX_PATH"] = str(args.pex)
                    candidates = []
                    for enabled in range(5):
                        cal_data = args.work / f"{case_id}_{enabled}.cal.dat"
                        deck = args.work / f"{case_id}_{enabled}.cal.spice"
                        deck.write_text(
                            instantiate(
                                cal_template,
                                common | control_values(enabled, supply) | {"CAL_DATA": str(cal_data)},
                            )
                        )
                        simulate(deck, args.work / f"{case_id}_{enabled}.cal.log")
                        candidates.extend(rows(cal_data, enabled))

                    selected = choose(candidates, supply)
                    case: dict[str, object] = {
                        "id": case_id,
                        "mos_corner": mos,
                        "res_corner": resistor,
                        "temperature_c": temperature,
                        "supply_v": supply,
                        "calibration": selected,
                    }
                    if selected is None:
                        case["core_checks"] = {"calibration_range": False}
                        case["boundary_checks"] = {"output_ceiling": False}
                        cases.append(case)
                        continue

                    enabled = int(selected["enabled_branches"])
                    observed: dict[str, float] = {}
                    core: dict[str, bool] = {}
                    boundary: dict[str, bool] = {}
                    attempts = 0
                    while attempts < 9:
                        deck = args.work / f"{case_id}_{attempts}.tran.spice"
                        deck.write_text(
                            instantiate(
                                tran_template,
                                common
                                | control_values(enabled, supply)
                                | {"VBIAS_V": f"{float(selected['vbias_v']):.3f}"},
                            )
                        )
                        log = args.work / f"{case_id}_{attempts}.tran.log"
                        simulate(deck, log)
                        observed = measured(log)
                        core, boundary = checks(observed, supply)
                        attempts += 1
                        failed = {name for name, passed in core.items() if not passed}
                        if not failed:
                            break
                        if "swing_min" in failed and failed <= {"swing_min", "crossing_time"}:
                            magnitude = min(abs(observed["diff_high"]), abs(observed["diff_low"]))
                            target_current = observed["supply_current_avg"] * 0.52 / max(magnitude, 1e-6)
                            alternatives = [
                                row for row in candidates
                                if int(row["enabled_branches"]) == enabled
                                and float(row["vbias_v"]) > float(selected["vbias_v"])
                                and float(row["current_a"]) <= 0.008
                                and min(float(row["outp_v"]), float(row["outn_v"])) >= 1.8
                            ]
                            if not alternatives:
                                break
                            selected = min(
                                alternatives,
                                key=lambda row: abs(float(row["current_a"]) - target_current),
                            )
                            continue
                        if failed == {"swing_max"}:
                            magnitude = max(abs(observed["diff_high"]), abs(observed["diff_low"]))
                            target_current = observed["supply_current_avg"] * 0.52 / max(magnitude, 1e-6)
                            alternatives = [
                                row for row in candidates
                                if int(row["enabled_branches"]) == enabled
                                and float(row["vbias_v"]) < float(selected["vbias_v"])
                                and float(row["current_a"]) >= 0.001
                            ]
                            if not alternatives:
                                break
                            selected = min(
                                alternatives,
                                key=lambda row: abs(float(row["current_a"]) - target_current),
                            )
                            continue
                        break
                    case["calibration"] = selected
                    case["transient_calibration_attempts"] = attempts
                    case["observed"] = observed
                    case["core_checks"] = {"calibration_range": True} | core
                    case["boundary_checks"] = boundary
                    cases.append(case)

    core_passed = sum(all(case["core_checks"].values()) for case in cases)
    boundary_passed = sum(all(case["boundary_checks"].values()) for case in cases)
    result = {
        "schema_version": 1,
        "result": "pass" if core_passed == len(cases) and boundary_passed == len(cases) else "fail",
        "core_result": "pass" if core_passed == len(cases) else "fail",
        "boundary_result": "pass" if boundary_passed == len(cases) else "fail",
        "qualification": (
            "full-RC extracted public-model PVT evidence; pad/ESD boundary remains unmodeled"
            if args.pex else
            "bounded schematic public-model PVT evidence; pad/ESD boundary remains unmodeled"
        ),
        "target_rate_gt_s": 2.5,
        "case_count": len(cases),
        "core_passed_case_count": core_passed,
        "boundary_passed_case_count": boundary_passed,
        "cases": cases,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"programmable serdes_tx PVT core: {core_passed}/{len(cases)}")
    print(f"programmable serdes_tx boundary: {boundary_passed}/{len(cases)}")
    if core_passed != len(cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
