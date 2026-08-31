#!/usr/bin/env python3
"""Validate physical closure of the Wi-Fi LNA/mixer routed parent."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("source", "drc", "lvs", "pex", "gds", "render", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    drc = args.drc.read_text()
    lvs = args.lvs.read_text()
    pex = args.pex.read_text()
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
    result = {
        "schema_version": 1,
        "claim": "wifi_2p4g_lna_external_lo_mixer_routed_parent",
        "drc_error_count": int(count.group(1)) if count else -1,
        "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": digest(args.pex),
        "gds_sha256": digest(args.gds),
        "layout_image_sha256": digest(args.render),
        "layout_image_bytes": args.render.stat().st_size,
        "layout_source_sha256": {
            "parent": digest(args.source / "layout.tcl"),
            "lna": digest(args.source.parent / "rf_lna" / "layout.tcl"),
            "mixer": digest(args.source.parent / "rf_switch_mixer" / "layout.tcl"),
        },
        "schematic_source_sha256": {
            "parent": digest(args.source / "rf_rx_external_lo_parent.spice"),
            "lna": digest(args.source.parent / "rf_lna" / "lna_cs_core.spice"),
            "mixer": digest(args.source.parent / "rf_switch_mixer" / "mixer.spice"),
        },
        "checker_source_sha256": digest(Path(__file__)),
    }
    passed = (result["drc_error_count"] == 0 and result["lvs_unique"]
              and result["pex_resistor_count"] >= 200
              and result["pex_capacitor_count"] >= 150
              and result["layout_image_bytes"] >= 15_000)
    result["result"] = "pass" if passed else "fail"
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("wifi LNA/mixer routed parent physical: "
          f"DRC={result['drc_error_count']} LVS={result['lvs_unique']} "
          f"PEX={result['pex_resistor_count']}R/{result['pex_capacitor_count']}C")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
