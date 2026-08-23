#!/usr/bin/env python3
"""Merge the exact-PEX lane RC-channel boundary sweep."""

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
pex = [document.get("pex_sha256") for document in documents]
physical = [document.get("physical_sha256") for document in documents]
sources = [document.get("source_sha256") for document in documents]
expected = {
    "ch6": (6.0, 1e-12), "ch7": (7.0, 1.25e-12),
    "ch8": (8.0, 1.5e-12), "ch9": (9.0, 1.75e-12),
}


def declared(document: dict) -> tuple[float, float]:
    channel = document.get("channel_stress", {})
    return (channel.get("series_resistance_ohm_per_leg"),
            channel.get("differential_shunt_capacitance_f"))


valid = (
    len(documents) == 4
    and {document.get("case_id") for document in documents} == set(expected)
    and all(document.get("complete_case_count") == 1 for document in documents)
    and all(declared(document) == expected[document.get("case_id")]
            for document in documents)
    and all(identity == pex[0] for identity in pex[1:])
    and all(identity == physical[0] for identity in physical[1:])
    and all(identity == sources[0] for identity in sources[1:])
)
result = {
    "schema_version": 1,
    "claim": "completed_exact_pex_lane_rc_channel_boundary_sweep",
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
            "channel_stress": document.get("channel_stress"),
            "observed_case": document.get("cases", [None])[0],
            "electrical_result": document.get("result"),
            "evidence_sha256": sha256(path),
        }
        for path, document in zip(args.case, documents)
    ],
    "result": "pass" if valid else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"lane channel sweep: {result['completed_case_count']}/{len(documents)} complete; "
      f"{result['electrical_passing_case_count']}/{len(documents)} electrical pass")
if not valid:
    raise SystemExit(1)
