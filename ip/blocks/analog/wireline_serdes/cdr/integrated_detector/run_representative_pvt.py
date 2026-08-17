#!/usr/bin/env python3
"""Calibrate edge phase for the integrated detector over representative PVT."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

from run_phase_offset import (SAMPLE_CYCLES, SCALAR, SCALAR_NAMES, alternating_pwl,
                              instantiate, sample_measures)

ENVIRONMENTS = (
    ("nominal", "typical", "res_typical", 3.30, 27, 0.70, 0.80),
    ("fast_cold_lowcm", "ff", "res_ff", 3.63, -40, 0.60, 0.80),
    ("fast_hot_lowv", "ff", "res_ss", 2.97, 125, 0.80, 0.60),
    ("slow_hot_lowcm", "ss", "res_ss", 2.97, 125, 0.60, 0.85),
    ("slow_cold_highcm", "ss", "res_ff", 3.63, -40, 0.80, 0.95),
    ("typ_cold_lowv", "typical", "res_ff", 2.97, -40, 0.70, 0.90),
    ("typ_hot_highv", "typical", "res_ss", 3.63, 125, 0.70, 0.70),
    ("fast_nom_highcm", "ff", "res_typical", 3.30, 27, 0.80, 0.70),
    ("slow_nom_lowcm", "ss", "res_typical", 3.30, 27, 0.60, 0.95),
)
EDGE_PHASES_DEG = (-101.25, -112.5, -123.75, -135.0, -146.25, -157.5, -168.75)
OFFSETS_S = (-80e-12, -40e-12, 40e-12, 80e-12)
SAMPLER_BIASES_V = (0.90, 1.00, 1.10, 1.20, 1.30)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--only-environment", choices=tuple(env[0] for env in ENVIRONMENTS))
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "integrated_detector/phase_offset_tb.spice.in").read_text()
    ui, edge, count = 1 / 2.5e9, 20e-12, 24
    environments = tuple(env for env in ENVIRONMENTS
                         if args.only_environment in (None, env[0]))
    specifications = []
    for environment in environments:
        env_id, mos, resistor, vdd, temperature, cm_fraction, pd_bias = environment
        common_mode = vdd * cm_fraction
        for sampler_bias in SAMPLER_BIASES_V:
            for phase in EDGE_PHASES_DEG:
                for offset in OFFSETS_S:
                    case_id = (
                        f"{env_id}_sb{sampler_bias:.2f}_phase_{phase:+.2f}_"
                        f"offset_{offset/1e-12:+.0f}ps"
                    ).replace("+", "p").replace("-", "m").replace(".", "p")
                    values = {
                        "MOS_CORNER": mos, "RES_CORNER": resistor,
                        "TEMP_C": str(temperature), "VDD_V": f"{vdd:.2f}",
                        "CLOCK_CM_V": f"{common_mode:.6f}", "CLOCK_PEAK_V": "0.45",
                        "EDGE_PHASE_DEG": f"{phase:.2f}",
                        "EDGE_N_PHASE_DEG": f"{phase + 180:.2f}",
                        "DATA_P_PWL": alternating_pwl(True, common_mode, 0.14, ui,
                                                       edge, offset, count),
                        "DATA_N_PWL": alternating_pwl(False, common_mode, 0.14, ui,
                                                       edge, offset, count),
                        "VBIAS_SAMPLER_V": f"{sampler_bias:.2f}",
                        "VBIAS_PD_V": f"{pd_bias:.2f}",
                        "TSTEP_S": f"{ui / 100:.12g}",
                        "TSTOP_S": f"{count * ui:.12g}",
                        "MEAS_START_S": f"{8 * ui:.12g}",
                        "SAMPLE_MEASURES": sample_measures(ui),
                    }
                    specifications.append((case_id, environment, sampler_bias, phase,
                                           offset, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        case_id, environment, sampler_bias, phase, offset, values = specification
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck_text = instantiate(template, values)
        reusable = (deck.exists() and log.exists() and deck.read_text() == deck_text
                    and len({name for name, _ in SCALAR.findall(log.read_text())})
                    == len(SCALAR_NAMES) + 4 * len(SAMPLE_CYCLES))
        if reusable:
            return_code = 0
        else:
            deck.write_text(deck_text)
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=120, check=False)
            return_code = run.returncode
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        expected_early_sign = 1 if offset < 0 else -1
        signed = []
        for cycle in SAMPLE_CYCLES:
            signed.extend((expected_early_sign * observed.get(f"early0_{cycle}", 0.0),
                           -expected_early_sign * observed.get(f"late0_{cycle}", 0.0),
                           expected_early_sign * observed.get(f"early1_{cycle}", 0.0),
                           -expected_early_sign * observed.get(f"late1_{cycle}", 0.0)))
        complete = (return_code == 0
                    and len(observed) == len(SCALAR_NAMES) + 4 * len(SAMPLE_CYCLES))
        minimum_margin = min(signed)
        required_margin = 0.10 if abs(offset) <= 40e-12 else 0.075
        passed = (complete and minimum_margin >= required_margin
                  and 0.003 <= observed["supply_current"] <= 0.040)
        return {"id": case_id, "environment": environment[0],
                "sampler_bias_v": sampler_bias, "edge_phase_deg": phase,
                "transition_offset_s": offset,
                "required_margin_v": required_margin,
                "minimum_directional_margin_v": minimum_margin,
                "observed": observed, "result": "pass" if passed else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    groups = []
    for environment in environments:
        env_id = environment[0]
        candidates = []
        for sampler_bias in SAMPLER_BIASES_V:
            for phase in EDGE_PHASES_DEG:
                members = [case for case in cases if case["environment"] == env_id
                           and case["sampler_bias_v"] == sampler_bias
                           and case["edge_phase_deg"] == phase]
                if len(members) == len(OFFSETS_S) and all(case["result"] == "pass"
                                                          for case in members):
                    candidates.append({"sampler_bias_v": sampler_bias,
                                       "edge_phase_deg": phase,
                                       "minimum_margin_v": min(
                                           case["minimum_directional_margin_v"]
                                           for case in members)})
        selected = (max(candidates, key=lambda candidate: candidate["minimum_margin_v"])
                    if candidates else None)
        groups.append({"environment": env_id,
                       "phase_detector_bias_v": environment[6],
                       "valid_setting_count": len(candidates), "selected_setting": selected,
                       "result": "pass" if selected else "fail"})
    complete_count = sum(len(case["observed"]) == len(SCALAR_NAMES)
                         + 4 * len(SAMPLE_CYCLES) for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    passed = complete_count == len(cases) and passing_groups == len(groups)
    result = {"schema_version": 1, "result": "pass" if passed else "fail",
              "case_count": len(cases), "complete_case_count": complete_count,
              "group_count": len(groups), "passing_group_count": passing_groups,
              "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cdr_alexander_frontend representative PVT: {complete_count}/{len(cases)} "
          f"complete; {passing_groups}/{len(groups)} environments calibrate")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
