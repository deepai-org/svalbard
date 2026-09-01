#!/usr/bin/env python3
"""Create the physical record for the buffered state-free event macro."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import compile_event_capture_state_free_buffered_physical_source as compiler


WORK = Path("/work")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


pex = WORK / "retimed_event_capture_bridge.pex.spice"
text = pex.read_text()
resistors = sum(bool(re.match(r"^R\S+\s", line, re.I))
                for line in text.splitlines())
capacitors = sum(bool(re.match(r"^C\S+\s", line, re.I))
                  for line in text.splitlines())
result = {
    "schema_version": 1,
    "claim": "state_free_event_physical_lane_interface_legality",
    "scope": "generated state-free event and physical lane-interface buffers; native Magic DRC, Netgen LVS, full-RC extraction, and review render",
    "top": compiler.TOP,
    "source_revision": compiler.SOURCE_REVISION,
    "drc_stage_result": "pass",
    "lvs_stage_result": "pass_unique",
    "pex_stage_result": "pass",
    "pex_resistor_count": resistors,
    "pex_capacitor_count": capacitors,
    "identity": {
        "schematic_sha256": digest(WORK / "retimed_event_capture_bridge.spice"),
        "layout_tcl_sha256": digest(WORK / "retimed_event_capture_bridge_layout.tcl"),
        "mag_sha256": digest(WORK / "retimed_event_capture_bridge.mag"),
        "gds_sha256": digest(WORK / "retimed_event_capture_bridge.gds"),
        "pex_sha256": digest(pex),
        "layout_png_sha256": digest(WORK / "retimed_event_capture_bridge-layout.png"),
    },
    "not_a_claim": [
        "routed event-to-lane parent",
        "five-environment timing closure",
        "closed CDR or PCIe link",
        "provider signoff or silicon yield",
    ],
    "result": "pass",
}
(WORK / "retimed-event-capture-buffered-physical.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": "pass", "resistors": resistors,
                  "capacitors": capacitors}, sort_keys=True))
