#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path

from compile_segment import KINDS, SOURCE_REVISION


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
work, segments = Path("/work"), {}
for kind, (top, stages) in KINDS.items():
    drc = next((work / f"{kind}-drc").rglob("*.rpt")).read_text()
    lvs = next((work / f"{kind}-lvs").rglob("*.lvs.out")).read_text()
    pex_path = work / f"{kind}.pex.spice"
    pex = pex_path.read_text()
    counts = [int(x) for x in re.findall(r"(?:TOTAL DRC Errors\s*=|COUNT:)\s*(\d+)", drc)]
    if not counts or max(counts) or "Circuits match uniquely" not in lvs:
        raise RuntimeError(f"{kind}: physical legality failure")
    if "Property errors were found" in lvs:
        raise RuntimeError(f"{kind}: device-property mismatch")
    segments[kind] = {
        "top": top, "stage_multiplicities": list(stages),
        "drc_errors": 0, "lvs_result": "pass_unique",
        "pex_resistor_count": len(re.findall(r"^R\S+\s", pex, re.I | re.M)),
        "pex_capacitor_count": len(re.findall(r"^C\S+\s", pex, re.I | re.M)),
        "identity": {
            "source_sha256": digest(work / f"{kind}.spice"),
            "lvs_view_sha256": digest(work / f"{kind}-lvs.spice"),
            "layout_tcl_sha256": digest(work / f"{kind}-layout.tcl"),
            "mag_sha256": digest(work / f"{top}.mag"),
            "pex_sha256": digest(pex_path),
        },
    }
result = {
    "schema_version": 1,
    "claim": "consumer_local_clock_segment_physical_legality",
    "source_revision": SOURCE_REVISION,
    "segments": segments,
    "result": "pass",
    "not_a_claim": ["composed timing", "routed parent", "PCIe compliance"],
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
