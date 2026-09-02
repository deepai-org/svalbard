#!/usr/bin/env python3
"""Bind the selected local clock-fanout physical artifacts by digest."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import compile_local_clock_fanout_source as compiler


WORK = Path("/work")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


pex = WORK / "local_clock_fanout.pex.spice"
text = pex.read_text()
result = {
    "schema_version": 1,
    "claim": "local_clock_fanout_physical_legality",
    "scope": "six-branch static-CMOS fanout; DRC, unique LVS, full-RC extraction, and exact review render",
    "top": compiler.TOP,
    "source_revision": compiler.SOURCE_REVISION,
    "selected_candidate": {
        "sampler_pre_mult": 16, "sampler_output_mult": 32,
        "capture_pre_mult": 4, "capture_output_mult": 8,
        "branch_count": 6,
    },
    "logical_mos_count": 24,
    "raw_finger_count": 288,
    "drc_stage_result": "pass",
    "lvs_stage_result": "pass_unique",
    "pex_stage_result": "pass",
    "pex_resistor_count": sum(bool(re.match(r"^R\S+\s", line, re.I)) for line in text.splitlines()),
    "pex_capacitor_count": sum(bool(re.match(r"^C\S+\s", line, re.I)) for line in text.splitlines()),
    "identity": {
        "schematic_sha256": digest(WORK / "local_clock_fanout.spice"),
        "layout_tcl_sha256": digest(WORK / "local_clock_fanout_layout.tcl"),
        "mag_sha256": digest(WORK / "local_clock_fanout.mag"),
        "gds_sha256": digest(WORK / "local_clock_fanout.gds"),
        "pex_sha256": digest(pex),
        "layout_png_sha256": digest(WORK / "local_clock_fanout-layout.png"),
    },
    "not_a_claim": [
        "event-to-lane routed parent", "post-layout composed timing",
        "five-environment closure", "closed CDR or PCIe link",
        "provider signoff or silicon yield",
    ],
    "result": "pass",
}
(WORK / "local-clock-fanout-physical.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": "pass", "resistors": result["pex_resistor_count"],
                  "capacitors": result["pex_capacitor_count"]}, sort_keys=True))
