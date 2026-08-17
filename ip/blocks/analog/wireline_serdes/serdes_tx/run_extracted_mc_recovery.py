#!/usr/bin/env python3
"""Apply transient-aware bias recovery to seeded full-RC statistical outliers."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
SWITCHES = {"global": (1, 0), "mismatch": (0, 1), "combined": (1, 1)}


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled SPICE tokens: {remaining}")
    return result


def controls(enabled: int) -> dict[str, str]:
    return {f"B{index}_V": "0" if index < enabled else "3.3" for index in range(4)}


def checks(observed: dict[str, float]) -> dict[str, bool]:
    required = {"diff_high", "diff_low", "supply_current_avg", "output_floor",
                "output_floor_n", "common_mode_avg", "diff_rise", "diff_fall"}
    complete = required <= observed.keys()
    result = {"complete": complete}
    if complete:
        result |= {
            "finite": all(math.isfinite(observed[name]) for name in required),
            "swing_min": observed["diff_high"] <= -0.40 and observed["diff_low"] >= 0.40,
            "swing_max": observed["diff_high"] >= -0.65 and observed["diff_low"] <= 0.65,
            "symmetry": abs(abs(observed["diff_high"]) - abs(observed["diff_low"])) <= 0.025,
            "crossing": max(observed["diff_rise"], observed["diff_fall"]) <= 80e-12,
            "current": 0.001 <= observed["supply_current_avg"] <= 0.008,
            "floor": min(observed["output_floor"], observed["output_floor_n"]) >= 1.8,
            "common_mode": 1.8 <= observed["common_mode_avg"] <= 3.2,
        }
    return result


def candidate_biases(start: float, observed: dict[str, float]) -> list[float]:
    magnitude = min(abs(observed.get("diff_high", 0)), abs(observed.get("diff_low", 0)))
    direction = 1 if magnitude < 0.4 else -1
    values = []
    for step in range(1, 22):
        value = round(start + direction * 0.02 * step, 2)
        if 0.80 <= value <= 1.60:
            values.append(value)
    for step in range(1, 22):
        value = round(start - direction * 0.02 * step, 2)
        if 0.80 <= value <= 1.60 and value not in values:
            values.append(value)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--primary", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    primary = json.loads(args.primary.read_text())
    template = (args.source / "extracted_mc_transient_tb.spice.in").read_text()
    recoveries = []

    for case in primary["cases"]:
        original_checks = checks(case.get("observed", {}))
        if all(original_checks.values()):
            continue
        campaign = str(case["campaign"])
        switches = SWITCHES[campaign]
        case_dir = args.work / str(case["id"])
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / ".spiceinit").write_text(f"setseed {case['seed']}\n")
        original = case["calibration"]
        start_bias = float(original["vbias_v"])
        start_code = int(original["enabled_branches"])
        common = {"PEX_PATH": str(args.pex), "STAT_GLOBAL": str(switches[0]),
                  "STAT_MISMATCH": str(switches[1])}
        attempts = []
        selected = None
        for enabled in [start_code] + [code for code in range(4, -1, -1) if code != start_code]:
            for bias in candidate_biases(start_bias, case.get("observed", {}))[:20]:
                attempt_id = len(attempts)
                deck = case_dir / f"attempt_{attempt_id:02d}.spice"
                deck.write_text(instantiate(template, common | controls(enabled)
                                            | {"VBIAS_V": f"{bias:.2f}"}))
                log = case_dir / f"attempt_{attempt_id:02d}.log"
                environment = os.environ.copy()
                environment["HOME"] = str(case_dir)
                with log.open("w") as output:
                    run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                         stderr=subprocess.STDOUT, timeout=45,
                                         check=False, env=environment)
                observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
                result_checks = checks(observed)
                attempt = {"enabled_branches": enabled, "vbias_v": bias,
                           "observed": observed, "checks": result_checks,
                           "result": "pass" if run.returncode == 0 and all(result_checks.values()) else "fail"}
                attempts.append(attempt)
                if attempt["result"] == "pass":
                    selected = attempt
                    break
            if selected:
                break
        recoveries.append({"id": case["id"], "seed": case["seed"],
                           "campaign": campaign, "original_checks": original_checks,
                           "original_observed": case.get("observed", {}),
                           "attempt_count": len(attempts), "selected": selected,
                           "result": "pass" if selected else "fail"})

    recovered = sum(item["result"] == "pass" for item in recoveries)
    original_full_passes = len(primary["cases"]) - len(recoveries)
    result = {"schema_version": 1,
              "result": "pass" if recovered == len(recoveries) else "fail",
              "primary_sample_count": len(primary["cases"]),
              "primary_full_check_passed": original_full_passes,
              "outlier_count": len(recoveries), "recovered_count": recovered,
              "final_passed_sample_count": original_full_passes + recovered,
              "recoveries": recoveries}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"transient-aware recovery: {recovered}/{len(recoveries)} outliers; "
          f"final {original_full_passes + recovered}/{len(primary['cases'])}")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
