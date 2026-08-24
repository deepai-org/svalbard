#!/usr/bin/env python3
"""Merge independently simulated capture-calibration points."""

import argparse
import hashlib
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--case", action="append", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()

rows = []
for path in args.case:
    document = json.loads(path.read_text())
    point = (document.get("cases") or [{}])[0]
    rows.append({
        "case_id": document.get("case_id"),
        "controls": document.get("controls"),
        "environment": document.get("environment"),
        "minimum_sampler_even_v": point.get("minimum_sampler_even_v"),
        "minimum_sampler_odd_v": point.get("minimum_sampler_odd_v"),
        "minimum_frontend_even_v": point.get("minimum_frontend_even_v"),
        "minimum_frontend_odd_v": point.get("minimum_frontend_odd_v"),
        "minimum_frontend_write_even_v": point.get(
            "minimum_frontend_write_even_v"),
        "minimum_frontend_write_odd_v": point.get(
            "minimum_frontend_write_odd_v"),
        "minimum_capture_even_v": point.get("minimum_capture_even_v"),
        "minimum_capture_odd_v": point.get("minimum_capture_odd_v"),
        "result": document.get("result"),
        "evidence_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    })

result = {
    "schema_version": 1,
    "case_count": len(rows),
    "passing_case_count": sum(row["result"] == "pass" for row in rows),
    "cases": rows,
}
result["result"] = "pass" if result["passing_case_count"] else "fail"
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"capture scan: {result['passing_case_count']}/{len(rows)} pass")
