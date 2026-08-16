#!/usr/bin/env python3
"""Reduce the two upstream BFM smoke results to one compact JSON document."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


def fail(message: str) -> None:
    raise SystemExit(f"bfm-smoke: {message}")


if len(sys.argv) != 5:
    fail("usage: check_results.py RESULTS_XML PCIEVHOST_LOG SOURCE_AUDIT OUTPUT_JSON")

xml_path, log_path, source_audit_path, output_path = map(Path, sys.argv[1:])
source_audit = json.loads(source_audit_path.read_text(encoding="utf-8"))
if source_audit.get("result") != "pass_with_limitations":
    fail("source audit result is absent or invalid")
root = ET.parse(xml_path).getroot()
suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
if not suites:
    fail("cocotbext-pcie produced no JUnit test suite")

cases = list(root.iter("testcase"))
tests = len(cases)
failures = sum(1 for case in cases if case.find("failure") is not None)
errors = sum(1 for case in cases if case.find("error") is not None)
skipped = sum(1 for case in cases if case.find("skipped") is not None)
if tests < 1 or failures or errors:
    fail(
        f"cocotbext-pcie JUnit result is not clean: "
        f"tests={tests} failures={failures} errors={errors}"
    )

text = log_path.read_text(encoding="utf-8", errors="replace")
plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
markers = {
    "good_lcrc": plain.count("Good LCRC"),
    "good_dllp_crc": plain.count("Good DLLP CRC"),
    "ack": plain.count("DL Ack seq"),
    "update_fc": plain.count("UpdateFC-"),
    "completion": plain.count("TL Completion"),
}
if "$finish" not in plain or "Verilator: cpu" not in plain:
    fail("pcievhost did not reach a normal Verilator finish")
if any(count < 1 for count in markers.values()):
    fail(f"pcievhost traffic marker missing: {markers}")

result = {
    "schema_version": 1,
    "result": "pass",
    "qualification": "upstream representative smoke only",
    "cocotbext_pcie": {
        "revision": "92732edd2d8cef002f0e984697ff31ccfe8a19a9",
        "tests": tests,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
    },
    "pcievhost": {
        "revision": "b82b2ff3a047f742354c9607dea34b9b97bf108c",
        "normal_finish": True,
        "traffic_markers": markers,
    },
    "source_audit": source_audit,
    "limitations": [
        "these are upstream self-tests, not tests against the SVALBARD endpoint",
        "the pair's specification-interpretation independence remains unproven",
        "pcievhost documents only partial LTSSM coverage",
        "cocotbext-pcie does not provide the custom endpoint serial PHY boundary"
    ]
}
output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"bfm-smoke: cocotbext-pcie PASS ({tests} tests)")
print(f"bfm-smoke: pcievhost PASS ({markers})")
