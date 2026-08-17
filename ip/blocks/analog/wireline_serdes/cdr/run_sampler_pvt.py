#!/usr/bin/env python3
"""Calibrate the dual-edge sampler across GF180 process and operating corners."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

from run_sampler_nominal import BIAS_VALUES, BITS, SAMPLE_INDICES, instantiate, pwl

MOS_CORNERS = ("typical", "ff", "ss")
RES_CORNERS = ("res_typical", "res_ff", "res_ss")
COMMON_MODE_FRACTIONS = (0.60, 0.70, 0.80)
SCALAR = re.compile(
    r"^(sample_\d+|even_cm_avg|odd_cm_avg|supply_current)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "sampler_tb.spice.in").read_text()
    ui = 1 / 2.5e9
    measures = []
    for index in SAMPLE_INDICES:
        output = "even_diff" if index % 2 == 0 else "odd_diff"
        measures.append(f"meas tran sample_{index} find {output} at={(index + 1) * ui + 50e-12:.12g}")

    specifications = []
    for mos in MOS_CORNERS:
        for resistor in RES_CORNERS:
            for vdd in (2.97, 3.30, 3.63):
                for temperature in (-40, 27, 125):
                    for cm_fraction in COMMON_MODE_FRACTIONS:
                        common_mode = vdd * cm_fraction
                        for bias in BIAS_VALUES:
                            case_id = (f"{mos}_{resistor}_{vdd:.2f}_{temperature:+d}_cm{cm_fraction:.2f}_b{bias:.2f}"
                                       .replace("+", "p").replace("-", "m"))
                            values = {
                                "MOS_CORNER": mos, "RES_CORNER": resistor,
                                "DUT_INCLUDE": (f".include {args.pex}" if args.pex else
                                                ".include /src/cdr_sampler.spice"),
                                "DUT_SUBCKT": "cdr_sampler_pex" if args.pex else "cdr_sampler",
                                "TEMP_C": str(temperature), "VDD_SOURCE": f"{vdd:.2f}",
                                "DATA_P_PWL": pwl(True, common_mode, 0.10, ui, 20e-12),
                                "DATA_N_PWL": pwl(False, common_mode, 0.10, ui, 20e-12),
                                "CLOCK_CM_V": f"{common_mode:.6f}", "CLOCK_PEAK_V": "0.45",
                                "CLOCK_HZ": "1.25g", "CLOCK_PHASE_DEG": "0",
                                "CLOCK_N_PHASE_DEG": "180", "VBIAS_V": f"{bias:.2f}",
                                "CLOAD_F": "25f", "TSTEP_S": f"{ui / 100:.12g}",
                                "TSTOP_S": f"{(len(BITS) + 1) * ui:.12g}",
                                "MEAS_START_S": f"{4 * ui:.12g}",
                                "SAMPLE_MEASURES": "\n".join(measures),
                            }
                            specifications.append((case_id, mos, resistor, vdd, temperature,
                                                   cm_fraction, bias, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        case_id, mos, resistor, vdd, temperature, cm_fraction, bias, values = specification
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck_text = instantiate(template, values)
        reusable = (deck.exists() and log.exists() and deck.read_text() == deck_text
                    and len({name for name, _ in SCALAR.findall(log.read_text())})
                    == len(SAMPLE_INDICES) + 3)
        if reusable:
            return_code = 0
        else:
            deck.write_text(deck_text)
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=90, check=False)
            return_code = run.returncode
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        signed = {index: observed.get(f"sample_{index}", 0.0) * (1 if BITS[index] else -1)
                  for index in SAMPLE_INDICES}
        even_margin = min(value for index, value in signed.items() if index % 2 == 0)
        odd_margin = min(value for index, value in signed.items() if index % 2 == 1)
        complete = return_code == 0 and len(observed) == len(SAMPLE_INDICES) + 3
        electrical = (complete and even_margin >= 0.10 and odd_margin >= 0.10
                      and abs(even_margin - odd_margin) <= 0.10
                      and 0.50 <= observed["even_cm_avg"] <= float(vdd) - 0.10
                      and 0.50 <= observed["odd_cm_avg"] <= float(vdd) - 0.10
                      and 0.001 <= observed["supply_current"] <= 0.010)
        return {"id": case_id, "mos_corner": mos, "res_corner": resistor,
                "supply_v": vdd, "temperature_c": temperature,
                "common_mode_fraction": cm_fraction, "bias_v": bias,
                "even_margin_v": even_margin, "odd_margin_v": odd_margin,
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
        passing = [case for case in members if case["result"] == "pass"
                   and 0.90 <= float(case["bias_v"]) <= 1.30]
        selected = (max(passing, key=lambda case: min(float(case["even_margin_v"]),
                                                       float(case["odd_margin_v"])))
                    if passing else None)
        valid = selected is not None and sum(case["result"] == "pass" for case in members) >= 3
        groups.append({"group": list(key),
                       "passing_bias_count": sum(case["result"] == "pass" for case in members),
                       "selected_case": selected,
                       "result": "pass" if valid else "fail"})
    passing_groups = sum(group["result"] == "pass" for group in groups)
    complete_cases = sum(len(case["observed"]) == len(SAMPLE_INDICES) + 3 for case in cases)
    passed = complete_cases == len(cases) and passing_groups == len(groups)
    result = {"schema_version": 1, "extraction": "full_rc" if args.pex else "schematic",
              "result": "pass" if passed else "fail", "case_count": len(cases),
              "complete_case_count": complete_cases, "group_count": len(groups),
              "passing_group_count": passing_groups, "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cdr_sampler PVT: {complete_cases}/{len(cases)} complete; "
          f"{passing_groups}/{len(groups)} groups pass")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
