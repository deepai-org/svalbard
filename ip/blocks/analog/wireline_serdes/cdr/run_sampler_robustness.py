#!/usr/bin/env python3
"""Stress the extracted sampler after selecting one fixed bias per environment."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

from run_sampler_nominal import BITS, SAMPLE_INDICES, instantiate, pwl

ENVIRONMENTS = (
    ("nominal", "typical", "res_typical", 3.30, 27, 0.70),
    ("fast_cold_lowcm", "ff", "res_ff", 3.63, -40, 0.60),
    ("fast_hot_lowv", "ff", "res_ss", 2.97, 125, 0.80),
    ("slow_hot_lowcm", "ss", "res_ss", 2.97, 125, 0.60),
    ("slow_cold_highcm", "ss", "res_ff", 3.63, -40, 0.80),
    ("typ_cold_lowv", "typical", "res_ff", 2.97, -40, 0.70),
    ("typ_hot_highv", "typical", "res_ss", 3.63, 125, 0.70),
    ("fast_nom_highcm", "ff", "res_typical", 3.30, 27, 0.80),
    ("slow_nom_lowcm", "ss", "res_typical", 3.30, 27, 0.60),
)
STRESSES = (
    ("baseline", 25, 0.10, 0.45, 0.0, 0.0),
    ("load10", 10, 0.10, 0.45, 0.0, 0.0),
    ("load50", 50, 0.10, 0.45, 0.0, 0.0),
    ("load100", 100, 0.10, 0.45, 0.0, 0.0),
    ("data50m", 25, 0.05, 0.45, 0.0, 0.0),
    ("data200m", 25, 0.20, 0.45, 0.0, 0.0),
    ("clock300m", 25, 0.10, 0.30, 0.0, 0.0),
    ("clock600m", 25, 0.10, 0.60, 0.0, 0.0),
    ("phase_m50ps", 25, 0.10, 0.45, -22.5, 0.0),
    ("phase_m25ps", 25, 0.10, 0.45, -11.25, 0.0),
    ("phase_p25ps", 25, 0.10, 0.45, 11.25, 0.0),
    ("phase_p50ps", 25, 0.10, 0.45, 22.5, 0.0),
    ("offset_m50m", 25, 0.10, 0.45, 0.0, -0.05),
    ("offset_p50m", 25, 0.10, 0.45, 0.0, 0.05),
    ("combined_m25ps", 100, 0.05, 0.30, -11.25, 0.0),
    ("combined_p25ps", 100, 0.05, 0.30, 11.25, 0.0),
)
QUALIFICATION_STRESS_IDS = {
    "baseline", "load10", "load50", "data200m", "clock300m", "clock600m",
    "phase_m50ps", "phase_m25ps", "phase_p25ps", "phase_p50ps",
}
BIAS_VALUES = (0.90, 1.00, 1.10, 1.20, 1.30)
SCALAR = re.compile(
    r"^(sample_\d+|even_cm_avg|odd_cm_avg|supply_current)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "sampler_tb.spice.in").read_text()
    ui = 1 / 2.5e9
    measures = [
        f"meas tran sample_{index} find {'even_diff' if index % 2 == 0 else 'odd_diff'} "
        f"at={(index + 1) * ui + 50e-12:.12g}"
        for index in SAMPLE_INDICES
    ]
    specifications = []
    for environment in ENVIRONMENTS:
        env_id, mos, resistor, vdd, temperature, cm_fraction = environment
        common_mode = vdd * cm_fraction
        for stress in STRESSES:
            stress_id, load_ff, data_peak, clock_peak, phase, input_offset = stress
            for bias in BIAS_VALUES:
                case_id = f"{env_id}_{stress_id}_b{bias:.2f}".replace(".", "p")
                values = {
                    "MOS_CORNER": mos, "RES_CORNER": resistor,
                    "DUT_INCLUDE": f".include {args.pex}", "DUT_SUBCKT": "cdr_sampler_pex",
                    "TEMP_C": str(temperature), "VDD_SOURCE": f"{vdd:.2f}",
                    "DATA_P_PWL": pwl(True, common_mode + input_offset, data_peak, ui, 20e-12),
                    "DATA_N_PWL": pwl(False, common_mode - input_offset, data_peak, ui, 20e-12),
                    "CLOCK_CM_V": f"{common_mode:.6f}", "CLOCK_PEAK_V": f"{clock_peak:.3f}",
                    "CLOCK_HZ": "1.25g", "CLOCK_PHASE_DEG": f"{phase:.3f}",
                    "CLOCK_N_PHASE_DEG": f"{180 + phase:.3f}", "VBIAS_V": f"{bias:.2f}",
                    "CLOAD_F": f"{load_ff}f", "TSTEP_S": f"{ui / 100:.12g}",
                    "TSTOP_S": f"{(len(BITS) + 1) * ui:.12g}",
                    "MEAS_START_S": f"{4 * ui:.12g}",
                    "SAMPLE_MEASURES": "\n".join(measures),
                }
                specifications.append((case_id, environment, stress, bias, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        case_id, environment, stress, bias, values = specification
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
        vdd = float(environment[3])
        complete = return_code == 0 and len(observed) == len(SAMPLE_INDICES) + 3
        passed = (complete and min(even_margin, odd_margin) >= 0.10
                  and abs(even_margin - odd_margin) <= 0.12
                  and 0.50 <= observed["even_cm_avg"] <= vdd - 0.10
                  and 0.50 <= observed["odd_cm_avg"] <= vdd - 0.10
                  and 0.0005 <= observed["supply_current"] <= 0.010)
        return {"id": case_id, "environment": environment[0], "stress": stress[0],
                "bias_v": bias, "even_margin_v": even_margin, "odd_margin_v": odd_margin,
                "observed": observed, "result": "pass" if passed else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    groups = []
    for environment in ENVIRONMENTS:
        env_id = environment[0]
        members = [case for case in cases if case["environment"] == env_id]
        candidates = []
        for bias in BIAS_VALUES:
            biased = [case for case in members if case["bias_v"] == bias
                      and case["stress"] in QUALIFICATION_STRESS_IDS]
            if (len(biased) == len(QUALIFICATION_STRESS_IDS)
                    and all(case["result"] == "pass" for case in biased)):
                candidates.append((min(min(case["even_margin_v"], case["odd_margin_v"])
                                           for case in biased), bias))
        selected = max(candidates)[1] if candidates else None
        groups.append({"environment": env_id, "valid_bias_count": len(candidates),
                       "selected_bias_v": selected,
                       "result": "pass" if selected is not None else "fail"})
    complete = sum(len(case["observed"]) == len(SAMPLE_INDICES) + 3 for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    passed = complete == len(cases) and passing_groups == len(groups)
    result = {"schema_version": 1, "extraction": "full_rc",
              "result": "pass" if passed else "fail", "case_count": len(cases),
              "complete_case_count": complete, "group_count": len(groups),
              "passing_group_count": passing_groups,
              "adversarial_case_count": sum(case["stress"] not in QUALIFICATION_STRESS_IDS
                                            for case in cases),
              "adversarial_passing_case_count": sum(
                  case["result"] == "pass" and case["stress"] not in QUALIFICATION_STRESS_IDS
                  for case in cases),
              "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cdr_sampler robustness: {complete}/{len(cases)} complete; "
          f"{passing_groups}/{len(groups)} environments pass")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
