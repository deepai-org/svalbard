#!/usr/bin/env python3
"""Inject bounded sinusoidal supply disturbance into the extracted sampler."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

from run_sampler_aperture import selected_biases
from run_sampler_nominal import BITS, SAMPLE_INDICES, instantiate, pwl
from run_sampler_robustness import ENVIRONMENTS

DISTURBANCES = (("baseline", 0, 10e6, 0),) + tuple(
    (f"ripple{amplitude}m_{frequency / 1e6:g}m_p{phase}", amplitude, frequency, phase)
    for amplitude in (25, 50, 100)
    for frequency in (10e6, 100e6, 625e6, 1.25e9)
    for phase in (0, 90)
)
SCALAR = re.compile(
    r"^(sample_\d+|even_cm_avg|odd_cm_avg|supply_current)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--pvt", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)
    biases = selected_biases(json.loads(args.pvt.read_text()))
    missing = [environment[0] for environment in ENVIRONMENTS if environment[0] not in biases]
    if missing:
        raise SystemExit(f"PVT result lacks selected biases for: {', '.join(missing)}")
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
        for disturbance in DISTURBANCES:
            noise_id, amplitude_mv, frequency, phase = disturbance
            source = (f"{vdd:.2f}" if amplitude_mv == 0 else
                      f"SIN({vdd:.6f} {amplitude_mv / 1000:.6f} {frequency:.12g} 0 0 {phase})")
            values = {
                "MOS_CORNER": mos, "RES_CORNER": resistor,
                "DUT_INCLUDE": f".include {args.pex}", "DUT_SUBCKT": "cdr_sampler_pex",
                "TEMP_C": str(temperature), "VDD_SOURCE": source,
                "DATA_P_PWL": pwl(True, common_mode, 0.10, ui, 20e-12),
                "DATA_N_PWL": pwl(False, common_mode, 0.10, ui, 20e-12),
                "CLOCK_CM_V": f"{common_mode:.6f}", "CLOCK_PEAK_V": "0.45",
                "CLOCK_HZ": "1.25g", "CLOCK_PHASE_DEG": "0",
                "CLOCK_N_PHASE_DEG": "180", "VBIAS_V": f"{biases[env_id]:.2f}",
                "CLOAD_F": "25f", "TSTEP_S": f"{ui / 100:.12g}",
                "TSTOP_S": f"{(len(BITS) + 1) * ui:.12g}",
                "MEAS_START_S": f"{4 * ui:.12g}",
                "SAMPLE_MEASURES": "\n".join(measures),
            }
            specifications.append((env_id, environment, disturbance, biases[env_id], values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        env_id, environment, disturbance, bias, values = specification
        noise_id, amplitude_mv, frequency, phase = disturbance
        case_id = f"{env_id}_{noise_id}".replace(".", "p")
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
        return {"id": case_id, "environment": env_id, "amplitude_mv": amplitude_mv,
                "frequency_hz": frequency, "phase_deg": phase, "bias_v": bias,
                "even_margin_v": even_margin, "odd_margin_v": odd_margin,
                "observed": observed, "result": "pass" if passed else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    groups = []
    for environment in ENVIRONMENTS:
        env_id = environment[0]
        qualification = [case for case in cases if case["environment"] == env_id
                         and case["amplitude_mv"] <= 50]
        valid = len(qualification) == 17 and all(case["result"] == "pass"
                                                 for case in qualification)
        groups.append({"environment": env_id, "qualification_case_count": len(qualification),
                       "result": "pass" if valid else "fail"})
    complete = sum(len(case["observed"]) == len(SAMPLE_INDICES) + 3 for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    passed = complete == len(cases) and passing_groups == len(groups)
    result = {"schema_version": 1, "extraction": "full_rc",
              "qualified_ripple_peak_mv": 50,
              "result": "pass" if passed else "fail", "case_count": len(cases),
              "complete_case_count": complete, "group_count": len(groups),
              "passing_group_count": passing_groups,
              "adversarial_100mv_passing_case_count": sum(case["result"] == "pass"
                                                          and case["amplitude_mv"] == 100
                                                          for case in cases),
              "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cdr_sampler supply noise: {complete}/{len(cases)} complete; "
          f"{passing_groups}/{len(groups)} environments pass")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
