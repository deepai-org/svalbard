#!/usr/bin/env python3
"""Merge qualified fixed- and split-control half-rate VCO evidence by hash."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SERDES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERDES_ROOT))

from analog_evidence import (  # noqa: E402
    EvidenceError,
    covers_band,
    covers_value,
    environment_index,
    merge_intervals,
    require_same_environment_keys,
    require_unique_sha256,
    sha256_file,
)


TARGET_HZ = 1.25e9
GUARDBAND_HZ = (1.225e9, 1.275e9)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--split-inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    splits = [(path, json.loads(path.read_text())) for path in args.split_inputs]
    if len(splits) != 3:
        raise SystemExit(f"expected three split-control members, got {len(splits)}")

    baseline_simulation = baseline["simulation"]
    try:
        baseline_environment_index = environment_index(
            baseline_simulation["environments"]
        )
        split_environment_indexes = [
            environment_index(source["environments"]) for _, source in splits
        ]
        baseline_environment_keys = require_same_environment_keys(
            [baseline_environment_index, *split_environment_indexes],
            expected_count=5,
        )
    except EvidenceError as error:
        raise SystemExit(str(error)) from error

    baseline_hashes = [
        record["pex_sha256"] for record in baseline["physical"].values()
    ]
    split_hashes = [source["physical"]["pex_sha256"] for _, source in splits]
    all_hashes = baseline_hashes + split_hashes
    try:
        require_unique_sha256(all_hashes, expected_count=10)
    except EvidenceError as error:
        raise SystemExit(str(error)) from error
    baseline_physical_pass = (
        baseline["result"] == "pass"
        and baseline["required_target_result"] == "pass"
        and baseline_simulation["initial_condition"] == "none"
        and not baseline_simulation["transient_uic"]
        and all(baseline["pex_identity"].values())
        and all(record["result"] == "pass" for record in baseline["physical"].values())
    )
    split_physical_pass = all(
        source["environment_set"] == "full"
        and source["result"] == "screen_complete"
        and source["initial_condition"] == "none"
        and not source["transient_uic"]
        and source["physical"]["drc_error_count"] == 0
        and source["physical"]["lvs_unique"]
        and source["physical"]["pex_resistor_count"] >= 1000
        and source["physical"]["pex_capacitor_count"] >= 280
        for _, source in splits
    )
    physical_pass = (
        baseline_physical_pass
        and split_physical_pass
        and len(baseline_hashes) == 7
    )

    environments = []
    for key in sorted(baseline_environment_keys):
        baseline_environment = baseline_environment_index[key]
        intervals = [
            (float(lower), float(upper))
            for lower, upper in baseline_environment["continuous_bank_intervals_hz"]
        ]
        contributors = [{
            "source": args.baseline.name,
            "continuous_intervals_hz": baseline_environment[
                "continuous_bank_intervals_hz"
            ],
        }]
        for index, (path, source) in enumerate(splits):
            split_environment = split_environment_indexes[index][key]
            intervals.extend(
                (float(lower), float(upper))
                for lower, upper in split_environment["continuous_intervals_hz"]
            )
            contributors.append({
                "source": path.name,
                "pex_sha256": source["physical"]["pex_sha256"],
                "continuous_intervals_hz": split_environment[
                    "continuous_intervals_hz"
                ],
            })
        merged = merge_intervals(intervals)
        target_covered = covers_value(merged, TARGET_HZ)
        guardband_covered = covers_band(merged, *GUARDBAND_HZ)
        environments.append({
            "environment": list(key),
            "continuous_intervals_hz": merged,
            "target_covered": target_covered,
            "two_percent_guardband_covered": guardband_covered,
            "contributors": contributors,
        })

    target_count = sum(item["target_covered"] for item in environments)
    guardband_count = sum(
        item["two_percent_guardband_covered"] for item in environments
    )
    case_count = baseline_simulation["case_count"] + sum(
        source["case_count"] for _, source in splits
    )
    passing_case_count = baseline_simulation["passing_case_count"] + sum(
        source["passing_case_count"] for _, source in splits
    )
    qualified = (
        physical_pass
        and case_count == 880
        and target_count == len(environments)
        and guardband_count == len(environments)
    )
    result = {
        "schema_version": 1,
        "claim": "ten_physical_half_rate_vco_parents_full_pvt_design_guardband",
        "qualification": "design_guardband",
        "target_hz": TARGET_HZ,
        "design_band_hz": list(GUARDBAND_HZ),
        "member_count": len(all_hashes),
        "unique_pex_count": len(all_hashes),
        "case_count": case_count,
        "passing_case_count": passing_case_count,
        "environment_count": len(environments),
        "target_environment_count": target_count,
        "guardband_environment_count": guardband_count,
        "baseline_evidence": {
            "source": args.baseline.name,
            "sha256": sha256_file(args.baseline),
            "member_count": len(baseline_hashes),
            "case_count": baseline_simulation["case_count"],
        },
        "split_evidence_sha256": {
            path.name: sha256_file(path) for path, _ in splits
        },
        "combiner_source_sha256": sha256_file(Path(__file__)),
        "shared_evidence_source_sha256": sha256_file(
            SERDES_ROOT / "analog_evidence.py"
        ),
        "split_members": [
            {
                "source": path.name,
                "case_count": source["case_count"],
                "passing_case_count": source["passing_case_count"],
                **source["physical"],
            }
            for path, source in splits
        ],
        "environments": environments,
        "result": "pass" if qualified else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"full half-rate VCO bank: physical={'pass' if physical_pass else 'fail'}; "
        f"cases={passing_case_count}/{case_count}; target={target_count}/5; "
        f"guardband={guardband_count}/5"
    )
    if not qualified:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
