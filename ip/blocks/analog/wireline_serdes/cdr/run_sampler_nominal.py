#!/usr/bin/env python3
"""Sweep dual-edge CML sampler bias on a deterministic 2.5 GT/s pattern."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

BITS = (1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1, 1, 1, 0,
        1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1)
SAMPLE_INDICES = tuple(range(4, 24))
BIAS_VALUES = (0.80, 0.90, 1.00, 1.10, 1.20, 1.30, 1.40)
SCALAR = re.compile(
    r"^(sample_\d+|even_cm_avg|odd_cm_avg|supply_current)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def pwl(positive: bool, common_mode: float, peak: float, ui: float, edge: float) -> str:
    points: list[tuple[float, float]] = []
    initial = BITS[0]
    level = common_mode + (peak if initial == positive else -peak)
    points.append((0.0, level))
    previous = initial
    for index, bit in enumerate(BITS[1:], start=1):
        if bit == previous:
            continue
        center = (index + 0.5) * ui
        old = common_mode + (peak if previous == positive else -peak)
        new = common_mode + (peak if bit == positive else -peak)
        points.extend(((center - edge / 2, old), (center + edge / 2, new)))
        previous = bit
    points.append(((len(BITS) + 1) * ui, common_mode + (peak if previous == positive else -peak)))
    return " ".join(f"{time:.12g} {voltage:.6f}" for time, voltage in points)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "sampler_tb.spice.in").read_text()
    ui = 1 / 2.5e9
    sample_measures = []
    for index in SAMPLE_INDICES:
        output = "even_diff" if index % 2 == 0 else "odd_diff"
        time = (index + 1) * ui + 50e-12
        sample_measures.append(f"meas tran sample_{index} find {output} at={time:.12g}")
    cases = []
    for bias in BIAS_VALUES:
        values = {
            "MOS_CORNER": "typical", "RES_CORNER": "res_typical",
            "DUT_INCLUDE": (f".include {args.pex}" if args.pex else
                            ".include /src/cdr_sampler.spice"),
            "DUT_SUBCKT": "cdr_sampler_pex" if args.pex else "cdr_sampler",
            "TEMP_C": "27", "VDD_V": "3.30",
            "DATA_P_PWL": pwl(True, 2.20, 0.10, ui, 20e-12),
            "DATA_N_PWL": pwl(False, 2.20, 0.10, ui, 20e-12),
            "CLOCK_CM_V": "2.20", "CLOCK_PEAK_V": "0.45", "CLOCK_HZ": "1.25g",
            "VBIAS_V": f"{bias:.2f}", "CLOAD_F": "25f",
            "TSTEP_S": f"{ui / 100:.12g}", "TSTOP_S": f"{(len(BITS) + 1) * ui:.12g}",
            "MEAS_START_S": f"{4 * ui:.12g}",
            "SAMPLE_MEASURES": "\n".join(sample_measures),
        }
        case_id = f"bias_{bias:.2f}"
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, values))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=90, check=False)
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        signed = [observed.get(f"sample_{index}", 0.0) * (1 if BITS[index] else -1)
                  for index in SAMPLE_INDICES]
        complete = run.returncode == 0 and len(observed) == len(SAMPLE_INDICES) + 3
        passed = (complete and min(signed) >= 0.10
                  and 0.80 <= observed["even_cm_avg"] <= 3.10
                  and 0.80 <= observed["odd_cm_avg"] <= 3.10
                  and 0.001 <= observed["supply_current"] <= 0.010)
        cases.append({"id": case_id, "bias_v": bias, "observed": observed,
                      "minimum_signed_sample_v": min(signed),
                      "result": "pass" if passed else "fail"})
    passing = sum(case["result"] == "pass" for case in cases)
    result = {"schema_version": 1, "extraction": "full_rc" if args.pex else "schematic",
              "result": "pass" if passing else "fail", "case_count": len(cases),
              "passing_case_count": passing, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cdr_sampler nominal: {passing}/{len(cases)} bias points pass")
    if not passing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
