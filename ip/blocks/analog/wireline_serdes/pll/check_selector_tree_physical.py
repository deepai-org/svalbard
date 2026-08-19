#!/usr/bin/env python3
"""Check hierarchical selector-tree DRC/LVS/full-RC and render evidence."""
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
        "schema_version": 1,
        "claim": "balanced_sixteen_leaf_physical_selector_tree",
        "used_leaf_count": 12,
        "spare_leaf_count": 4,
        "selector_instance_count": 15,
        "logic_depth": 4,
        "drc_error_count": int(match.group(1)) if match else -1,
        "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": digest(args.pex),
        "layout_source_sha256": digest(args.source / "selector_tree_layout.tcl"),
        "schematic_source_sha256": digest(args.source / "selector_tree.spice"),
        "selector_unit_layout_sha256": digest(args.source / "selector_unit_layout.tcl"),
        "selector_unit_schematic_sha256": digest(args.source / "selector_unit.spice"),
        "shared_layout_generator_sha256": digest(
            args.source.parent / "phase_interpolator" / "layout.tcl"),
        "layout_image_sha256": digest(args.render),
        "layout_image_bytes": args.render.stat().st_size,
    }
    passed = (result["drc_error_count"] == 0 and result["lvs_unique"]
              and result["pex_resistor_count"] >= 15 * 300
              and result["pex_capacitor_count"] >= 15 * 100
              and result["layout_image_bytes"] >= 20_000)
    result["result"] = "pass" if passed else "fail"
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"selector tree physical: DRC={result['drc_error_count']}; "
          f"LVS={result['lvs_unique']}; PEX={result['pex_resistor_count']}R/"
          f"{result['pex_capacitor_count']}C")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
