#!/usr/bin/env python3
"""Find viable full-RC nominal load-code and tail-bias combinations."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "extracted_operating_tb.spice.in").read_text()
    cases = []
    for enabled in range(1, 5):
        for bias_step in range(18, 31):
            bias = bias_step * 0.05
            values = {"VBIAS": f"{bias:.2f}"}
            values.update({f"B{index}": "0" if index < enabled else "3.3" for index in range(4)})
            deck_text = template
            for name, value in values.items():
                deck_text = deck_text.replace(f"@{name}@", value)
            stem = f"code{enabled}_bias{bias:.2f}"
            deck = args.work / f"{stem}.spice"
            log = args.work / f"{stem}.log"
            deck.write_text(deck_text)
            with log.open("w") as output:
                run = subprocess.run(
                    ["ngspice", "-b", str(deck)], stdout=output,
                    stderr=subprocess.STDOUT, timeout=30, check=False,
                )
            observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
            complete = run.returncode == 0 and len(observed) == 7
            passed = complete and (
                observed["diff_high"] <= -0.40
                and observed["diff_low"] >= 0.40
                and observed["diff_high"] >= -0.65
                and observed["diff_low"] <= 0.65
                and abs(abs(observed["diff_high"]) - abs(observed["diff_low"])) <= 0.010
                and observed["supply_current_avg"] <= 0.008
                and min(observed["output_floor"], observed["output_floor_n"]) >= 1.8
                and max(observed["diff_rise"], observed["diff_fall"]) <= 80e-12
            )
            cases.append({
                "enabled_branches": enabled,
                "vbias_v": bias,
                "result": "pass" if passed else "fail",
                "observed": observed,
            })
    passing = [case for case in cases if case["result"] == "pass"]
    result = {
        "schema_version": 1,
        "result": "pass" if passing else "fail",
        "case_count": len(cases),
        "passing_case_count": len(passing),
        "passing_cases": passing,
        "cases": cases,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"full-RC nominal operating sweep: {len(passing)}/{len(cases)} pass")
    if not passing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
