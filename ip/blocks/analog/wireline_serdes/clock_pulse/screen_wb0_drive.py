#!/usr/bin/env python3
"""Create a non-promotable PEX drive counterfactual for the write taper.

The compact clock-pulse PEX has a clear SS/hot failure: the WPN interval
exists, but the first write stage does not reliably regenerate and the later
taper receives too little usable time.  This helper changes only an explicitly
named stage or the active devices through the first four taper stages to rank a
layout revision direction.  It intentionally does *not* scale the associated
diffusion/gate parasitics, so its output is diagnostic data and can never be
used as physical-release evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--pex", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--report", required=True, type=Path)
parser.add_argument("--scale", required=True, type=float)
parser.add_argument("--scope", choices=("wb0", "active_taper"),
                    default="wb0")
args = parser.parse_args()

if not 1.0 < args.scale <= 4.0:
    parser.error("--scale must be greater than 1 and no more than 4")

width = re.compile(r"\bw=([-+0-9.eE]+)u\b")
changed: list[dict[str, object]] = []
rewritten: list[str] = []

for line in args.pex.read_text().splitlines():
    fields = line.split()
    # Extracted FET syntax is: instance drain gate source bulk model params.
    wb0_target = (
        len(fields) >= 6
        and fields[0].startswith("X")
        and fields[2].startswith(("DBG_E_WPN.", "DBG_O_WPN."))
        # Magic may reverse source and drain while preserving the PMOS body.
        # The target output can therefore be either terminal one or three.
        and (fields[1].startswith(("DBG_E_WB1.", "DBG_O_WB1."))
             or fields[3].startswith(("DBG_E_WB1.", "DBG_O_WB1.")))
        and fields[5] == "pfet_03v3"
    )
    active_taper_target = (
        len(fields) >= 6
        and fields[0].startswith("X")
        and ((fields[5] == "pfet_03v3"
              and fields[2].startswith(("DBG_E_WPN.", "DBG_O_WPN."))
              and (fields[1].startswith(("DBG_E_WB1.", "DBG_O_WB1."))
                   or fields[3].startswith(("DBG_E_WB1.", "DBG_O_WB1."))))
             or (fields[5] == "nfet_03v3"
                 and fields[2].startswith(("DBG_E_WB1.", "DBG_O_WB1."))
                 and (fields[1].startswith(("DBG_E_WB2.", "DBG_O_WB2."))
                      or fields[3].startswith(("DBG_E_WB2.", "DBG_O_WB2."))))
             or (fields[5] == "pfet_03v3"
                 and fields[2].startswith(("DBG_E_WB2.", "DBG_O_WB2."))
                 and (fields[1].startswith(("DBG_E_WB3.", "DBG_O_WB3."))
                      or fields[3].startswith(("DBG_E_WB3.", "DBG_O_WB3."))))
             or (fields[5] == "nfet_03v3"
                 and fields[2].startswith(("DBG_E_WB3.", "DBG_O_WB3.")))))
    target = wb0_target if args.scope == "wb0" else active_taper_target
    if target:
        match = width.search(line)
        if not match:
            raise SystemExit(f"no width on target device: {line}")
        old_width = float(match.group(1))
        new_width = old_width * args.scale
        line = line[:match.start(1)] + f"{new_width:.12g}" + line[match.end(1):]
        changed.append({"instance": fields[0], "old_width_um": old_width,
                        "new_width_um": new_width})
    rewritten.append(line)

# Failing closed prevents this mechanism probe from silently becoming a broad
# or empty PEX rewrite after a layout edit.
expected_count = 4 if args.scope == "wb0" else 36
if len(changed) != expected_count:
    raise SystemExit(f"expected {expected_count} target fingers, found {len(changed)}")

args.output.write_text("\n".join(rewritten) + "\n")
args.report.write_text(json.dumps({
    "schema_version": 1,
    "claim": "clock_pulse_write_taper_drive_counterfactual",
    "classification": "diagnostic_only_not_physical_release_evidence",
    "input_pex_sha256": hashlib.sha256(args.pex.read_bytes()).hexdigest(),
    "output_pex_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    "scale": args.scale,
    "scope": args.scope,
    "changed_devices": changed,
    "parasitics_scaled": False,
    "required_followup": "realize the candidate in layout, run DRC/LVS/full-RC PEX, and replay the declared contract",
}, indent=2, sort_keys=True) + "\n")
