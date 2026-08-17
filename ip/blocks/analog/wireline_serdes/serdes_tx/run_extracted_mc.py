#!/usr/bin/env python3
"""Run reproducible full-RC process, mismatch, and combined statistics."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
from pathlib import Path

MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
CAMPAIGNS = {
    "global": (1, 0),
    "mismatch": (0, 1),
    "combined": (1, 1),
}


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled SPICE tokens: {remaining}")
    return result


def run_ngspice(deck: Path, log: Path, seed_home: Path) -> int:
    environment = os.environ.copy()
    environment["HOME"] = str(seed_home)
    with log.open("w") as output:
        run = subprocess.run(
            ["ngspice", "-b", str(deck)], stdout=output, stderr=subprocess.STDOUT,
            timeout=45, check=False, env=environment,
        )
    return run.returncode


def controls(enabled: int) -> dict[str, str]:
    return {f"B{index}_V": "0" if index < enabled else "3.3" for index in range(4)}


def calibration_rows(path: Path, enabled: int) -> list[dict[str, float | int]]:
    rows = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) != 5 or not fields[0][0].isdigit():
            continue
        _, bias, outp, outn, current = map(float, fields)
        rows.append({"enabled_branches": enabled, "vbias_v": bias, "outp_v": outp,
                     "outn_v": outn, "current_a": current,
                     "static_diff_v": outn - outp})
    return rows


def select_calibration(rows: list[dict[str, float | int]]) -> dict[str, float | int] | None:
    safe = [row for row in rows if 0.55 <= float(row["vbias_v"]) <= 1.75
            and 0.001 <= float(row["current_a"]) <= 0.008
            and min(float(row["outp_v"]), float(row["outn_v"])) >= 1.8
            and max(float(row["outp_v"]), float(row["outn_v"])) <= 3.32]
    if not safe:
        return None
    window = [row for row in safe if 0.60 <= float(row["static_diff_v"]) <= 0.64]
    if window:
        return max(window, key=lambda row: float(row["current_a"]))
    return min(safe, key=lambda row: abs(float(row["static_diff_v"]) - 0.62))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=50)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    cal_template = (args.source / "extracted_mc_calibration_tb.spice.in").read_text()
    tran_template = (args.source / "extracted_mc_transient_tb.spice.in").read_text()
    records: list[dict[str, object]] = []

    for campaign_index, (campaign, switches) in enumerate(CAMPAIGNS.items()):
        for sample in range(args.samples):
            seed = 17001 + campaign_index * 10000 + sample
            case_id = f"{campaign}_{sample:03d}"
            case_dir = args.work / case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / ".spiceinit").write_text(f"setseed {seed}\n")
            common = {"PEX_PATH": str(args.pex), "STAT_GLOBAL": str(switches[0]),
                      "STAT_MISMATCH": str(switches[1])}
            candidates: list[dict[str, float | int]] = []
            return_codes = []
            for enabled in range(5):
                data = case_dir / f"code{enabled}.dat"
                deck = case_dir / f"code{enabled}.cal.spice"
                deck.write_text(instantiate(cal_template, common | controls(enabled)
                                            | {"CAL_DATA": str(data)}))
                return_codes.append(run_ngspice(deck, case_dir / f"code{enabled}.cal.log", case_dir))
                if data.exists():
                    candidates.extend(calibration_rows(data, enabled))
            selected = select_calibration(candidates)
            record: dict[str, object] = {"id": case_id, "campaign": campaign,
                                         "sample": sample, "seed": seed,
                                         "calibration": selected}
            if selected is None or any(return_codes):
                record["checks"] = {"calibration": False}
                record["result"] = "fail"
                records.append(record)
                continue
            enabled = int(selected["enabled_branches"])
            deck = case_dir / "selected.tran.spice"
            deck.write_text(instantiate(tran_template, common | controls(enabled)
                                        | {"VBIAS_V": f"{float(selected['vbias_v']):.3f}"}))
            log = case_dir / "selected.tran.log"
            return_code = run_ngspice(deck, log, case_dir)
            observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
            required = {"diff_high", "diff_low", "supply_current_avg", "output_floor",
                        "output_floor_n", "common_mode_avg", "diff_rise", "diff_fall"}
            complete = return_code == 0 and required <= observed.keys()
            checks = {"calibration": True, "complete": complete}
            if complete:
                checks |= {
                    "finite": all(math.isfinite(observed[name]) for name in required),
                    "swing": observed["diff_high"] <= -0.40 and observed["diff_low"] >= 0.40,
                    "swing_max": observed["diff_high"] >= -0.65 and observed["diff_low"] <= 0.65,
                    "symmetry": abs(abs(observed["diff_high"]) - abs(observed["diff_low"])) <= 0.025,
                    "crossing": max(observed["diff_rise"], observed["diff_fall"]) <= 80e-12,
                    "current": 0.001 <= observed["supply_current_avg"] <= 0.008,
                    "floor": min(observed["output_floor"], observed["output_floor_n"]) >= 1.8,
                }
            record |= {"observed": observed, "checks": checks,
                       "result": "pass" if all(checks.values()) else "fail"}
            records.append(record)

    by_campaign = {}
    for campaign in CAMPAIGNS:
        subset = [record for record in records if record["campaign"] == campaign]
        by_campaign[campaign] = {"samples": len(subset),
                                 "passed": sum(record["result"] == "pass" for record in subset)}
    passed = sum(record["result"] == "pass" for record in records)
    result = {"schema_version": 1, "result": "pass" if passed == len(records) else "fail",
              "sample_count": len(records), "passed_sample_count": passed,
              "campaigns": by_campaign, "cases": records}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"full-RC statistical: {passed}/{len(records)} pass {by_campaign}")
    if passed != len(records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
