#!/usr/bin/env python3
"""Merge worst-environment RX bandwidth-mode/channel screen."""

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
    "low_ch6": ("low", 6.0, 1e-12), "low_ch7": ("low", 7.0, 1.25e-12),
    "high_ch6": ("high", 6.0, 1e-12), "high_ch7": ("high", 7.0, 1.25e-12),
}


def setting(document: dict) -> tuple[str, float, float]:
    channel = document.get("channel_stress", {})
    return (document.get("controls", {}).get("rx_bandwidth_mode"),
            channel.get("series_resistance_ohm_per_leg"),
            channel.get("differential_shunt_capacitance_f"))


valid = (
    len(documents) == 4
    and {document.get("case_id") for document in documents} == set(expected)
    and all(document.get("complete_case_count") == 1 for document in documents)
    and all(setting(document) == expected[document.get("case_id")]
            for document in documents)
    and all(identity == pex[0] for identity in pex[1:])
    and all(identity == physical[0] for identity in physical[1:])
    and all(identity == sources[0] for identity in sources[1:])
)
result = {
    "schema_version": 1,
    "claim": "completed_worst_environment_rx_bandwidth_mode_channel_screen",
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
            "rx_bandwidth_mode": document.get("controls", {}).get("rx_bandwidth_mode"),
            "channel_stress": document.get("channel_stress"),
            "observed_case": (document.get("cases") or [None])[0],
            "electrical_result": document.get("result"),
            "evidence_sha256": sha256(path),
        }
        for path, document in zip(args.case, documents)
    ],
    "result": "pass" if valid else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"RX bandwidth-mode screen: {result['completed_case_count']}/{len(documents)} "
      f"complete; {result['electrical_passing_case_count']}/{len(documents)} pass")
if not valid:
    raise SystemExit(1)
