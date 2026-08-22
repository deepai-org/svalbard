#!/usr/bin/env python3
"""Validate the declared long-pattern channel and timing stress matrix."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--case", action="append", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
documents = [json.loads(path.read_text()) for path in args.case]
expected_ids = {"prbs_base", "channel", "timing", "combined"}
ids = {document.get("case_id") for document in documents}
pex = [document.get("pex_sha256") for document in documents]
physical = [document.get("physical_sha256") for document in documents]
selected = [document.get("selected_case") or {} for document in documents]
valid = (
    len(documents) == 4 and ids == expected_ids
    and all(document.get("result") == "pass" for document in documents)
    and all(document.get("stimulus", {}).get("pattern") == "prbs7"
            and document.get("stimulus", {}).get("bit_count") == 64
            and document.get("stimulus", {}).get("scored_pair_count") == 28
            for document in documents)
    and all(identity == pex[0] for identity in pex[1:])
    and all(identity == physical[0] for identity in physical[1:])
)
result = {
    "schema_version": 1,
    "claim": "bounded_extracted_1p25_gbd_lane_capture_stress",
    "case_count": len(documents),
    "passing_case_count": sum(document.get("result") == "pass" for document in documents),
    "pex_sha256": pex[0] if pex else None,
    "physical_sha256": physical[0] if physical else None,
    "minimum_frontend_margin_v": min(
        min(case.get("minimum_frontend_even_v", 0.0),
            case.get("minimum_frontend_odd_v", 0.0)) for case in selected
    ),
    "minimum_capture_margin_v": min(
        min(case.get("minimum_capture_even_v", 0.0),
            case.get("minimum_capture_odd_v", 0.0)) for case in selected
    ),
    "minimum_supply_current_a": min(case.get("supply_current_a", 0.0) for case in selected),
    "maximum_supply_current_a": max(case.get("supply_current_a", 0.0) for case in selected),
    "cases": [
        {
            "case_id": document.get("case_id"),
            "stimulus": document.get("stimulus"),
            "channel_stress": document.get("channel_stress"),
            "selected_case": document.get("selected_case"),
            "result": document.get("result"),
            "evidence_sha256": sha256(path),
        }
        for path, document in zip(args.case, documents)
    ],
    "result": "pass" if valid else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"lane capture stress: {result['passing_case_count']}/{len(documents)} pass")
if not valid:
    raise SystemExit(1)
