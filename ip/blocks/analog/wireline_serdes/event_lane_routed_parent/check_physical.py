#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
for name in ("source", "layout", "drc", "lvs", "pex", "gds", "render", "output"):
    parser.add_argument(f"--{name}", type=Path, required=True)
args = parser.parse_args()
drc, lvs, pex = args.drc.read_text(), args.lvs.read_text(), args.pex.read_text()
count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
result = {
    "schema_version": 1,
    "claim": "routed_event_v7_fanout_regenerative_lane_physical_legality",
    "scope": "namespace-safe routed parent; DRC, unique LVS, full-RC extraction",
    "top": "event_lane_routed_parent",
    "drc_error_count": int(count.group(1)) if count else -1,
    "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
    "pex_resistor_count": len(re.findall(r"^R\S+\s", pex, re.MULTILINE)),
    "pex_capacitor_count": len(re.findall(r"^C\S+\s", pex, re.MULTILINE)),
    "identity": {
        "schematic_sha256": digest(args.source),
        "layout_source_sha256": digest(args.layout),
        "pex_sha256": digest(args.pex),
        "gds_sha256": digest(args.gds),
        "layout_image_sha256": digest(args.render),
    },
    "not_a_claim": ["post-layout timing", "five-environment closure",
                    "closed CDR or PCIe link", "provider signoff or silicon yield"],
}
passed = (result["drc_error_count"] == 0 and result["lvs_unique"] and
          result["pex_resistor_count"] > 10_000 and
          result["pex_capacitor_count"] > 7_000 and args.render.stat().st_size > 20_000)
result["result"] = "pass" if passed else "fail"
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": result["result"], "drc": result["drc_error_count"],
                  "lvs": result["lvs_unique"], "resistors": result["pex_resistor_count"],
                  "capacitors": result["pex_capacitor_count"]}, sort_keys=True))
if not passed:
    raise SystemExit(1)
