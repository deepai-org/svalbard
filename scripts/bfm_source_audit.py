#!/usr/bin/env python3
"""Audit locked BFM sources for licenses and obvious shared lineage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "projects/pcie_gen1_endpoint/verification/dependencies.lock"
MAX_SOURCE_BYTES = 2 * 1024 * 1024
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".h", ".hpp", ".py", ".sv", ".v", ".vhd", ".vhdl"}


def fail(message: str) -> None:
    raise SystemExit(f"bfm-source-audit: {message}")


if len(sys.argv) != 3:
    fail("usage: bfm_source_audit.py MATERIALIZED_ROOT OUTPUT_JSON")

source_root = Path(sys.argv[1]).resolve()
output_path = Path(sys.argv[2]).resolve()
if output_path.exists():
    fail(f"output already exists: {output_path}")

document = json.loads(LOCK.read_text(encoding="utf-8"))
locked = {item["id"]: item for item in document["dependencies"] if "archive_url" in item}
license_results = {}
for dependency_id, item in sorted(locked.items()):
    dependency_root = source_root / dependency_id
    license_path = dependency_root / "LICENSE"
    if not dependency_root.is_dir() or not license_path.is_file():
        fail(f"{dependency_id} lacks its expected source root or LICENSE")
    observed = hashlib.sha256(license_path.read_bytes()).hexdigest()
    if observed != item["license_sha256"]:
        fail(f"license checksum mismatch for {dependency_id}")
    license_results[dependency_id] = {
        "spdx_observed": item["license"],
        "sha256": observed,
    }

families = {
    "cocotbext_pcie": [
        "bfm.cocotbext_pcie",
        "python.cocotbext_axi",
        "python.cocotb_bus",
        "python.cocotb_test",
    ],
    "pcievhost": ["bfm.pcievhost", "cosim.vproc"],
}
tokens = {
    "cocotbext_pcie": re.compile(r"pcievhost|wyvernsemi|\bvproc\b", re.IGNORECASE),
    "pcievhost": re.compile(r"cocotbext[-_. ]?pcie|alex forencich", re.IGNORECASE),
}
hashes: dict[str, dict[str, str]] = {}
language_counts: dict[str, dict[str, int]] = {}
cross_references = []
for family, dependency_ids in families.items():
    hashes[family] = {}
    language_counts[family] = {}
    for dependency_id in dependency_ids:
        for path in sorted((source_root / dependency_id).rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if path.stat().st_size > MAX_SOURCE_BYTES:
                fail(f"oversized source file in audit: {path}")
            relative = f"{dependency_id}/{path.relative_to(source_root / dependency_id)}"
            content = path.read_bytes()
            hashes[family][relative] = hashlib.sha256(content).hexdigest()
            suffix = path.suffix.lower()
            language_counts[family][suffix] = language_counts[family].get(suffix, 0) + 1
            if tokens[family].search(content.decode("utf-8", errors="ignore")):
                cross_references.append(relative)

if language_counts["cocotbext_pcie"].get(".py", 0) < 1:
    fail("cocotbext-pcie family has no Python implementation sources")
if not any(language_counts["pcievhost"].get(suffix, 0) for suffix in (".c", ".cpp", ".h")):
    fail("pcievhost family has no C/C++ implementation sources")
shared_hashes = sorted(set(hashes["cocotbext_pcie"].values()) & set(hashes["pcievhost"].values()))
if cross_references or shared_hashes:
    fail(
        "targeted lineage scan found cross-family references or byte-identical source: "
        f"references={cross_references}, shared_hashes={shared_hashes}"
    )

result = {
    "schema_version": 1,
    "result": "pass_with_limitations",
    "licenses": license_results,
    "lineage_scan": {
        "cross_family_name_or_attribution_references": [],
        "byte_identical_source_files": [],
        "language_source_counts": language_counts,
        "conclusion": "no shared code lineage observed in the targeted locked-source scan",
    },
    "limitations": [
        "archive snapshots do not contain full revision history",
        "absence of matching names or source hashes cannot prove independent specification interpretation",
        "this audit does not qualify either model against the SVALBARD endpoint",
    ],
}
output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("bfm-source-audit: PASS (licenses and targeted lineage scan)")
