#!/usr/bin/env python3
"""Merge a declared exact-PEX data-restorer calibration screen."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--case", action="append", required=True, type=Path)
parser.add_argument("--claim", required=True)
parser.add_argument("--axis", required=True,
                    choices=("restorer_bias_v", "sampler_phase_deg"))
parser.add_argument("--expected", action="append", required=True)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
expected = {}
for declaration in args.expected:
    case_id, value = declaration.split("=", 1)
    expected[case_id] = float(value)
documents = [json.loads(path.read_text()) for path in args.case]
pex = [document.get("pex_sha256") for document in documents]
physical = [document.get("physical_sha256") for document in documents]
sources = [document.get("source_sha256") for document in documents]
valid = (
    len(documents) == 4
    and {document.get("case_id") for document in documents} == set(expected)
    and all(document.get("complete_case_count") == 1 for document in documents)
    and all(document.get("controls", {}).get("restorer_mode") == "data"
            for document in documents)
    and all(document.get("controls", {}).get(args.axis)
            == expected[document.get("case_id")] for document in documents)
    and all(identity == pex[0] for identity in pex[1:])
    and all(identity == physical[0] for identity in physical[1:])
    and all(identity == sources[0] for identity in sources[1:])
)
result = {
    "schema_version": 1,
    "claim": args.claim,
    "case_count": len(documents),
    "completed_case_count": sum(document.get("complete_case_count") == 1
                                for document in documents),
    "electrical_passing_case_count": sum(document.get("result") == "pass"
                                         for document in documents),
    "pex_sha256": pex[0] if pex else None,
    "physical_sha256": physical[0] if physical else None,
    "source_sha256": sources[0] if sources else None,
    "cases": [
        {
            "case_id": document.get("case_id"),
            args.axis: document.get("controls", {}).get(args.axis),
            "observed_case": (document.get("cases") or [None])[0],
            "electrical_result": document.get("result"),
            "evidence_sha256": sha256(path),
        }
        for path, document in zip(args.case, documents)
    ],
    "result": "pass" if valid else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"lane restorer sweep: {result['completed_case_count']}/{len(documents)} complete; "
      f"{result['electrical_passing_case_count']}/{len(documents)} electrical pass")
if not valid:
    raise SystemExit(1)
