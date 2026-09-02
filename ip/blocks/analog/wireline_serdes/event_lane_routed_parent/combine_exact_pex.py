#!/usr/bin/env python3
"""Fail-closed composition of split exact-parent PVT campaigns."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
HCLK_CONTRACT = (HERE.parent / "clock_pulse_hclk_window_probe" /
                 "hclk_window_contract.json")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def combine(paths: list[Path]) -> dict:
    require(len(paths) >= 1, "at least one result is required")
    inputs = [json.loads(path.read_text()) for path in paths]
    reference = inputs[0]
    identity_fields = ("claim", "scope", "physical_sha256", "pex_sha256", "control")
    for index, item in enumerate(inputs):
        require(item.get("schema_version") == 1, f"input {index}: unsupported schema")
        for field in identity_fields:
            require(item.get(field) == reference.get(field),
                    f"input {index}: {field} mismatch")
        require(item.get("result") == "pass", f"input {index}: result is not pass")
        require(item.get("passing_case_count") == item.get("case_count"),
                f"input {index}: incomplete passing count")
    cases = [case for item in inputs for case in item.get("cases", [])]
    observed = [case.get("environment_id") for case in cases]
    require(all(isinstance(identifier, str) for identifier in observed),
            "case environment id is missing")
    require(len(observed) == len(set(observed)), "duplicate environment case")
    expected = {item["id"] for item in json.loads(HCLK_CONTRACT.read_text())["environments"]}
    require(set(observed) == expected,
            f"environment set mismatch: expected {sorted(expected)}, got {sorted(observed)}")
    require(all(case.get("result") == "pass" for case in cases), "failed case present")
    cases.sort(key=lambda case: case["environment_id"])
    return {"schema_version": 1,
            "claim": "exact_routed_parent_five_environment_static_capture",
            "scope": reference["scope"],
            "physical_sha256": reference["physical_sha256"],
            "pex_sha256": reference["pex_sha256"],
            "control": reference["control"],
            "input_result_sha256": [digest(path) for path in paths],
            "environment_ids": sorted(expected), "case_count": len(cases),
            "passing_case_count": len(cases), "cases": cases,
            "not_a_claim": reference["not_a_claim"], "result": "pass"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = combine(args.inputs)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"],
                      "passing_case_count": result["passing_case_count"],
                      "case_count": result["case_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
