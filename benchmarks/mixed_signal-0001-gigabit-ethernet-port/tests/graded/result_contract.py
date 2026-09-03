"""Fail-closed contract for evidence emitted by candidate-facing testbenches."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

BENCH_ROOT = Path(__file__).resolve().parents[2]
COVERAGE_PATH = BENCH_ROOT / "tests/coverage/coverage_manifest.json"
PDK_LOCK_PATH = BENCH_ROOT / "pdk.lock.json"
BENCHMARK_PROFILE_PATH = BENCH_ROOT / "benchmark_profile.json"
VALID_VIEWS = {"rtl", "mapped", "schematic", "pex", "layout", "routed_system"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required_scenarios() -> set[str]:
    manifest = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    return {scenario["id"] for scenario in manifest["scenarios"]}


def validate_result(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("unsupported evidence schema")
    if data.get("benchmark") != "circuitbench-mixed-signal/0001-complete-gigabit-ethernet-port":
        errors.append("benchmark identity mismatch")
    if data.get("pdk_lock_sha256") != _sha256(PDK_LOCK_PATH):
        errors.append("PDK lock identity mismatch")
    if data.get("benchmark_profile_sha256") != _sha256(BENCHMARK_PROFILE_PATH):
        errors.append("benchmark profile identity mismatch")
    candidate_hash = data.get("candidate_sha256")
    if not isinstance(candidate_hash, str) or len(candidate_hash) != 64:
        errors.append("missing candidate digest")

    results = data.get("scenario_results")
    if not isinstance(results, list):
        return errors + ["scenario_results must be a list"]
    ids = [result.get("id") for result in results if isinstance(result, dict)]
    if len(ids) != len(set(ids)):
        errors.append("duplicate scenario result")
    missing = required_scenarios() - set(ids)
    extra = set(ids) - required_scenarios()
    if missing:
        errors.append(f"missing scenarios: {sorted(missing)}")
    if extra:
        errors.append(f"unknown scenarios: {sorted(extra)}")

    all_pass = True
    for result in results:
        if not isinstance(result, dict):
            errors.append("scenario result is not an object")
            all_pass = False
            continue
        label = result.get("id", "unknown")
        if result.get("view") not in VALID_VIEWS:
            errors.append(f"{label}: invalid or missing view")
        cases = result.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append(f"{label}: no individual cases")
            all_pass = False
            continue
        for case in cases:
            if not isinstance(case, dict) or not isinstance(case.get("passed"), bool):
                errors.append(f"{label}: malformed case verdict")
                all_pass = False
                continue
            if not case["passed"]:
                all_pass = False
            metrics = case.get("metrics", {})
            if not isinstance(metrics, dict):
                errors.append(f"{label}: metrics are not an object")
                all_pass = False
                continue
            for name, value in metrics.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                    errors.append(f"{label}: non-finite/non-numeric metric {name}")
                    all_pass = False

    claimed = data.get("complete_port_passed")
    if not isinstance(claimed, bool):
        errors.append("complete_port_passed must be boolean")
    elif claimed and (errors or not all_pass or set(ids) != required_scenarios()):
        errors.append("complete-port pass contradicts detailed evidence")
    return errors


def load_and_validate(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["evidence is missing or invalid JSON"]
    if not isinstance(data, dict):
        return ["evidence root must be an object"]
    return validate_result(data)
