#!/usr/bin/env python3
"""Check the routed selected-bank parent physical boundary."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SERDES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERDES_ROOT))

from analog_evidence import sha256_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--lvs", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--gds", type=Path, required=True)
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    drc, lvs, pex = args.drc.read_text(), args.lvs.read_text(), args.pex.read_text()
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
    result = {
        "schema_version": 1,
        "claim": "physical_selected_two_vco_bias_dac_selector_parent",
        "selected_vco_members": ["split_fast", "split_gain"],
        "bias_dac_instance_count": 2,
        "selector_instance_count": 1,
        "selector_cell": "vco_selector_unit",
        "selector_signal_pair_copies": 2,
        "drc_error_count": int(count.group(1)) if count else -1,
        "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": sha256_file(args.pex),
        "gds_sha256": sha256_file(args.gds),
        "layout_image_sha256": sha256_file(args.render),
        "layout_image_bytes": args.render.stat().st_size,
        "layout_source_sha256": sha256_file(args.source / "vco_bank_top_layout.tcl"),
        "schematic_source_sha256": sha256_file(args.source / "vco_bank_top.spice"),
        "shared_evidence_source_sha256": sha256_file(
            SERDES_ROOT / "analog_evidence.py"
        ),
    }
    passed = (
        result["drc_error_count"] == 0
        and result["lvs_unique"]
        and result["pex_resistor_count"] >= 3000
        and result["pex_capacitor_count"] >= 1000
        and result["layout_image_bytes"] >= 20_000
    )
    result["result"] = "pass" if passed else "fail"
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"selected VCO bank parent: drc={result['drc_error_count']}; "
        f"lvs={result['lvs_unique']}; pex={result['pex_resistor_count']}R/"
        f"{result['pex_capacitor_count']}C"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
