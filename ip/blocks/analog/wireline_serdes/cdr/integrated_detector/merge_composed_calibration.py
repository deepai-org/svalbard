#!/usr/bin/env python3
"""Merge phase-only and targeted sampler-bias searches into one calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase-search", required=True, type=Path)
    parser.add_argument("--base-calibration", required=True, type=Path)
    parser.add_argument("--retry-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--list-failed", action="store_true")
    args = parser.parse_args()
    phase = json.loads(args.phase_search.read_text())
    base = json.loads(args.base_calibration.read_text())
    base_settings = {item["environment"]: item for item in base["selected_settings"]}
    failed = [group["environment"] for group in phase["groups"]
              if group["result"] != "pass"]
    if args.list_failed:
        print("\n".join(failed))
        return
    if args.retry_dir is None or args.output is None:
        parser.error("--retry-dir and --output are required when merging")
    settings = []
    retry_hashes = {}
    retry_cases = 0
    for group in phase["groups"]:
        environment = group["environment"]
        selected = group.get("selected")
        source = "edge_phase_search"
        if selected is None:
            retry_path = args.retry_dir / f"{environment}.json"
            retry = json.loads(retry_path.read_text())
            if retry.get("result") != "pass" or retry.get("passing_group_count") != 1:
                raise SystemExit(f"sampler recalibration failed: {environment}")
            selected = retry["groups"][0]["selected"]
            retry_cases += retry["case_count"]
            retry_hashes[environment] = hashlib.sha256(retry_path.read_bytes()).hexdigest()
            source = "sampler_bias_and_edge_phase_search"
        if "sampler_bias_v" not in selected:
            selected = {"sampler_bias_v": base_settings[environment]["sampler_bias_v"],
                        **selected}
        settings.append({"environment": environment, "source": source, **selected})
    passed = (phase.get("case_count") == 252 and phase.get("complete_case_count") == 252
              and len(settings) == 9 and len(failed) == len(retry_hashes))
    result = {
        "schema_version": 1, "result": "pass" if passed else "fail",
        "phase_search_case_count": phase.get("case_count"),
        "sampler_recalibration_case_count": retry_cases,
        "recalibrated_environments": failed,
        "phase_search_sha256": hashlib.sha256(args.phase_search.read_bytes()).hexdigest(),
        "sampler_recalibration_sha256": retry_hashes,
        "selected_settings": settings,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not passed:
        raise SystemExit("composed calibration merge failed")
    print(f"composed calibration: 9/9 settings; {len(failed)} sampler-bias retries")


if __name__ == "__main__":
    main()
