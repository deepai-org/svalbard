#!/usr/bin/env python3
"""Fail closed on incomplete or misleading requirement-to-test coverage."""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH_ROOT = HERE.parents[1]
MANIFEST = HERE / "coverage_manifest.json"
ALLOWED_ORACLE = {"self_tested", "specified"}
ALLOWED_HARNESS = {"reference_executable", "candidate_adapter_specified", "implemented"}


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    profile = json.loads((BENCH_ROOT / "benchmark_profile.json").read_text(encoding="utf-8"))
    metadata = json.loads((BENCH_ROOT / "tests/assets/metadata.json").read_text(encoding="utf-8"))
    reward = json.loads((BENCH_ROOT / "tests/assets/tiered_reward.json").read_text(encoding="utf-8"))
    codec_crosscheck = json.loads((BENCH_ROOT / "tests/assets/8b10b_crosscheck.json").read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    assert profile.get("schema_version") == 1
    assert profile.get("status") == "authored_unpiloted"
    claim = data.get("coverage_claim", "")
    assert "42 frozen requirements" in claim
    assert "Candidate results are recorded separately" in claim

    requirements = data.get("requirements")
    scenarios = data.get("scenarios")
    assert isinstance(requirements, list) and requirements
    assert isinstance(scenarios, list) and scenarios

    req_ids = [item.get("id") for item in requirements]
    test_ids = [item.get("id") for item in scenarios]
    assert all(isinstance(value, str) and value for value in req_ids + test_ids)
    assert len(req_ids) == len(set(req_ids)), "duplicate requirement ID"
    assert len(test_ids) == len(set(test_ids)), "duplicate scenario ID"

    covered: set[str] = set()
    for scenario in scenarios:
        refs = scenario.get("requirements")
        assert isinstance(refs, list) and refs, f"{scenario.get('id')} has no requirements"
        unknown = set(refs) - set(req_ids)
        assert not unknown, f"{scenario.get('id')} names unknown requirements: {sorted(unknown)}"
        assert scenario.get("oracle_status") in ALLOWED_ORACLE
        assert scenario.get("harness_status") in ALLOWED_HARNESS
        for field in ("stimulus", "observations", "oracle"):
            assert scenario.get(field), f"{scenario.get('id')} lacks {field}"
        covered.update(refs)

    missing = set(req_ids) - covered
    assert not missing, f"requirements without scenarios: {sorted(missing)}"
    assert all("pass" not in scenario for scenario in scenarios), (
        "coverage manifest must not embed candidate pass claims"
    )
    assert metadata.get("requirements") == len(req_ids)
    assert metadata.get("verification_scenarios") == len(test_ids)
    assert profile["protocol"]["line_rate_baud"] == 1_250_000_000
    assert profile["protocol"]["unit_interval_ps"] == 800
    assert profile["digital_phy_boundary"]["width_bits"] == 10
    assert len(profile["mandatory_pvt"]) == 5
    assert math.isclose(sum(reward["weights"].values()), 1.0, rel_tol=0.0, abs_tol=1e-12)
    assert reward["status"] == "uncalibrated_until_pilot"
    assert codec_crosscheck["crosscheck_status"] == "passed"
    assert codec_crosscheck["encoding_comparison"]["mismatches"] == 0
    assert codec_crosscheck["encoding_comparison"]["data_entries"] == 512
    assert codec_crosscheck["encoding_comparison"]["control_entries"] == 24
    print(f"coverage audit: PASS ({len(req_ids)} requirements, {len(test_ids)} scenarios)")


if __name__ == "__main__":
    main()
