#!/usr/bin/env python3
"""Mutation qualification for the fail-closed evidence contract."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from result_contract import BENCHMARK_PROFILE_PATH, PDK_LOCK_PATH, required_scenarios, validate_result


def valid_fixture() -> dict[str, object]:
    return {
        "schema_version": 1,
        "benchmark": "circuitbench-mixed-signal/0001-complete-gigabit-ethernet-port",
        "pdk_lock_sha256": hashlib.sha256(PDK_LOCK_PATH.read_bytes()).hexdigest(),
        "benchmark_profile_sha256": hashlib.sha256(BENCHMARK_PROFILE_PATH.read_bytes()).hexdigest(),
        "candidate_sha256": "a" * 64,
        "complete_port_passed": True,
        "scenario_results": [
            {
                "id": scenario,
                "view": "routed_system",
                "cases": [{"id": "qualification-fixture", "passed": True, "metrics": {"margin": 1.0}}],
            }
            for scenario in sorted(required_scenarios())
        ],
    }


def main() -> None:
    baseline = valid_fixture()
    assert validate_result(baseline) == []

    missing = copy.deepcopy(baseline)
    missing["scenario_results"].pop()
    assert any("missing scenarios" in error for error in validate_result(missing))

    stale_pdk = copy.deepcopy(baseline)
    stale_pdk["pdk_lock_sha256"] = "0" * 64
    assert "PDK lock identity mismatch" in validate_result(stale_pdk)

    stale_profile = copy.deepcopy(baseline)
    stale_profile["benchmark_profile_sha256"] = "0" * 64
    assert "benchmark profile identity mismatch" in validate_result(stale_profile)

    nan_metric = copy.deepcopy(baseline)
    nan_metric["scenario_results"][0]["cases"][0]["metrics"]["eye"] = float("nan")
    assert any("non-finite" in error for error in validate_result(nan_metric))

    hidden_failure = copy.deepcopy(baseline)
    hidden_failure["scenario_results"][0]["cases"][0]["passed"] = False
    assert any("contradicts" in error for error in validate_result(hidden_failure))

    wrong_view = copy.deepcopy(baseline)
    wrong_view["scenario_results"][0]["view"] = "claimed_pex_but_really_schematic"
    assert any("invalid or missing view" in error for error in validate_result(wrong_view))

    print("result-contract mutation self-test: PASS")


if __name__ == "__main__":
    main()
