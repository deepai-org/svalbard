#!/usr/bin/env python3
"""Merge fail-closed representative extracted lane environments."""

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
environments = [tuple(document.get("environment", ())) for document in documents]
valid = (
    len(documents) == 5
    and len(set(environments)) == 5
    and all(document.get("result") == "pass" for document in documents)
    and all(document.get("extraction") == "full_rc_leaves" for document in documents)
    and all(document.get("serial_rate_hz") == 1.25e9 for document in documents)
)
result = {
    "schema_version": 1,
    "claim": "representative_pvt_externally_clocked_1p25_gbd_tx_to_sampler",
    "environment_count": len(documents),
    "passing_environment_count": sum(document.get("result") == "pass" for document in documents),
    "cases": [
        {
            "environment": document.get("environment"),
            "controls": document.get("controls"),
            "selected_case": document.get("selected_case"),
            "evidence_sha256": sha256(path),
            "result": document.get("result"),
        }
        for path, document in zip(args.case, documents)
    ],
    "result": "pass" if valid else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"lane representative PVT: {result['passing_environment_count']}/{len(documents)} pass")
if not valid:
    raise SystemExit(1)
