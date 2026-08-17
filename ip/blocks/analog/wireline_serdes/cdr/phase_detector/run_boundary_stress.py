#!/usr/bin/env python3
"""Verify fixed-code extracted phase-detector guardbands and exploratory stress."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

from run_boundary_pvt import CUR, EDGE, PREV, SAMPLE_INDICES, SCALAR
from run_xor_nominal import instantiate, pwl

ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27, 0.70),
    ("typical", "res_ff", 2.97, 125, 0.80),
    ("typical", "res_ss", 3.63, -40, 0.60),
    ("ff", "res_ff", 2.97, -40, 0.60),
    ("ff", "res_ss", 3.63, 125, 0.80),
    ("ff", "res_typical", 3.30, 27, 0.70),
    ("ss", "res_ff", 3.63, -40, 0.60),
    ("ss", "res_ss", 2.97, 125, 0.80),
    ("ss", "res_typical", 3.30, 27, 0.70),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--pvt", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument(
        "--bias-override", action="append", default=[], metavar="ENV_INDEX=VOLTS",
        help="replace the PVT-selected fixed bias for one numbered environment",
    )
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    pvt = json.loads(args.pvt.read_text())
    if pvt["result"] != "pass" or pvt.get("symbol_rate_hz") != 1.25e9:
        raise SystemExit("stress requires a passing 1.25 Gupdate/s extracted PVT result")
    template = (args.source / "boundary_tb.spice.in").read_text()
    dut_sha256 = hashlib.sha256(args.pex.read_bytes()).hexdigest()
    selected = {tuple(group["group"]): group["selected_case"] for group in pvt["groups"]}
    overrides = {}
    for assignment in args.bias_override:
        try:
            index_text, voltage_text = assignment.split("=", 1)
            index, voltage = int(index_text), float(voltage_text)
        except ValueError as error:
            parser.error(f"invalid --bias-override {assignment!r}: {error}")
        if not 0 <= index < len(ENVIRONMENTS) or not 0.45 <= voltage <= 1.15:
            parser.error(f"out-of-range --bias-override {assignment!r}")
        overrides[index] = voltage

    design = []
    for peak in (0.10, 0.14, 0.20):
        for load in (10e-15, 25e-15, 50e-15):
            design.append((f"amp{2*peak:.2f}_load{load*1e15:.0f}", 1.25e9, 20e-12,
                           peak, load, 0.0, 0.0, 0.0, 0.075))
    for rate in (1.0e9, 1.25e9, 1.5e9):
        for edge in (20e-12, 50e-12, 100e-12):
            design.append((f"rate{rate/1e9:.2f}_edge{edge*1e12:.0f}", rate, edge,
                           0.14, 25e-15, 0.0, 0.0, 0.0, 0.075))
    design.append(("combined_guardband", 1.5e9, 100e-12, 0.10, 50e-15,
                   0.0, 0.0, 0.0, 0.050))
    for frequency in (10e6, 100e6, 625e6, 1.25e9):
        for phase in (90.0, 270.0):
            design.append((f"ripple50m_{frequency:.0f}_{phase:.0f}", 1.25e9, 20e-12,
                           0.14, 25e-15, 0.05, frequency, phase, 0.075))
    exploratory = [
        ("overspeed_2x", 2.5e9, 20e-12, 0.14, 25e-15, 0.0, 0.0, 0.0, 0.10),
        ("overspeed_guardband", 1.75e9, 100e-12, 0.10, 50e-15, 0.0, 0.0, 0.0, 0.10),
        ("load100", 1.25e9, 20e-12, 0.14, 100e-15, 0.0, 0.0, 0.0, 0.10),
        ("input140m", 1.25e9, 20e-12, 0.07, 25e-15, 0.0, 0.0, 0.0, 0.10),
        ("combined_extreme", 2.5e9, 100e-12, 0.10, 100e-15, 0.0, 0.0, 0.0, 0.10),
    ]
    for frequency in (10e6, 100e6, 625e6, 1.25e9):
        for phase in (90.0, 270.0):
            exploratory.append((f"ripple100m_{frequency:.0f}_{phase:.0f}", 1.25e9,
                                20e-12, 0.14, 25e-15, 0.10, frequency, phase, 0.10))

    specifications = []
    for environment_index, environment in enumerate(ENVIRONMENTS):
        chosen = selected[environment]
        fixed_bias = overrides.get(environment_index, chosen["bias_v"])
        mos, resistor, vdd, temperature, cm_fraction = environment
        for classification, scenarios in (("design", design), ("exploratory", exploratory)):
            for scenario in scenarios:
                name, rate, edge, peak, load, ripple, frequency, phase, required_margin = scenario
                ui = 1 / rate
                measures = []
                for index in SAMPLE_INDICES:
                    time = (index + 0.5) * ui
                    measures.append(f"meas tran early_{index} find early_diff at={time:.12g}")
                    measures.append(f"meas tran late_{index} find late_diff at={time:.12g}")
                common_mode = vdd * cm_fraction
                signals = {}
                for signal_name, bits in (("PREV", PREV), ("EDGE", EDGE), ("CUR", CUR)):
                    signals[f"{signal_name}_P_PWL"] = pwl(bits, True, common_mode, peak, ui, edge)
                    signals[f"{signal_name}_N_PWL"] = pwl(bits, False, common_mode, peak, ui, edge)
                supply = (f"SIN({vdd:.6f} {ripple:.6f} {frequency:.12g} 0 0 {phase:.1f})"
                          if ripple else f"{vdd:.6f}")
                case_id = f"e{environment_index}_{classification}_{name}"
                values = {
                    "DUT_SHA256": dut_sha256, "MOS_CORNER": mos,
                    "RES_CORNER": resistor, "DUT_INCLUDE": f".include {args.pex}",
                    "DUT_SUBCKT": "cml_alexander_boundary_pex",
                    "TEMP_C": str(temperature), "VDD_SOURCE": supply,
                    "VBIAS_V": f"{fixed_bias:.2f}", "CLOAD_F": f"{load:.12g}",
                    "TSTEP_S": f"{ui/100:.12g}",
                    "TSTOP_S": f"{(len(PREV)+1)*ui:.12g}",
                    "MEAS_START_S": f"{4*ui:.12g}", "MEASURES": "\n".join(measures),
                    **signals,
                }
                specifications.append((case_id, classification, environment_index,
                                       environment, fixed_bias, name, rate, edge,
                                       peak, load, ripple, frequency, phase,
                                       required_margin, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        (case_id, classification, environment_index, environment, bias, name, rate,
         edge, peak, load, ripple, frequency, phase, required_margin, values) = specification
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck_text = instantiate(template, values)
        expected_scalars = 2 * len(SAMPLE_INDICES) + 3
        reusable = (deck.exists() and log.exists() and deck.read_text() == deck_text
                    and len({key for key, _ in SCALAR.findall(log.read_text())}) == expected_scalars)
        if reusable:
            return_code = 0
        else:
            deck.write_text(deck_text)
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=90, check=False)
            return_code = run.returncode
        observed = {key: float(value) for key, value in SCALAR.findall(log.read_text())}
        early = [observed.get(f"early_{index}", 0.0)
                 * (1 if PREV[index] ^ EDGE[index] else -1) for index in SAMPLE_INDICES]
        late = [observed.get(f"late_{index}", 0.0)
                * (1 if EDGE[index] ^ CUR[index] else -1) for index in SAMPLE_INDICES]
        complete = return_code == 0 and len(observed) == expected_scalars
        margin = min(min(early), min(late))
        vdd = float(environment[2])
        passed = (complete and margin >= required_margin
                  and 0.50 <= observed["early_cm_avg"] <= vdd - 0.15
                  and 0.50 <= observed["late_cm_avg"] <= vdd - 0.15
                  and 0.0002 <= observed["supply_current"] <= 0.020)
        return {"id": case_id, "classification": classification,
                "environment_index": environment_index, "environment": list(environment),
                "selected_bias_v": bias, "scenario": name, "symbol_rate_hz": rate,
                "edge_s": edge, "input_peak_v": peak, "load_f": load,
                "supply_ripple_peak_v": ripple, "supply_ripple_hz": frequency,
                "supply_phase_deg": phase, "required_margin_v": required_margin,
                "minimum_signed_margin_v": margin,
                "observed": observed, "result": "pass" if passed else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    design_cases = [case for case in cases if case["classification"] == "design"]
    exploratory_cases = [case for case in cases if case["classification"] == "exploratory"]
    complete_count = sum(len(case["observed"]) == 2 * len(SAMPLE_INDICES) + 3 for case in cases)
    design_passing = sum(case["result"] == "pass" for case in design_cases)
    exploratory_passing = sum(case["result"] == "pass" for case in exploratory_cases)
    passing_environments = sum(all(case["result"] == "pass" for case in design_cases
                                   if case["environment_index"] == index)
                               for index in range(len(ENVIRONMENTS)))
    passed = complete_count == len(cases) and design_passing == len(design_cases)
    result = {"schema_version": 1, "result": "pass" if passed else "fail",
              "pex_sha256": dut_sha256, "pvt_sha256": hashlib.sha256(args.pvt.read_bytes()).hexdigest(),
              "bias_overrides_v": {str(key): value for key, value in sorted(overrides.items())},
              "case_count": len(cases), "complete_case_count": complete_count,
              "design_case_count": len(design_cases), "design_passing_case_count": design_passing,
              "exploratory_case_count": len(exploratory_cases),
              "exploratory_passing_case_count": exploratory_passing,
              "environment_count": len(ENVIRONMENTS),
              "passing_environment_count": passing_environments, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cml_alexander_boundary stress: {complete_count}/{len(cases)} complete; "
          f"design {design_passing}/{len(design_cases)}; "
          f"exploratory {exploratory_passing}/{len(exploratory_cases)}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
