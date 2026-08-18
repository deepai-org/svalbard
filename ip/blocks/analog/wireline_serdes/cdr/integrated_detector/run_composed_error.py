#!/usr/bin/env python3
"""Compose two samplers, two Alexander boundaries, and the error combiner."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

from run_phase_offset import SAMPLE_CYCLES, alternating_pwl, instantiate
from run_representative_pvt import (EDGE_PHASES_DEG, ENVIRONMENTS, OFFSETS_S,
                                    SAMPLER_BIASES_V)

ERROR_BIASES_V = (0.75, 0.90, 1.05)
MEASURE = re.compile(r"^(err[01]_\d+|output_cm_avg|supply_current)\s*=\s*([-+0-9.eE]+)",
                     re.MULTILINE)


def error_measures(ui: float, sample_delay: float) -> str:
    measures = []
    for cycle in SAMPLE_CYCLES:
        for lane, edge_index in ((0, 2 * cycle + 1), (1, 2 * cycle + 2)):
            time = edge_index * ui + sample_delay
            measures.append(f"meas tran err{lane}_{cycle} find err at={time:.12g}")
    return "\n".join(measures)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sampler-pex", type=Path)
    parser.add_argument("--detector-pex", type=Path)
    parser.add_argument("--error-pex", type=Path)
    parser.add_argument("--error-calibration", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--sweep-edge-phase", action="store_true")
    parser.add_argument("--sweep-sampler-bias", action="store_true")
    parser.add_argument("--sample-delay-ps", type=float, default=150.0)
    parser.add_argument("--only-environment", choices=tuple(env[0] for env in ENVIRONMENTS))
    parser.add_argument("--allow-partial-groups", action="store_true")
    args = parser.parse_args()
    pex_paths = (args.sampler_pex, args.detector_pex, args.error_pex)
    if any(pex_paths) and not all(pex_paths):
        parser.error("all three PEX paths are required together")
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    calibration = json.loads(args.calibration.read_text())
    if "groups" in calibration:
        selected = {group["environment"]: group["selected_setting"]
                    for group in calibration["groups"]}
    else:
        selected = {item["environment"]: item
                    for item in calibration["selected_settings"]}
    error_selected = None
    if args.error_calibration:
        error_calibration = json.loads(args.error_calibration.read_text())
        if error_calibration.get("result") != "pass":
            parser.error("error calibration must be a passing composition")
        error_selected = {group["environment"]: group["selected"]["error_bias_v"]
                          for group in error_calibration["groups"]}
    template = (args.source / "integrated_detector/error_combiner_tb.spice.in").read_text()
    extracted = all(pex_paths)
    if extracted:
        includes = "\n".join(f".include {path}" for path in pex_paths)
        subckts = ("cdr_sampler_pex", "cml_alexander_boundary_pex",
                   "cml_phase_error_filter_pex")
    else:
        includes = "\n".join((".include /src/cdr_sampler.spice",
                               ".include /src/phase_detector/cml_phase_detector.spice",
                               ".include /src/phase_error_filter/phase_error_filter.spice"))
        subckts = ("cdr_sampler", "cml_alexander_boundary", "cml_phase_error_filter")

    ui, edge, count = 1 / 2.5e9, 20e-12, 24
    specifications = []
    environments = tuple(environment for environment in ENVIRONMENTS
                         if args.only_environment in (None, environment[0]))
    sample_delay = args.sample_delay_ps * 1e-12
    if not 100e-12 <= sample_delay <= 350e-12:
        parser.error("--sample-delay-ps must be between 100 and 350")
    for environment in environments:
        env_id, mos, resistor, vdd, temperature, cm_fraction, pd_bias = environment
        setting = selected[env_id]
        common_mode = vdd * cm_fraction
        edge_phases = EDGE_PHASES_DEG if args.sweep_edge_phase else (setting["edge_phase_deg"],)
        sampler_biases = (SAMPLER_BIASES_V if args.sweep_sampler_bias
                          else (setting["sampler_bias_v"],))
        error_biases = ((error_selected[env_id],) if error_selected is not None
                        else ERROR_BIASES_V)
        for sampler_bias in sampler_biases:
            for edge_phase in edge_phases:
                for error_bias in error_biases:
                    for offset in OFFSETS_S:
                        case_id = (
                            f"{env_id}_sb{sampler_bias:.2f}_phase{edge_phase:+.2f}_"
                            f"eb{error_bias:.2f}_offset_{offset/1e-12:+.0f}ps"
                        )
                        case_id = (case_id.replace("+", "p").replace("-", "m")
                                   .replace(".", "p"))
                        values = {
                            "MOS_CORNER": mos, "RES_CORNER": resistor,
                            "DUT_INCLUDES": includes, "SAMPLER_SUBCKT": subckts[0],
                            "PD_SUBCKT": subckts[1], "ERROR_SUBCKT": subckts[2],
                            "TEMP_C": str(temperature), "VDD_V": f"{vdd:.2f}",
                            "CLOCK_CM_V": f"{common_mode:.6f}", "CLOCK_PEAK_V": "0.45",
                            "EDGE_PHASE_DEG": f"{edge_phase:.2f}",
                            "EDGE_N_PHASE_DEG": f"{edge_phase + 180:.2f}",
                            "DATA_P_PWL": alternating_pwl(
                                True, common_mode, 0.14, ui, edge, offset, count),
                            "DATA_N_PWL": alternating_pwl(
                                False, common_mode, 0.14, ui, edge, offset, count),
                            "VBIAS_SAMPLER_V": f"{sampler_bias:.2f}",
                            "VBIAS_PD_V": f"{pd_bias:.2f}",
                            "VBIAS_ERROR_V": f"{error_bias:.2f}",
                            "TSTEP_S": f"{ui / 100:.12g}",
                            "TSTOP_S": f"{count * ui:.12g}",
                            "MEAS_START_S": f"{8 * ui:.12g}",
                            "ERROR_MEASURES": error_measures(ui, sample_delay),
                        }
                        specifications.append((case_id, env_id, vdd, offset,
                                               sampler_bias, edge_phase, error_bias,
                                               values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        (case_id, env_id, vdd, offset, sampler_bias, edge_phase, error_bias,
         values) = specification
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, values))
        with log.open("w") as output:
            try:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=args.timeout_s,
                                     check=False)
                return_code = run.returncode
            except subprocess.TimeoutExpired:
                return_code = 124
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        expected = 1 if offset < 0 else -1
        margins = [expected * observed.get(f"err{lane}_{cycle}", -99 * expected)
                   for cycle in SAMPLE_CYCLES for lane in (0, 1)]
        complete = return_code == 0 and len(observed) == 8
        passed = (complete and min(margins) >= 0.10
                  and 0.35 <= observed.get("output_cm_avg", 0) <= float(vdd) - 0.20
                  and 0.003 <= observed.get("supply_current", 0) <= 0.060)
        return {"id": case_id, "environment": env_id, "sampler_bias_v": sampler_bias,
                "edge_phase_deg": edge_phase,
                "error_bias_v": error_bias,
                "transition_offset_s": offset, "minimum_signed_error_v": min(margins),
                "observed": observed, "result": "pass" if passed else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    groups = []
    for environment in environments:
        env_id = environment[0]
        candidates = []
        phase_values = EDGE_PHASES_DEG if args.sweep_edge_phase else (selected[env_id]["edge_phase_deg"],)
        sampler_values = (SAMPLER_BIASES_V if args.sweep_sampler_bias
                          else (selected[env_id]["sampler_bias_v"],))
        error_biases = ((error_selected[env_id],) if error_selected is not None
                        else ERROR_BIASES_V)
        for sampler_bias in sampler_values:
            for phase in phase_values:
                for bias in error_biases:
                    members = [case for case in cases if case["environment"] == env_id
                               and case["sampler_bias_v"] == sampler_bias
                               and case["edge_phase_deg"] == phase
                               and case["error_bias_v"] == bias]
                    if (len(members) == len(OFFSETS_S)
                            and all(case["result"] == "pass" for case in members)):
                        candidates.append({
                            "sampler_bias_v": sampler_bias,
                            "edge_phase_deg": phase,
                            "error_bias_v": bias,
                            "minimum_signed_error_v": min(
                                case["minimum_signed_error_v"] for case in members),
                        })
        chosen = max(candidates, key=lambda item: item["minimum_signed_error_v"],
                     default=None)
        groups.append({"environment": env_id, "passing_bias_count": len(candidates),
                       "selected": chosen, "result": "pass" if chosen else "fail"})
    complete_count = sum(len(case["observed"]) == 8 for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    result = {"schema_version": 1, "result": "pass" if complete_count == len(cases)
              and passing_groups == len(groups) else "fail",
              "mode": "full_rc_composed" if extracted else "schematic_composed",
              "case_count": len(cases), "complete_case_count": complete_count,
              "edge_phase_recalibrated": args.sweep_edge_phase,
              "sampler_bias_recalibrated": args.sweep_sampler_bias,
              "error_bias_calibrated": error_selected is not None,
              "sample_delay_s": sample_delay,
              "group_count": len(groups), "passing_group_count": passing_groups,
              "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"composed error front end: {complete_count}/{len(cases)} complete; "
          f"{passing_groups}/{len(groups)} environments calibrate")
    if result["result"] != "pass" and not (args.allow_partial_groups
                                            and complete_count == len(cases)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
