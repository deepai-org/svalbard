#!/usr/bin/env python3
"""Verify the stacked CML XOR truth table at static and 2.5 GT/s rates."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

BIAS_VALUES = (0.60, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20)
BITS_A = (0, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 1, 1)
BITS_B = (0, 1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 0)
SAMPLE_INDICES = tuple(range(4, 22))
SCALAR = re.compile(r"^(sample_\d+|outcm_avg|supply_current)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def pwl(bits: tuple[int, ...], positive: bool, common_mode: float, peak: float,
        ui: float, edge: float) -> str:
    level = lambda bit: common_mode + (peak if (bit == 1) == positive else -peak)
    points = [(0.0, level(bits[0]))]
    previous = bits[0]
    for index, bit in enumerate(bits[1:], start=1):
        if bit == previous:
            continue
        center = index * ui
        points.extend(((center - edge / 2, level(previous)),
                       (center + edge / 2, level(bit))))
        previous = bit
    points.append(((len(bits) + 1) * ui, level(previous)))
    return " ".join(f"{time:.12g} {voltage:.6f}" for time, voltage in points)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "xor_tb.spice.in").read_text()
    ui = 1 / 2.5e9
    measures = [f"meas tran sample_{index} find outdiff at={(index + 0.5) * ui:.12g}"
                for index in SAMPLE_INDICES]
    cases = []
    for bias in BIAS_VALUES:
        values = {
            "MOS_CORNER": "typical", "RES_CORNER": "res_typical", "TEMP_C": "27",
            "VDD_V": "3.30", "AP_PWL": pwl(BITS_A, True, 2.20, 0.14, ui, 20e-12),
            "AN_PWL": pwl(BITS_A, False, 2.20, 0.14, ui, 20e-12),
            "BP_PWL": pwl(BITS_B, True, 2.20, 0.14, ui, 20e-12),
            "BN_PWL": pwl(BITS_B, False, 2.20, 0.14, ui, 20e-12),
            "VBIAS_V": f"{bias:.2f}", "CLOAD_F": "25f", "TSTEP_S": "4p",
            "TSTOP_S": f"{(len(BITS_A) + 1) * ui:.12g}",
            "MEAS_START_S": f"{4 * ui:.12g}", "MEASURES": "\n".join(measures),
        }
        case_id = f"bias_{bias:.2f}"
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, values))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=90, check=False)
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        signed = [observed.get(f"sample_{index}", 0.0)
                  * (1 if BITS_A[index] ^ BITS_B[index] else -1)
                  for index in SAMPLE_INDICES]
        complete = run.returncode == 0 and len(observed) == len(SAMPLE_INDICES) + 2
        passed = (complete and min(signed) >= 0.10
                  and 0.50 <= observed["outcm_avg"] <= 3.10
                  and 0.0001 <= observed["supply_current"] <= 0.010)
        cases.append({"bias_v": bias, "minimum_signed_xor_v": min(signed),
                      "observed": observed, "result": "pass" if passed else "fail"})
    passing = sum(case["result"] == "pass" for case in cases)
    result = {"schema_version": 1, "result": "pass" if passing else "fail",
              "case_count": len(cases), "passing_case_count": passing, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cml_xor nominal: {passing}/{len(cases)} bias points pass")
    if not passing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
