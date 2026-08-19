#!/usr/bin/env python3
"""Bind physical, bias, PVT, disturbance, and handoff evidence for the VCO parent."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical", type=Path, required=True)
    parser.add_argument("--bias-dac", type=Path, required=True)
    parser.add_argument("--nominal", type=Path, required=True)
    parser.add_argument("--pvt", type=Path, required=True)
    parser.add_argument("--supply", type=Path, required=True)
    parser.add_argument("--sequence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    physical = load(args.physical)
    bias = load(args.bias_dac)
    nominal = load(args.nominal)
    pvt = load(args.pvt)
    supply = load(args.supply)
    sequence = load(args.sequence)

    pex_hashes = {
        str(item.get("pex_sha256", ""))
        for item in (physical, nominal, pvt, supply, sequence)
    }
    selected_codes = [
        int(code)
        for item in pvt.get("calibration", [])
        for code in dict(item.get("selected_codes") or {}).values()
    ]
    minimum_code_rail_headroom = min(
        (min(code, 31 - code) for code in selected_codes), default=-1
    )
    component_results = {
        "physical": physical.get("result"),
        "bias_dac": bias.get("result"),
        "nominal": nominal.get("result"),
        "pvt": pvt.get("result"),
        "supply_reference_stress": supply.get("result"),
        "sequence": sequence.get("result"),
    }
    references = {
        float(item.get("bias_reference_v", -1.0))
        for item in (nominal, pvt, sequence)
    }
    bias_reference_range = bias.get("simulation", {}).get("reference_range_v")
    preferred_band = pvt.get("selection_preferred_band_hz", [])
    selected_frequencies = [
        float(item["selected_frequency_hz"])
        for item in pvt.get("calibration", [])
        if item.get("selected_frequency_hz") is not None
    ]
    passed = (
        all(value == "pass" for value in component_results.values())
        and len(pex_hashes) == 1
        and "" not in pex_hashes
        and references == {2.0}
        and bias_reference_range == [0.0, 2.0]
        and int(pvt.get("passing_environment_count", 0)) == 5
        and int(supply.get("case_count", 0)) == 55
        and int(supply.get("passing_case_count", 0)) == 55
        and int(supply.get("passing_environment_count", 0)) == 5
        and float(supply.get("cycle_displacement_limit_s", 0.0)) == 40e-12
        and float(supply.get("frequency_pushing_limit_fraction", 0.0)) == 0.02
        and supply.get("pvt_evidence_sha256") == digest(args.pvt)
        and preferred_band == [1.227e9, 1.273e9]
        and len(selected_frequencies) == 5
        and all(preferred_band[0] <= value <= preferred_band[1]
                for value in selected_frequencies)
        and minimum_code_rail_headroom >= 3
    )
    result = {
        "schema_version": 1,
        "claim": "physically_closed_realizable_selected_vco_bank_parent",
        "checker_source_sha256": digest(Path(__file__)),
        "component_results": component_results,
        "bias_reference_v": 2.0,
        "common_parent_pex_sha256": next(iter(pex_hashes)) if len(pex_hashes) == 1 else None,
        "passing_pvt_environment_count": pvt.get("passing_environment_count", 0),
        "passing_supply_reference_environment_count": supply.get(
            "passing_environment_count", 0
        ),
        "maximum_supply_reference_cycle_displacement_s": max(
            (float(item["maximum_cycle_displacement_s"])
             for item in supply.get("groups", [])), default=None
        ),
        "maximum_supply_reference_frequency_pushing_fraction": max(
            (float(item["maximum_frequency_pushing_fraction"])
             for item in supply.get("groups", [])), default=None
        ),
        "selected_pvt_codes": [
            {
                "environment": item.get("environment"),
                "member": item.get("selected_member"),
                "codes": item.get("selected_codes"),
            }
            for item in pvt.get("calibration", [])
        ],
        "minimum_selected_code_rail_headroom": minimum_code_rail_headroom,
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        "selected VCO bank aggregate: "
        f"components={component_results}; PVT={result['passing_pvt_environment_count']}/5; "
        f"stress={result['passing_supply_reference_environment_count']}/5; "
        f"code_headroom={minimum_code_rail_headroom}; result={result['result']}"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
