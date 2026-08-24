#!/usr/bin/env python3
"""Validate the routed fast RX/PI parent checkpoint and its open corner."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--aggregate", required=True, type=Path)
parser.add_argument("--physical", required=True, type=Path)
parser.add_argument("--pex", required=True, type=Path)
parser.add_argument("--runner", required=True, type=Path)
parser.add_argument("--merger", required=True, type=Path)
parser.add_argument("--testbench", required=True, type=Path)
for name in ("render", "top-schematic", "capture-schematic",
             "frontend-schematic", "converter-schematic", "top-layout",
             "capture-layout", "frontend-layout", "frontend-base-layout",
             "converter-layout"):
    parser.add_argument(f"--{name}", required=True, type=Path)
parser.add_argument("--case", action="append", required=True, type=Path)
args = parser.parse_args()

aggregate = json.loads(args.aggregate.read_text())
physical = json.loads(args.physical.read_text())
case_files = {json.loads(path.read_text())["case_id"]: path for path in args.case}
cases = {name: json.loads(path.read_text()) for name, path in case_files.items()}
expected = {
    "tt": "pass", "ff_cold": "pass", "ff_hot": "pass",
    "ss_hot": "fail", "ss_passive": "pass",
}

checks = [
    set(cases) == set(expected),
    aggregate.get("case_count") == 5,
    aggregate.get("passing_case_count") == 4,
    aggregate.get("result") == "fail",
    aggregate.get("aggregate_source_sha256") == digest(args.merger),
    aggregate.get("claim") ==
        "routed_pi_rx_fast_capture_parent_extracted_2p5_gts_combined_stress_pvt",
    physical.get("result") == "pass",
    physical.get("drc_error_count") == 0,
    physical.get("lvs_unique") is True,
    physical.get("pex_sha256") == digest(args.pex),
    physical.get("layout_image_sha256") == digest(args.render),
    physical.get("pex_resistor_count") == 8717,
    physical.get("pex_capacitor_count") == 4874,
]
for name in ("top-schematic", "capture-schematic", "frontend-schematic",
             "converter-schematic", "top-layout", "capture-layout",
             "frontend-layout", "frontend-base-layout", "converter-layout"):
    checks.append(physical["source_sha256"][name]
                  == digest(getattr(args, name.replace("-", "_"))))

aggregate_cases = {case["case_id"]: case for case in aggregate["cases"]}
checks.append(set(aggregate_cases) == set(expected))
for name, expected_result in expected.items():
    case = cases[name]
    summary = aggregate_cases[name]
    checks.extend((
        case.get("result") == expected_result,
        case.get("complete_case_count") == 1,
        summary.get("result") == expected_result,
        summary.get("evidence_sha256") == digest(case_files[name]),
        case["pex_sha256"]["rx_pi_capture_parent_pex"] == digest(args.pex),
        case["physical_sha256"]["rx_pi_capture_parent"] == digest(args.physical),
        case["source_sha256"]["runner"] == digest(args.runner),
        case["source_sha256"]["base_testbench"] == digest(args.testbench),
        case["stimulus"]["serial_rate_hz"] == 2.5e9,
        case["stimulus"]["bit_count"] == 24,
        case["stimulus"]["pattern"] == "prbs7",
        case["stimulus"]["tx_clock_jitter_peak_s"] == 30e-12,
        case["stimulus"]["tx_clock_duty"] == 0.47,
        case["channel_stress"]["series_resistance_ohm_per_leg"] == 6.0,
        case["channel_stress"]["differential_shunt_capacitance_f"] == 1e-12,
        case["supply_stress"]["vdd_ripple_peak_v"] == 0.020,
        case["acceptance_limits"]["sampler_supply_overshoot_max_v"] == 0.050,
    ))
    if expected_result == "pass":
        selected = case.get("selected_case") or {}
        checks.extend((
            case.get("passing_case_count") == 1,
            selected.get("result") == "pass",
            selected.get("minimum_capture_even_v", -1) > 0.10,
            selected.get("minimum_capture_odd_v", -1) > 0.10,
            selected.get("sampler_supply_overshoot_max_v", 1) <= 0.050,
        ))

failed = cases["ss_hot"]
failed_run = failed["cases"][0]
alignment = [row for row in failed_run["alignment_scan"]
             if not row["swap_lanes"]]
checks.extend((
    failed.get("passing_case_count") == 0,
    failed.get("selected_case") is None,
    failed_run.get("complete") is True,
    max(row["minimum_capture_v"] for row in alignment) < 0,
    any(row["minimum_capture_even_v"] > 0 for row in alignment),
    any(row["minimum_capture_odd_v"] > 0 for row in alignment),
))

if not all(checks):
    raise SystemExit("routed fast RX/PI checkpoint failed")
minimum_capture = min(
    min(case["selected_case"]["minimum_capture_even_v"],
        case["selected_case"]["minimum_capture_odd_v"])
    for name, case in cases.items() if expected[name] == "pass")
print("routed fast RX/PI checkpoint: PASS; 4/5 environments close, "
      f"minimum passing capture margin {minimum_capture:.6g} V; "
      "SS/hot preserves mixed-lane failure")
