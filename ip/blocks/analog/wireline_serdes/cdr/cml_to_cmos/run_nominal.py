#!/usr/bin/env python3
"""Verify nominal dynamic CML-to-CMOS sensing across input and output load."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

BITS = (1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 1, 1, 0)
SAMPLE_INDICES = tuple(range(3, 12))
SAMPLE_DELAYS_S = (650e-12, 750e-12)
SCALAR = re.compile(r"^(out[pn]_\d+_\d+|supply_current)\s*=\s*([-+0-9.eE]+)",
                    re.MULTILINE)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return result


def pwl(positive: bool, common_mode: float, peak: float, interval: float,
        edge: float) -> str:
    points = [(0.0, common_mode + (peak if BITS[0] == positive else -peak))]
    previous = BITS[0]
    for index, bit in enumerate(BITS[1:], start=1):
        if bit == previous:
            continue
        center = index * interval
        old = common_mode + (peak if previous == positive else -peak)
        new = common_mode + (peak if bit == positive else -peak)
        points.extend(((center - edge / 2, old), (center + edge / 2, new)))
        previous = bit
    points.append(((len(BITS) + 1) * interval,
                   common_mode + (peak if previous == positive else -peak)))
    return " ".join(f"{time:.12g} {voltage:.6f}" for time, voltage in points)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    parser.add_argument("--eval-width-ps", type=int, default=500)
    parser.add_argument("--timeout-s", type=int, default=90,
                        help="per-case ngspice timeout (increase for full-RC PEX)")
    args = parser.parse_args()
    if not 450 <= args.eval_width_ps <= 650:
        parser.error("--eval-width-ps must be between 450 and 650")
    args.work.mkdir(parents=True, exist_ok=True)
    source_dir = (args.source / "cml_to_cmos" if
                  (args.source / "cml_to_cmos").is_dir() else args.source)
    template = (source_dir / "transient_tb.spice.in").read_text()
    dut_path = args.pex if args.pex else source_dir / "cml_to_cmos.spice"
    dut_sha256 = hashlib.sha256(dut_path.read_bytes()).hexdigest()
    interval, edge = 800e-12, 20e-12
    measures = []
    for index in SAMPLE_INDICES:
        for delay in SAMPLE_DELAYS_S:
            sample_time = index * interval + delay
            delay_ps = round(delay / 1e-12)
            measures.append(f"meas tran outP_{index}_{delay_ps} find v(OUTP) at={sample_time:.12g}")
            measures.append(f"meas tran outN_{index}_{delay_ps} find v(OUTN) at={sample_time:.12g}")
    cases = []
    for differential_input in (0.10, 0.20, 0.40):
        for load_ff in (10, 25, 50):
            peak = differential_input / 2
            values = {
                "MOS_CORNER": "typical", "TEMP_C": "27", "VDD_V": "3.30",
                "DUT_SHA256": dut_sha256,
                "DUT_INCLUDE": f".include {dut_path}",
                "DUT_SUBCKT": "cml_to_cmos_pex" if args.pex else "cml_to_cmos",
                "EVAL_WIDTH_S": f"{args.eval_width_ps}p",
                "INP_PWL": pwl(True, 2.30, peak, interval, edge),
                "INN_PWL": pwl(False, 2.30, peak, interval, edge),
                "CLOAD_F": f"{load_ff}f", "TSTOP_S": f"{len(BITS) * interval:.12g}",
                "MEASURES": "\n".join(measures),
            }
            case_id = f"input{differential_input:.2f}_load{load_ff}".replace(".", "p")
            deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
            deck_text = instantiate(template, values)
            reusable = (deck.exists() and log.exists() and deck.read_text() == deck_text
                        and len({name for name, _ in SCALAR.findall(log.read_text())})
                        == 2 * len(SAMPLE_INDICES) * len(SAMPLE_DELAYS_S) + 1)
            if reusable:
                return_code = 0
            else:
                deck.write_text(deck_text)
                with log.open("w") as output:
                    try:
                        run = subprocess.run(
                            ["ngspice", "-b", str(deck)], stdout=output,
                            stderr=subprocess.STDOUT, timeout=args.timeout_s,
                            check=False)
                        return_code = run.returncode
                    except subprocess.TimeoutExpired:
                        return_code = 124
            observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
            margins_by_delay = {round(delay / 1e-12): [] for delay in SAMPLE_DELAYS_S}
            for index in SAMPLE_INDICES:
                for delay in SAMPLE_DELAYS_S:
                    delay_ps = round(delay / 1e-12)
                    high = observed.get(
                        f"outp_{index}_{delay_ps}" if BITS[index]
                        else f"outn_{index}_{delay_ps}", 0.0)
                    low = observed.get(
                        f"outn_{index}_{delay_ps}" if BITS[index]
                        else f"outp_{index}_{delay_ps}", 3.30)
                    margins_by_delay[delay_ps].extend((high - 2.64, 0.66 - low))
            complete = (return_code == 0 and len(observed)
                        == 2 * len(SAMPLE_INDICES) * len(SAMPLE_DELAYS_S) + 1)
            early_margin = min(margins_by_delay[min(margins_by_delay)])
            qualified_margin = min(margins_by_delay[max(margins_by_delay)])
            passed = (complete and qualified_margin >= 0.0
                      and 0.00001 <= observed["supply_current"] <= 0.020)
            cases.append({"differential_input_v": differential_input, "load_ff": load_ff,
                          "early_logic_margin_v": early_margin,
                          "qualified_logic_margin_v": qualified_margin,
                          "qualified_delay_s": max(SAMPLE_DELAYS_S), "observed": observed,
                          "result": "pass" if passed else "fail"})
    passing = sum(case["result"] == "pass" for case in cases)
    result = {"schema_version": 1, "result": "pass" if passing == len(cases) else "fail",
              "case_count": len(cases), "passing_case_count": passing, "cases": cases}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"cml_to_cmos nominal: {passing}/{len(cases)} cases pass")
    if passing != len(cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
