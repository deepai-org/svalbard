#!/usr/bin/env python3
"""Combine physical split-control VCO candidate intervals across coarse members."""
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
    minimum_covering_members,
    require_same_environment_keys,
    require_unique_sha256,
    sha256_file,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scope", choices=("focused", "full"), default="focused")
    parser.add_argument("--minimize-members", action="store_true")
    args = parser.parse_args()
    if args.minimize_members and args.scope != "full":
        parser.error("--minimize-members requires --scope full")
    expected_environments = 2 if args.scope == "focused" else 5
    sources = [(path, json.loads(path.read_text())) for path in args.inputs]
    if len(sources) != 3:
        raise SystemExit(f"expected exactly three physical candidates, got {len(sources)}")
    try:
        environment_indexes = [
            environment_index(source["environments"]) for _, source in sources
        ]
        environment_keys = require_same_environment_keys(
            environment_indexes, expected_count=expected_environments
        )
    except EvidenceError as error:
        raise SystemExit(str(error)) from error
    selected_indexes = list(range(len(sources)))
    if args.minimize_members:
        member_intervals = {
            path.name: {
                key: environment_indexes[index][key]["continuous_intervals_hz"]
                for key in environment_keys
            }
            for index, (path, _) in enumerate(sources)
        }
        try:
            selected_names = minimum_covering_members(
                member_intervals, lower=1.225e9, upper=1.275e9
            )
        except EvidenceError as error:
            raise SystemExit(str(error)) from error
        selected_indexes = [
            index
            for index, (path, _) in enumerate(sources)
            if path.name in selected_names
        ]
    selected_sources = [sources[index] for index in selected_indexes]
    environments = []
    for key in sorted(environment_keys):
        intervals: list[tuple[float, float]] = []
        contributors = []
        for index in selected_indexes:
            path, source = sources[index]
            environment = environment_indexes[index][key]
            for lower, upper in environment["continuous_intervals_hz"]:
                intervals.append((float(lower), float(upper)))
            contributors.append({
                "source": path.name,
                "pex_sha256": source["physical"]["pex_sha256"],
                "continuous_intervals_hz": environment["continuous_intervals_hz"],
            })
        merged = merge_intervals(intervals)
        environments.append({
            "environment": list(key),
            "continuous_intervals_hz": merged,
            "target_covered": covers_value(merged, 1.25e9),
            "two_percent_guardband_covered": covers_band(
                merged, 1.225e9, 1.275e9
            ),
            "contributors": contributors,
        })
    pex_hashes = [source["physical"]["pex_sha256"] for _, source in sources]
    try:
        require_unique_sha256(pex_hashes, expected_count=3)
    except EvidenceError as error:
        raise SystemExit(str(error)) from error
    physical_pass = (
        all(
            source["physical"]["drc_error_count"] == 0
            and source["physical"]["lvs_unique"]
            and source["physical"]["pex_resistor_count"] >= 1000
            and source["physical"]["pex_capacitor_count"] >= 280
            and source["initial_condition"] == "none"
            and not source["transient_uic"]
            and source["result"] == "screen_complete"
            for _, source in sources
        )
    )
    target_count = sum(item["target_covered"] for item in environments)
    guardband_count = sum(item["two_percent_guardband_covered"] for item in environments)
    qualification_pass = (
        physical_pass
        and target_count == len(environments)
        and guardband_count == len(environments)
    )
    result = {
        "schema_version": 1,
        "claim": (
            "three_complete_physical_split_control_vco_margin_candidates"
            if args.scope == "focused"
            else (
                "minimum_physical_split_control_vco_bank_full_pvt_design_guardband"
                if args.minimize_members
                else "three_physical_split_control_vco_parents_full_pvt_design_guardband"
            )
        ),
        "scope": args.scope,
        "qualification": (
            "candidate_guardband" if args.scope == "focused" else "design_guardband"
        ),
        "candidate_member_count": len(sources),
        "member_count": len(selected_sources),
        "selected_sources": [path.name for path, _ in selected_sources],
        "candidate_case_count": sum(source["case_count"] for _, source in sources),
        "case_count": sum(source["case_count"] for _, source in selected_sources),
        "passing_case_count": sum(
            source["passing_case_count"] for _, source in selected_sources
        ),
        "target_environment_count": target_count,
        "guardband_environment_count": guardband_count,
        "candidate_unique_pex_count": len(pex_hashes),
        "unique_pex_count": len(selected_sources),
        "input_sha256": {path.name: sha256_file(path) for path, _ in sources},
        "combiner_source_sha256": sha256_file(Path(__file__)),
        "shared_evidence_source_sha256": sha256_file(
            SERDES_ROOT / "analog_evidence.py"
        ),
        "candidates": [
            {
                "source": path.name,
                "selected": index in selected_indexes,
                "claim": source["claim"],
                "case_count": source["case_count"],
                "passing_case_count": source["passing_case_count"],
                "drc_error_count": source["physical"]["drc_error_count"],
                "lvs_unique": source["physical"]["lvs_unique"],
                "pex_resistor_count": source["physical"]["pex_resistor_count"],
                "pex_capacitor_count": source["physical"]["pex_capacitor_count"],
                "pex_sha256": source["physical"]["pex_sha256"],
                "layout_image_sha256": source["physical"]["layout_image_sha256"],
            }
            for index, (path, source) in enumerate(sources)
        ],
        "environments": environments,
        "result": "pass" if qualification_pass else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"split-control bank: physical={'pass' if physical_pass else 'fail'}; "
        f"members={len(selected_sources)}/{len(sources)}; "
        f"cases={result['passing_case_count']}/{result['case_count']}; "
        f"target={target_count}/{expected_environments}; "
        f"guardband={guardband_count}/{len(environments)}"
    )
    if not qualification_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
