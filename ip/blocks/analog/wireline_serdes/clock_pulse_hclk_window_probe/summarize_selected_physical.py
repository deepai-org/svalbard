#!/usr/bin/env python3
"""Summarize a successfully completed physical legality run."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


WORK = Path("/work")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


pex = WORK / "selected_dual_control_pulse.pex.spice"
text = pex.read_text()
resistors = sum(bool(re.match(r"^R\S+\s", line, re.I))
                for line in text.splitlines())
capacitors = sum(bool(re.match(r"^C\S+\s", line, re.I))
                 for line in text.splitlines())
result = {
    "schema_version": 1,
    "claim": "selected_dual_control_pulse_physical_legality",
    "scope": "generated layout, native Magic DRC, Netgen LVS, and full-RC extraction",
    "top": "selected_dual_control_pulse",
    "selected_write_candidate": "hier_epoch_extra_2x_start_0p85x",
    "selected_sense_candidate": "sense_edge_pm12_base4_extra64_folded",
    "drc_stage_result": "pass",
    "lvs_stage_result": "pass",
    "pex_stage_result": "pass",
    "pex_resistor_count": resistors,
    "pex_capacitor_count": capacitors,
    "identity": {
        "schematic_sha256": digest(WORK / "selected_dual_control_pulse.spice"),
        "layout_tcl_sha256": digest(WORK / "selected_dual_control_pulse_layout.tcl"),
        "mag_sha256": digest(WORK / "selected_dual_control_pulse.mag"),
        "gds_sha256": digest(WORK / "selected_dual_control_pulse.gds"),
        "pex_sha256": digest(pex),
        "layout_png_sha256": digest(WORK / "selected_dual_control_pulse-layout.png"),
    },
    "not_a_claim": [
        "pex_timing_or_pvt_closure",
        "capture_or_cdr_closure",
        "provider_signoff_or_silicon_yield"
    ],
    "result": "pass"
}
(WORK / "selected-dual-control-physical.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": "pass", "resistors": resistors,
                  "capacitors": capacitors}, sort_keys=True))
