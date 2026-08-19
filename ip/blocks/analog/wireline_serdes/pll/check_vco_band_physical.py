#!/usr/bin/env python3
"""Check physical closure of the hierarchical VCO-band macro."""
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
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--lvs", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    drc, lvs, pex = args.drc.read_text(), args.lvs.read_text(), args.pex.read_text()
    match = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
    result = {
        "schema_version": 1, "claim": "physical_vco_band_with_startup",
        "delay_instance_count": 4, "startup_device_count": 2,
        "delay_geometry": {
            "cell": "cml_vco_delay_margin_fast", "load_length_um": 4.0,
            "cap_width_um": 3.2, "cap_length_um": 0.37,
            "main_tail_width_um": 15.0, "latch_tail_width_um": 6.0,
        },
        "drc_error_count": int(match.group(1)) if match else -1,
        "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": digest(args.pex),
        "layout_source_sha256": digest(args.source / "vco_band_layout.tcl"),
        "schematic_source_sha256": digest(args.source / "vco_band.spice"),
        "delay_schematic_source_sha256": digest(args.source / "physical_variants.spice"),
        "delay_layout_source_sha256": digest(args.source / "layout.tcl"),
        "startup_layout_source_sha256": digest(args.source / "startup_assist_layout.tcl"),
        "layout_image_sha256": digest(args.render),
        "layout_image_bytes": args.render.stat().st_size,
    }
    passed = (result["drc_error_count"] == 0 and result["lvs_unique"]
              and result["pex_resistor_count"] >= 4 * 250
              and result["pex_capacitor_count"] >= 4 * 70
              and result["layout_image_bytes"] >= 20_000)
    result["result"] = "pass" if passed else "fail"
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"VCO band physical: DRC={result['drc_error_count']}; "
          f"LVS={result['lvs_unique']}; PEX={result['pex_resistor_count']}R/"
          f"{result['pex_capacitor_count']}C")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
