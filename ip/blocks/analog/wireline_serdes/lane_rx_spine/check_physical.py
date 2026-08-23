#!/usr/bin/env python3
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
    for name in ("source", "drc", "lvs", "pex", "gds", "render", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    drc = args.drc.read_text()
    lvs = args.lvs.read_text()
    pex = args.pex.read_text()
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
    result = {
        "schema_version": 1,
        "claim": "routed_rx_restorer_sampler_parent",
        "drc_error_count": int(count.group(1)) if count else -1,
        "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": sha256_file(args.pex),
        "gds_sha256": sha256_file(args.gds),
        "layout_image_sha256": sha256_file(args.render),
        "layout_image_bytes": args.render.stat().st_size,
        "layout_source_sha256": sha256_file(args.source / "layout.tcl"),
        "schematic_source_sha256": sha256_file(args.source / "lane_rx_spine.spice"),
        "checker_source_sha256": sha256_file(Path(__file__)),
    }
    passed = (
        result["drc_error_count"] == 0
        and result["lvs_unique"]
        and result["pex_resistor_count"] >= 1000
        and result["pex_capacitor_count"] >= 400
        and result["layout_image_bytes"] >= 20_000
    )
    result["result"] = "pass" if passed else "fail"
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"lane RX spine physical: DRC={result['drc_error_count']} "
        f"LVS={result['lvs_unique']} PEX={result['pex_resistor_count']}R/"
        f"{result['pex_capacitor_count']}C"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
