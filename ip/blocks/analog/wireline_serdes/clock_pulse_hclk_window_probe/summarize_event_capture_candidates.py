#!/usr/bin/env python3
"""Create a hash-bound comparison of event/capture schematic campaigns."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(path: Path) -> dict:
    record = json.loads(path.read_text())
    required = {
        "case_count", "passing_case_count", "environment_code_coverage",
        "source_sha256", "contract_sha256", "result",
    }
    missing = sorted(required - set(record))
    if missing:
        raise ValueError(f"{path}: missing campaign fields {missing}")
    coverage = record["environment_code_coverage"]
    if not isinstance(coverage, dict) or not coverage:
        raise ValueError(f"{path}: invalid environment coverage")
    return {
        "id": path.stem,
        "input_sha256": digest(path),
        "source_sha256": record["source_sha256"],
        "bridge_sha256": record.get("bridge_sha256"),
        "contract_sha256": record["contract_sha256"],
        "case_count": record["case_count"],
        "passing_case_count": record["passing_case_count"],
        "covered_environment_count": sum(bool(codes) for codes in coverage.values()),
        "environment_count": len(coverage),
        "environment_code_coverage": coverage,
        "result": record["result"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("results", nargs="+", type=Path)
    args = parser.parse_args()
    candidates = [summarize(path) for path in args.results]
    identities = [(item["source_sha256"], item["bridge_sha256"])
                  for item in candidates]
    output = {
        "schema_version": 1,
        "claim": "event_capture_schematic_candidate_comparison",
        "candidate_count": len(candidates),
        "unique_circuit_identity_count": len(set(identities)),
        "candidates": candidates,
        "not_a_claim": [
            "automatic_candidate_generation",
            "candidate_optimum",
            "layout_or_extracted_qualification",
            "five_environment_physical_closure",
        ],
        "result": "recorded",
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"candidate_count": len(candidates),
                      "unique_circuit_identity_count": len(set(identities))},
                     sort_keys=True))


if __name__ == "__main__":
    main()
