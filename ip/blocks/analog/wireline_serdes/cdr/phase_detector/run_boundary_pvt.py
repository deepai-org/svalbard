#!/usr/bin/env python3
"""Calibrate a half-rate Alexander CML boundary over bounded GF180 PVT."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

from run_xor_nominal import instantiate, pwl

MOS_CORNERS = ("typical", "ff", "ss")
RES_CORNERS = ("res_typical", "res_ff", "res_ss")
SUPPLIES = (2.97, 3.30, 3.63)
TEMPERATURES = (-40, 27, 125)
COMMON_MODE_FRACTIONS = (0.60, 0.70, 0.80)
BIAS_VALUES = tuple(round(0.45 + 0.05 * index, 2) for index in range(15))
PREV = (0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 1, 1)
EDGE = (0, 1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 0)
CUR = (1, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0)
SAMPLE_INDICES = tuple(range(4, 22))
SCALAR = re.compile(
    r"^(early_\d+|late_\d+|early_cm_avg|late_cm_avg|supply_current)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--nominal", action="store_true")
    parser.add_argument("--hot-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "boundary_tb.spice.in").read_text()
    dut_sha256 = hashlib.sha256((args.source / "cml_phase_detector.spice").read_bytes()).hexdigest()
    ui = 1 / 2.5e9
    measures = []
    for index in SAMPLE_INDICES:
        time = (index + 0.5) * ui
        measures.append(f"meas tran early_{index} find early_diff at={time:.12g}")
        measures.append(f"meas tran late_{index} find late_diff at={time:.12g}")

    if args.nominal:
        environments = (("typical", "res_typical", 3.30, 27, 2 / 3),)
    else:
        temperatures = (125,) if args.hot_only else TEMPERATURES
        environments = ((mos, resistor, vdd, temperature, cm_fraction)
                        for mos in MOS_CORNERS for resistor in RES_CORNERS for vdd in SUPPLIES
                        for temperature in temperatures for cm_fraction in COMMON_MODE_FRACTIONS)
    specifications = []
    for mos, resistor, vdd, temperature, cm_fraction in environments:
        common_mode = vdd * cm_fraction
        signals = {}
        for name, bits in (("PREV", PREV), ("EDGE", EDGE), ("CUR", CUR)):
            signals[f"{name}_P_PWL"] = pwl(bits, True, common_mode, 0.14, ui, 20e-12)
            signals[f"{name}_N_PWL"] = pwl(bits, False, common_mode, 0.14, ui, 20e-12)
        for bias in BIAS_VALUES:
            case_id = (f"{mos}_{resistor}_{vdd:.2f}_{temperature:+d}_cm{cm_fraction:.3f}_b{bias:.2f}"
                       .replace("+", "p").replace("-", "m"))
            values = {
                "MOS_CORNER": mos, "RES_CORNER": resistor,
                "DUT_SHA256": dut_sha256,
                "TEMP_C": str(temperature), "VDD_V": f"{vdd:.2f}",
                "VBIAS_V": f"{bias:.2f}", "CLOAD_F": "25f",
                "TSTEP_S": f"{ui / 100:.12g}",
                "TSTOP_S": f"{(len(PREV) + 1) * ui:.12g}",
                "MEAS_START_S": f"{4 * ui:.12g}", "MEASURES": "\n".join(measures),
                **signals,
            }
            specifications.append((case_id, mos, resistor, vdd, temperature,
                                   cm_fraction, bias, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        case_id, mos, resistor, vdd, temperature, cm_fraction, bias, values = specification
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck_text = instantiate(template, values)
        expected_scalars = 2 * len(SAMPLE_INDICES) + 3
        reusable = (deck.exists() and log.exists() and deck.read_text() == deck_text
                    and len({name for name, _ in SCALAR.findall(log.read_text())}) == expected_scalars)
        if reusable:
            return_code = 0
        else:
            deck.write_text(deck_text)
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=90, check=False)
            return_code = run.returncode
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        early = [observed.get(f"early_{index}", 0.0)
                 * (1 if PREV[index] ^ EDGE[index] else -1) for index in SAMPLE_INDICES]
        late = [observed.get(f"late_{index}", 0.0)
                * (1 if EDGE[index] ^ CUR[index] else -1) for index in SAMPLE_INDICES]
        complete = return_code == 0 and len(observed) == expected_scalars
        early_margin, late_margin = min(early), min(late)
        maximum_cm = float(vdd) - 0.15
        electrical = (complete and early_margin >= 0.10 and late_margin >= 0.10
                      and abs(early_margin - late_margin) <= 0.05
                      and 0.50 <= observed["early_cm_avg"] <= maximum_cm
                      and 0.50 <= observed["late_cm_avg"] <= maximum_cm
                      and 0.0002 <= observed["supply_current"] <= 0.020)
        return {"id": case_id, "mos_corner": mos, "res_corner": resistor,
                "supply_v": vdd, "temperature_c": temperature,
                "common_mode_fraction": cm_fraction, "bias_v": bias,
                "early_margin_v": early_margin, "late_margin_v": late_margin,
                "observed": observed, "result": "pass" if electrical else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for case in cases:
        key = (case["mos_corner"], case["res_corner"], case["supply_v"],
               case["temperature_c"], case["common_mode_fraction"])
        grouped.setdefault(key, []).append(case)
    groups = []
    for key, members in grouped.items():
        passing = [case for case in members if case["result"] == "pass"]
        selected = (max(passing, key=lambda case: min(float(case["early_margin_v"]),
                                                       float(case["late_margin_v"])))
                    if passing else None)
        selected_index = members.index(selected) if selected else -1
        valid = len(passing) >= 3 and 0 < selected_index < len(members) - 1
        groups.append({"group": list(key), "passing_bias_count": len(passing),
                       "selected_case": selected, "result": "pass" if valid else "fail"})
    complete_cases = sum(len(case["observed"]) == 2 * len(SAMPLE_INDICES) + 3 for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    passed = complete_cases == len(cases) and passing_groups == len(groups)
    result = {"schema_version": 1, "extraction": "schematic",
              "result": "pass" if passed else "fail", "case_count": len(cases),
              "complete_case_count": complete_cases, "group_count": len(groups),
              "passing_group_count": passing_groups, "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cml_alexander_boundary PVT: {complete_cases}/{len(cases)} complete; "
          f"{passing_groups}/{len(groups)} groups pass")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
