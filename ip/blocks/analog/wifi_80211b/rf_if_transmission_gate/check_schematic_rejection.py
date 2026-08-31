#!/usr/bin/env python3
"""Bind the two decisive simple-transmission-gate screens to one decision."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


EXPECTED_ENVIRONMENTS = {
    "tt": ("typical", 3.30, 27),
    "ff_cold": ("ff", 3.63, -40),
    "ff_hot": ("ff", 2.97, 125),
    "ss_hot": ("ss", 2.97, 125),
    "ss_cold": ("ss", 3.63, -40),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def validate(result: dict[str, object], *, width: float, sample_rate: float,
             if_hz: float, hold_cap: float, label: str) -> dict[str, object]:
    require(result.get("claim") == "wifi_real_if_transmission_gate_12bit_accuracy_probe"
            and result.get("simulation_boundary") == "schematic"
            and result.get("probe_complete") is True
            and result.get("complete_case_count") == 5
            and result.get("device_width_scale") == width,
            f"{label} screen identity changed")
    boundary = result.get("declared_boundary", {})
    require(boundary.get("sample_rate_hz") == sample_rate
            and boundary.get("if_hz") == if_hz
            and boundary.get("hold_capacitance_per_leg_f") == hold_cap,
            f"{label} operating point changed")
    cases = {case.get("case_id"): case for case in result.get("cases", [])}
    require(set(cases) == set(EXPECTED_ENVIRONMENTS), f"{label} environment set changed")
    for name, environment in EXPECTED_ENVIRONMENTS.items():
        case = cases[name]
        require(tuple(case.get("environment", ())) == environment
                and case.get("complete") is True and case.get("result") == "fail"
                and math.isfinite(case.get("worst_track_error_abs_v", math.nan))
                and math.isfinite(case.get("worst_aperture_and_hold_error_abs_v", math.nan)),
                f"{label} {name} is not a complete failed case")
    return {"boundary": boundary, "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--high-if", required=True, type=Path)
    parser.add_argument("--low-if", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    high = json.loads(args.high_if.read_text())
    low = json.loads(args.low_if.read_text())
    high_data = validate(high, width=4.0, sample_rate=320e6, if_hz=100e6,
                         hold_cap=5e-12, label="high-IF")
    low_data = validate(low, width=1.0, sample_rate=80e6, if_hz=10e6,
                        hold_cap=5e-12, label="low-IF")

    def summary(data: dict[str, object]) -> dict[str, float]:
        cases = data["cases"].values()
        return {
            "worst_track_error_abs_v": max(case["worst_track_error_abs_v"] for case in cases),
            "worst_aperture_and_hold_error_abs_v": max(
                case["worst_aperture_and_hold_error_abs_v"] for case in data["cases"].values()),
        }

    high_summary, low_summary = summary(high_data), summary(low_data)
    limit = high_data["boundary"]["accuracy_limit_v"]
    output = {
        "schema_version": 1,
        "claim": "wifi_real_if_simple_transmission_gate_schematic_rejection",
        "result": "rejected_before_layout",
        "reason": (
            "At the declared 5-pF load, no screened simple transmission-gate sizing "
            "is within the 12-bit aperture/hold allocation.  Lower IF resolves much of "
            "the tracking error but leaves charge-injection-dominated hold error; do not "
            "create a physical layout for this topology."),
        "next_required_topology": (
            "differential_sampler_with_explicit_charge_injection_cancellation_or_"
            "bottom_plate_sampling_and_declared_control_timing"),
        "quarter_lsb_accuracy_limit_v": limit,
        "high_if_320ms_100mhz_width_scale_4": high_summary,
        "low_if_80ms_10mhz_width_scale_1": low_summary,
        "high_if_probe_sha256": digest(args.high_if),
        "low_if_probe_sha256": digest(args.low_if),
        "schematic_source_sha256": digest(args.source / "rf_if_transmission_gate.spice"),
        "testbench_sha256": digest(args.source / "transmission_gate_tb.spice.in"),
        "runner_sha256": digest(args.source / "run_transmission_gate_probe.py"),
        "checker_sha256": digest(Path(__file__)),
        "not_a_claim": [
            "physical_transmission_gate", "working_12bit_sampler", "adc_enob",
            "thermal_noise", "mismatch_yield", "clock_jitter_tolerance",
            "implemented_if_buffer", "integrated_wifi_receiver",
        ],
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": output["result"],
        "high_if_worst_hold_error_v": high_summary["worst_aperture_and_hold_error_abs_v"],
        "low_if_worst_hold_error_v": low_summary["worst_aperture_and_hold_error_abs_v"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
