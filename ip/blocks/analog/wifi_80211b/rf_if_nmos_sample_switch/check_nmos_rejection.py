#!/usr/bin/env python3
"""Bind the complete NMOS sample-switch probe to its rejection decision."""
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


def validate_probe(result: dict[str, object], boundary: str, pex: Path) -> dict[str, dict[str, object]]:
    require(result.get("claim") ==
            "wifi_real_if_differential_nmos_sampling_switch_12bit_accuracy_probe"
            and result.get("simulation_boundary") == boundary
            and result.get("probe_complete") is True
            and result.get("case_count") == 5
            and result.get("complete_case_count") == 5,
            f"incomplete {boundary} NMOS probe")
    if boundary == "pex":
        require(result.get("pex_sha256") == digest(pex), "PEX probe is not byte-bound")
    cases = {case.get("case_id"): case for case in result.get("cases", [])}
    require(set(cases) == set(EXPECTED_ENVIRONMENTS),
            f"{boundary} environment set changed")
    for name, environment in EXPECTED_ENVIRONMENTS.items():
        case = cases[name]
        require(tuple(case.get("environment", ())) == environment
                and case.get("complete") is True
                and math.isfinite(case.get("worst_track_error_abs_v", math.nan))
                and math.isfinite(case.get("worst_aperture_and_hold_error_abs_v", math.nan)),
                f"{boundary} {name} is incomplete")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical", required=True, type=Path)
    parser.add_argument("--schematic", required=True, type=Path)
    parser.add_argument("--pex-result", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    physical = json.loads(args.physical.read_text())
    schematic = json.loads(args.schematic.read_text())
    pex_result = json.loads(args.pex_result.read_text())
    require(physical.get("result") == "pass" and physical.get("drc_error_count") == 0
            and physical.get("lvs_unique") is True
            and physical.get("pex_sha256") == digest(args.pex),
            "NMOS rejection lacks closed physical identity")
    schematic_cases = validate_probe(schematic, "schematic", args.pex)
    pex_cases = validate_probe(pex_result, "pex", args.pex)
    limit = pex_result["declared_boundary"]["accuracy_limit_v"]
    require(schematic["declared_boundary"] == pex_result["declared_boundary"],
            "schematic and PEX probes changed their declared boundary")
    require(schematic.get("result") == "fail" and pex_result.get("result") == "fail"
            and all(case["result"] == "fail" for case in schematic_cases.values())
            and all(case["result"] == "fail" for case in pex_cases.values()),
            "NMOS probe no longer establishes all-corner rejection")
    cases = []
    for name in EXPECTED_ENVIRONMENTS:
        cases.append({
            "case_id": name,
            "schematic_worst_track_error_abs_v": schematic_cases[name]["worst_track_error_abs_v"],
            "schematic_worst_aperture_and_hold_error_abs_v":
                schematic_cases[name]["worst_aperture_and_hold_error_abs_v"],
            "pex_worst_track_error_abs_v": pex_cases[name]["worst_track_error_abs_v"],
            "pex_worst_aperture_and_hold_error_abs_v":
                pex_cases[name]["worst_aperture_and_hold_error_abs_v"],
        })
    worst_schematic = max(item["schematic_worst_aperture_and_hold_error_abs_v"]
                           for item in cases)
    worst_pex = max(item["pex_worst_aperture_and_hold_error_abs_v"] for item in cases)
    output = {
        "schema_version": 1,
        "claim": "wifi_real_if_nmos_switch_12bit_sample_interface_rejection",
        "result": "rejected",
        "reason": (
            "The physical NMOS-only switch fails the declared 12-bit sampling "
            "allocation in every complete PVT case, and the schematic baseline "
            "fails likewise; do not spend further effort tuning this topology."),
        "next_required_topology": "matched_transmission_gate_with_complementary_overlap_controlled_clocks",
        "declared_boundary": pex_result["declared_boundary"],
        "quarter_lsb_accuracy_limit_v": limit,
        "worst_schematic_aperture_and_hold_error_abs_v": worst_schematic,
        "worst_pex_aperture_and_hold_error_abs_v": worst_pex,
        "worst_pex_error_over_quarter_lsb": worst_pex / limit,
        "physical_result_sha256": digest(args.physical),
        "schematic_probe_sha256": digest(args.schematic),
        "pex_probe_sha256": digest(args.pex_result),
        "pex_sha256": digest(args.pex),
        "cases": cases,
        "not_a_claim": [
            "working_12bit_sampler", "adc_enob", "thermal_noise", "mismatch_yield",
            "clock_jitter_tolerance", "implemented_if_buffer", "integrated_wifi_receiver",
        ],
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": output["result"],
        "worst_pex_error_over_quarter_lsb": output["worst_pex_error_over_quarter_lsb"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
