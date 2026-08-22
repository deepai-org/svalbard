#!/usr/bin/env python3
"""Merge representative extracted lane-to-CMOS-capture environments."""

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
pex_identities = [document.get("pex_sha256") for document in documents]
physical_identities = [document.get("physical_sha256") for document in documents]
valid = (
    len(documents) == 5 and len(set(environments)) == 5
    and all(document.get("result") == "pass" for document in documents)
    and all(identity == pex_identities[0] for identity in pex_identities[1:])
    and all(identity == physical_identities[0] for identity in physical_identities[1:])
)
result = {
    "schema_version": 1,
    "claim": "representative_pvt_extracted_1p25_gbd_lane_dual_cmos_capture",
    "environment_count": len(documents),
    "passing_environment_count": sum(document.get("result") == "pass" for document in documents),
    "pex_sha256": pex_identities[0] if pex_identities else None,
    "physical_sha256": physical_identities[0] if physical_identities else None,
    "cases": [
        {"environment": document.get("environment"), "controls": document.get("controls"),
         "selected_case": document.get("selected_case"), "result": document.get("result"),
         "evidence_sha256": sha256(path)}
        for path, document in zip(args.case, documents)
    ],
    "result": "pass" if valid else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"lane dual-capture PVT: {result['passing_environment_count']}/{len(documents)} pass")
if not valid:
    raise SystemExit(1)
