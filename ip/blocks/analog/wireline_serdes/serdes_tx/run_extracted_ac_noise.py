#!/usr/bin/env python3
"""Run and summarize nominal full-RC differential AC and noise analyses."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled SPICE tokens: {remaining}")
    return result


def numeric_rows(path: Path) -> list[list[float]]:
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append([float(field) for field in line.split()])
        except ValueError:
            continue
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    ac_data = args.work / "ac.dat"
    noise_data = args.work / "noise.dat"
    supply_ac_data = args.work / "supply_ac.dat"
    template = (args.source / "extracted_ac_noise_tb.spice.in").read_text()
    deck = args.work / "ac_noise.spice"
    deck.write_text(instantiate(template, {"PEX_PATH": str(args.pex),
                                           "AC_DATA": str(ac_data),
                                           "SUPPLY_AC_DATA": str(supply_ac_data),
                                           "NOISE_DATA": str(noise_data)}))
    log = args.work / "ac_noise.log"
    with log.open("w") as output:
        run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                             stderr=subprocess.STDOUT, timeout=60, check=False)
    ac_rows = numeric_rows(ac_data) if ac_data.exists() else []
    # wrdata complex output is frequency, real(vdiff), imag(vdiff).
    ac = [(row[0], abs(complex(row[1], row[2]))) for row in ac_rows if len(row) >= 3]
    dc_gain = ac[0][1] if ac else math.nan
    target = dc_gain / math.sqrt(2) if ac else math.nan
    bandwidth = next((frequency for frequency, gain in ac if gain <= target), math.nan)
    noise_rows = numeric_rows(noise_data) if noise_data.exists() else []
    noise = [(row[0], abs(row[1])) for row in noise_rows if len(row) >= 2]
    integrated_noise_sq = 0.0
    for (f0, n0), (f1, n1) in zip(noise, noise[1:]):
        integrated_noise_sq += 0.5 * (n0 * n0 + n1 * n1) * (f1 - f0)
    supply_rows = numeric_rows(supply_ac_data) if supply_ac_data.exists() else []
    # frequency, real(diff), imag(diff), real(common mode), imag(common mode)
    supply = [(row[0], abs(complex(row[1], row[2])), abs(complex(row[3], row[4])))
              for row in supply_rows if len(row) >= 5]
    result = {
        "schema_version": 1,
        "result": "pass" if run.returncode == 0 and ac and noise and supply else "fail",
        "dc_differential_gain_v_per_v": dc_gain,
        "bandwidth_3db_hz": bandwidth,
        "gain_at_1p25ghz": min(ac, key=lambda row: abs(row[0] - 1.25e9))[1] if ac else math.nan,
        "gain_at_2p5ghz": min(ac, key=lambda row: abs(row[0] - 2.5e9))[1] if ac else math.nan,
        "integrated_output_noise_1mhz_20ghz_v_rms": math.sqrt(integrated_noise_sq),
        "differential_supply_gain_peak_v_per_v": max((row[1] for row in supply), default=math.nan),
        "common_mode_supply_gain_peak_v_per_v": max((row[2] for row in supply), default=math.nan),
        "ac_points": len(ac),
        "noise_points": len(noise),
        "supply_ac_points": len(supply),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
