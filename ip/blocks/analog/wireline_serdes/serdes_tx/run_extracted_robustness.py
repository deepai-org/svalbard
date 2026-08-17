#!/usr/bin/env python3
"""Run bounded full-RC load, input, rate, and supply-noise stress cases."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def cases() -> list[dict[str, float | str]]:
    nominal = {"rate": 2.5, "cp": 50.0, "cn": 50.0, "edge": 20.0,
               "skew": 0.0, "vdd": 3.3, "ripple": 0.0, "rfreq": 100e6}
    result = [nominal | {"id": "nominal"}]
    for value in (25, 50, 75, 100, 150, 200):
        result.append(nominal | {"id": f"load_{value}f", "cp": value, "cn": value})
    for cp, cn in ((25, 75), (75, 25), (50, 100), (100, 50), (50, 150), (150, 50)):
        result.append(nominal | {"id": f"load_mismatch_{cp}_{cn}f", "cp": cp, "cn": cn})
    for value in (5, 10, 20, 40, 80, 120):
        result.append(nominal | {"id": f"edge_{value}p", "edge": value})
    for value in (-40, -20, -10, 0, 10, 20, 40):
        result.append(nominal | {"id": f"input_skew_{value:+g}p", "skew": value})
    for amplitude in (25, 50, 100, 150):
        for frequency in (100e6, 500e6, 1e9):
            result.append(nominal | {"id": f"ripple_{amplitude}m_{frequency/1e6:g}m",
                                     "ripple": amplitude / 1000, "rfreq": frequency})
    for value in (2.97, 3.30, 3.63):
        result.append(nominal | {"id": f"supply_{value:.2f}v", "vdd": value})
    for value in (1.25, 2.5, 3.125):
        result.append(nominal | {"id": f"rate_{value:g}g", "rate": value})
    result.extend([
        nominal | {"id": "combined_heavy_slow", "cp": 150.0, "cn": 200.0,
                   "edge": 80.0, "skew": 20.0, "vdd": 2.97, "ripple": 0.10, "rfreq": 500e6},
        nominal | {"id": "combined_light_fast", "cp": 25.0, "cn": 50.0,
                   "edge": 5.0, "skew": -20.0, "vdd": 3.63, "ripple": 0.10, "rfreq": 1e9},
        nominal | {"id": "combined_nominal_load_noise", "edge": 40.0,
                   "skew": 10.0, "ripple": 0.15, "rfreq": 500e6},
    ])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "extracted_robustness_tb.spice.in").read_text()
    records = []
    for case in cases():
        period_ps = 1000.0 / float(case["rate"])
        edge_ps = float(case["edge"])
        stop_ps = 100.0 + 10.0 * period_ps
        values = {
            "PEX_PATH": str(args.pex), "VDD": f"{case['vdd']}",
            "RIPPLE": f"{case['ripple']}", "RIPPLE_FREQ": f"{case['rfreq']}",
            "EDGE": f"{edge_ps}p", "PERIOD": f"{period_ps}p",
            "PULSE_WIDTH": f"{period_ps / 2 - edge_ps}p",
            "INN_DELAY": f"{100.0 + float(case['skew'])}p",
            "CLOAD_P": f"{case['cp']}f", "CLOAD_N": f"{case['cn']}f",
            "TSTEP": f"{min(2.0, edge_ps / 5)}p", "TSTOP": f"{stop_ps}p",
            "MEAS_START": f"{100.0 + 6.0 * period_ps}p",
            "SAMPLE_HIGH": f"{100.0 + 8.75 * period_ps}p",
            "SAMPLE_LOW": f"{100.0 + 8.25 * period_ps}p",
        }
        deck_text = template
        for name, value in values.items():
            deck_text = deck_text.replace(f"@{name}@", value)
        deck = args.work / f"{case['id']}.spice"
        log = args.work / f"{case['id']}.log"
        deck.write_text(deck_text)
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=45, check=False)
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        required = {"diff_high", "diff_low", "supply_current_avg", "output_floor",
                    "output_floor_n", "common_mode_avg", "diff_rise", "diff_fall"}
        complete = run.returncode == 0 and required <= observed.keys()
        checks = {"complete": complete}
        if complete:
            checks |= {
                "finite": all(math.isfinite(observed[name]) for name in required),
                "swing": observed["diff_high"] <= -0.40 and observed["diff_low"] >= 0.40,
                "symmetry": abs(abs(observed["diff_high"]) - abs(observed["diff_low"])) <= 0.025,
                "crossing": max(observed["diff_rise"], observed["diff_fall"]) <= 80e-12,
                "current": 0.001 <= observed["supply_current_avg"] <= 0.008,
                "floor": min(observed["output_floor"], observed["output_floor_n"]) >= 1.8,
            }
        records.append(case | {"observed": observed, "checks": checks,
                               "result": "pass" if all(checks.values()) else "fail"})
    passed = sum(record["result"] == "pass" for record in records)
    result = {"schema_version": 1, "result": "pass" if passed == len(records) else "fail",
              "case_count": len(records), "passed_case_count": passed, "cases": records}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"full-RC robustness: {passed}/{len(records)} pass")
    if passed != len(records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
