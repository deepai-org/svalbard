#!/usr/bin/env python3
"""Combine physical split-control VCO candidate intervals across coarse members."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge(intervals: list[tuple[float, float]]) -> list[list[float]]:
    output: list[list[float]] = []
    for lower, upper in sorted(intervals):
        if not output or lower > output[-1][1]:
            output.append([lower, upper])
        else:
            output[-1][1] = max(output[-1][1], upper)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = [(path, json.loads(path.read_text())) for path in args.inputs]
    if len(sources) != 3:
        raise SystemExit(f"expected exactly three physical candidates, got {len(sources)}")
    environment_sets = [
        {
            tuple(environment["environment"])
            for environment in source["environments"]
        }
        for _, source in sources
    ]
    if not environment_sets or any(keys != environment_sets[0] for keys in environment_sets):
        raise SystemExit("candidate reports do not cover identical environment sets")
    environment_keys = {
        tuple(environment["environment"])
        for _, source in sources for environment in source["environments"]
    }
    environments = []
    for key in sorted(environment_keys):
        intervals: list[tuple[float, float]] = []
        contributors = []
        for path, source in sources:
            environment = next(
                item for item in source["environments"]
                if tuple(item["environment"]) == key
            )
            for lower, upper in environment["continuous_intervals_hz"]:
                intervals.append((float(lower), float(upper)))
            contributors.append({
                "source": path.name,
                "pex_sha256": source["physical"]["pex_sha256"],
                "continuous_intervals_hz": environment["continuous_intervals_hz"],
            })
        merged = merge(intervals)
        environments.append({
            "environment": list(key),
            "continuous_intervals_hz": merged,
            "target_covered": any(lower <= 1.25e9 <= upper for lower, upper in merged),
            "two_percent_guardband_covered": any(
                lower <= 1.225e9 and upper >= 1.275e9 for lower, upper in merged
            ),
            "contributors": contributors,
        })
    pex_hashes = [source["physical"]["pex_sha256"] for _, source in sources]
    physical_pass = (
        len(set(pex_hashes)) == len(pex_hashes)
        and all(
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
        "claim": "three_complete_physical_split_control_vco_margin_candidates",
        "limitation": "two-environment candidate screen; full five-environment qualification remains",
        "member_count": len(sources),
        "case_count": sum(source["case_count"] for _, source in sources),
        "passing_case_count": sum(source["passing_case_count"] for _, source in sources),
        "target_environment_count": target_count,
        "guardband_environment_count": guardband_count,
        "unique_pex_count": len(set(pex_hashes)),
        "input_sha256": {path.name: digest(path) for path, _ in sources},
        "members": [
            {
                "source": path.name,
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
            for path, source in sources
        ],
        "environments": environments,
        "result": "pass" if qualification_pass else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"split-control candidate bank: physical={'pass' if physical_pass else 'fail'}; "
        f"cases={result['passing_case_count']}/{result['case_count']}; "
        f"target={target_count}/{len(environments)}; "
        f"guardband={guardband_count}/{len(environments)}"
    )
    if not qualification_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
