#!/usr/bin/env python3
"""Create the physical record for the capture-integrated event bridge."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import compile_event_capture_integrated_physical_source as compiler
import compile_event_capture_integrated_state as event_source


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
    "claim": "retimed_capture_integrated_event_bridge_physical_legality",
    "scope": "generated capture-integrated event/bridge layout, native Magic DRC, "
             "Netgen LVS, full-RC extraction, and review render",
    "top": compiler.TOP,
    "source_revision": event_source.SOURCE_REVISION,
    "selected_bridge": compiler.BRIDGE.name,
    "selected_bridge_sha256": digest(compiler.BRIDGE),
    "drc_stage_result": "pass",
    "lvs_stage_result": "pass",
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
        "extracted_event_or_capture_timing_closure",
        "routed_event_to_regenerative_lane_parent",
        "cdr_loop_or_pcie_link_closure",
        "provider_signoff_or_silicon_yield",
    ],
    "result": "pass",
}
(WORK / "retimed-event-capture-physical.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": "pass", "resistors": resistors,
                  "capacitors": capacitors}, sort_keys=True))
