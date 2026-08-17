#!/usr/bin/env python3
"""Exercise extracted phase calibration versus clock, input, load, and quadrature."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(
    r"^(phase_delay|b_delay|diff_high|diff_low|output_cm|supply_current|duty_high)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)
CONTROLS = (
    (1.30, 0.30), (1.30, 0.50), (1.30, 0.65), (1.30, 0.69),
    (1.30, 0.72), (1.30, 0.75), (1.30, 0.775), (1.30, 0.80), (1.30, 0.85),
    (1.30, 0.88), (1.30, 0.90),
    (1.29, 0.93),
    (1.265, 0.975),
    (1.25, 1.00), (1.20, 1.10), (1.15, 1.15), (1.10, 1.20), (1.00, 1.25),
    (0.975, 1.265),
    (0.93, 1.29),
    (0.90, 1.30), (0.88, 1.30), (0.85, 1.30), (0.80, 1.30),
    (0.775, 1.30), (0.75, 1.30), (0.72, 1.30), (0.69, 1.30), (0.65, 1.30),
    (0.50, 1.30), (0.30, 1.30),
)
CONDITIONS = (
    ("clock_1p00g", 1.00e9, 0.20, 50e-15, 90.0),
    ("nominal", 1.25e9, 0.20, 50e-15, 90.0),
    ("clock_1p50g", 1.50e9, 0.20, 50e-15, 90.0),
    ("input_100mv", 1.25e9, 0.10, 50e-15, 90.0),
    ("input_300mv", 1.25e9, 0.30, 50e-15, 90.0),
    ("load_25f", 1.25e9, 0.20, 25e-15, 90.0),
    ("load_100f", 1.25e9, 0.20, 100e-15, 90.0),
    ("quadrature_75deg", 1.25e9, 0.20, 50e-15, 75.0),
    ("quadrature_105deg", 1.25e9, 0.20, 50e-15, 105.0),
)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 2:
        parser.error("--jobs must be 1 or 2")
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "transient_tb.spice.in").read_text()

    specifications = []
    for condition, frequency, amplitude, load, quadrature in CONDITIONS:
        period = 1 / frequency
        for code, (ctrl_a, ctrl_b) in enumerate(CONTROLS):
            values = {
                "MOS_CORNER": "typical", "RES_CORNER": "res_typical",
                "DUT_INCLUDE": f".include {args.pex}", "DUT_SUBCKT": "phase_interpolator_pex",
                "TEMP_C": "27", "VDD_V": "3.30", "VCM_V": "1.65",
                "INPUT_PEAK_V": f"{amplitude:.6g}", "FREQ_HZ": f"{frequency:.9g}",
                "B_P_PHASE_DEG": f"{360 - quadrature:.6g}",
                "B_N_PHASE_DEG": f"{180 - quadrature:.6g}",
                "CTRL_A_V": f"{ctrl_a:.3f}", "CTRL_B_V": f"{ctrl_b:.3f}",
                "VBIAS_BUF_V": "1.15", "CLOAD_F": f"{load:.9g}",
                "TSTEP_S": f"{period / 200:.9g}", "TSTOP_S": f"{6 * period:.9g}",
                "MEAS_START_S": f"{3 * period:.9g}",
            }
            specifications.append((condition, code, period, values))

    def simulate(specification: tuple[object, ...]) -> dict[str, object]:
        condition, code, period, values = specification
        deck = args.work / f"{condition}_c{code}.spice"
        log = args.work / f"{condition}_c{code}.log"
        deck.write_text(instantiate(template, values))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=60, check=False)
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        required = {"phase_delay", "b_delay", "diff_high", "diff_low", "output_cm",
                    "supply_current", "duty_high"}
        output_peak = max(observed.get("diff_high", 0), -observed.get("diff_low", 0)) / 2
        electrical = (run.returncode == 0 and required <= observed.keys()
                      and observed["diff_high"] >= 0.15 and observed["diff_low"] <= -0.15
                      and abs(observed["diff_high"] + observed["diff_low"]) <= 0.020
                      and observed["output_cm"] - output_peak >= 0.25
                      and observed["output_cm"] + output_peak <= 3.20
                      and 0.001 <= observed["supply_current"] <= 0.010
                      and abs((observed["duty_high"] % float(period))
                              - float(period) / 2) <= 12e-12)
        return {"condition": condition, "code": code, "observed": observed,
                "result": "pass" if electrical else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))

    groups = []
    for condition, frequency, amplitude, load, quadrature in CONDITIONS:
        members = [case for case in cases if case["condition"] == condition]
        members.sort(key=lambda case: int(case["code"]))
        valid = len(members) == len(CONTROLS) and all(case["result"] == "pass" for case in members)
        metrics: dict[str, object] = {}
        if valid:
            period = 1 / frequency
            delays = [float(case["observed"]["phase_delay"]) % period for case in members]
            span = delays[-1] - delays[0]
            input_span = sum(float(case["observed"]["b_delay"]) for case in members) / len(members)
            targets = [delays[0] + fraction * span for fraction in (0, 0.25, 0.5, 0.75, 1)]
            selected = [min(range(len(delays)), key=lambda index: abs(delays[index] - target))
                        for target in targets]
            errors = [delays[index] - target for index, target in zip(selected, targets)]
            metrics = {"span_s": span, "input_quadrature_s": input_span,
                       "selected_codes": selected, "phase_errors_s": errors,
                       "maximum_phase_error_s": max(abs(error) for error in errors)}
            valid = (all(a < b for a, b in zip(delays, delays[1:]))
                     and abs(span - input_span) <= 18e-12
                     and all(a < b for a, b in zip(selected, selected[1:]))
                     and max(abs(error) for error in errors) <= 12e-12)
        groups.append({"condition": condition, "frequency_hz": frequency,
                       "input_peak_v": amplitude, "load_f": load,
                       "quadrature_deg": quadrature, "observed": metrics,
                       "result": "pass" if valid else "fail"})

    passing = sum(group["result"] == "pass" for group in groups)
    result = {"schema_version": 1, "extraction": "full_rc",
              "result": "pass" if passing == len(groups) else "fail",
              "case_count": len(cases), "group_count": len(groups),
              "passing_group_count": passing, "groups": groups, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"phase_interpolator robustness: {passing}/{len(groups)} groups pass")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
