#!/usr/bin/env python3
"""Measure the extracted sampler's data-transition window around each clock edge."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

from run_sampler_nominal import SAMPLE_INDICES, instantiate
from run_sampler_robustness import ENVIRONMENTS

BITS = tuple(index % 2 for index in range(28))
SHIFTS_PS = tuple(range(-240, 241, 20))
SCALAR = re.compile(
    r"^(sample_\d+|even_cm_avg|odd_cm_avg|supply_current)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


def shifted_pwl(positive: bool, common_mode: float, peak: float, ui: float,
                edge: float, shift: float) -> str:
    points = [(0.0, common_mode + (peak if BITS[0] == positive else -peak))]
    for index, bit in enumerate(BITS[1:], start=1):
        center = (index + 0.5) * ui + shift
        old = common_mode + (peak if BITS[index - 1] == positive else -peak)
        new = common_mode + (peak if bit == positive else -peak)
        points.extend(((center - edge / 2, old), (center + edge / 2, new)))
    points.append(((len(BITS) + 1) * ui,
                   common_mode + (peak if BITS[-1] == positive else -peak)))
    return " ".join(f"{time:.12g} {voltage:.6f}" for time, voltage in points)


def selected_biases(pvt: dict[str, object]) -> dict[str, float]:
    selected: dict[str, float] = {}
    groups = pvt.get("groups", [])
    for environment in ENVIRONMENTS:
        env_id, mos, resistor, vdd, temperature, cm_fraction = environment
        for group in groups:
            key = group.get("group", [])
            if (len(key) == 5 and key[0] == mos and key[1] == resistor
                    and abs(float(key[2]) - vdd) < 1e-6 and int(key[3]) == temperature
                    and abs(float(key[4]) - cm_fraction) < 1e-6):
                case = group.get("selected_case")
                if case:
                    selected[env_id] = float(case["bias_v"])
                break
    return selected


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
        for shift_ps in SHIFTS_PS:
            values = {
                "MOS_CORNER": mos, "RES_CORNER": resistor,
                "DUT_INCLUDE": f".include {args.pex}", "DUT_SUBCKT": "cdr_sampler_pex",
                "TEMP_C": str(temperature), "VDD_SOURCE": f"{vdd:.2f}",
                "DATA_P_PWL": shifted_pwl(True, common_mode, 0.10, ui, 20e-12,
                                           shift_ps * 1e-12),
                "DATA_N_PWL": shifted_pwl(False, common_mode, 0.10, ui, 20e-12,
                                           shift_ps * 1e-12),
                "CLOCK_CM_V": f"{common_mode:.6f}", "CLOCK_PEAK_V": "0.45",
                "CLOCK_HZ": "1.25g", "CLOCK_PHASE_DEG": "0",
                "CLOCK_N_PHASE_DEG": "180", "VBIAS_V": f"{biases[env_id]:.2f}",
                "CLOAD_F": "25f", "TSTEP_S": "2p",
                "TSTOP_S": f"{(len(BITS) + 1) * ui:.12g}",
                "MEAS_START_S": f"{4 * ui:.12g}",
                "SAMPLE_MEASURES": "\n".join(measures),
            }
            specifications.append((env_id, environment, shift_ps, biases[env_id], values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        env_id, environment, shift_ps, bias, values = specification
        case_id = f"{env_id}_shift_{int(shift_ps):+d}ps".replace("+", "p").replace("-", "m")
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
        return {"id": case_id, "environment": env_id, "shift_ps": shift_ps,
                "bias_v": bias, "even_margin_v": even_margin, "odd_margin_v": odd_margin,
                "observed": observed, "result": "pass" if passed else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    groups = []
    for environment in ENVIRONMENTS:
        env_id = environment[0]
        members = sorted((case for case in cases if case["environment"] == env_id),
                         key=lambda case: case["shift_ps"])
        passing_shifts = [int(case["shift_ps"]) for case in members if case["result"] == "pass"]
        required = set(range(-80, 81, 20))
        valid = required.issubset(passing_shifts)
        groups.append({"environment": env_id, "bias_v": biases[env_id],
                       "minimum_passing_shift_ps": min(passing_shifts) if passing_shifts else None,
                       "maximum_passing_shift_ps": max(passing_shifts) if passing_shifts else None,
                       "passing_shift_count": len(passing_shifts),
                       "result": "pass" if valid else "fail"})
    complete = sum(len(case["observed"]) == len(SAMPLE_INDICES) + 3 for case in cases)
    passing_groups = sum(group["result"] == "pass" for group in groups)
    passed = complete == len(cases) and passing_groups == len(groups)
    result = {"schema_version": 1, "extraction": "full_rc", "grid_step_ps": 20,
              "required_shift_window_ps": [-80, 80],
              "result": "pass" if passed else "fail", "case_count": len(cases),
              "complete_case_count": complete, "group_count": len(groups),
              "passing_group_count": passing_groups, "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cdr_sampler aperture: {complete}/{len(cases)} complete; "
          f"{passing_groups}/{len(groups)} environments pass")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
