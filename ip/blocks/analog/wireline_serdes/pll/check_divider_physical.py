#!/usr/bin/env python3
"""Bind physical closure and extracted PVT evidence for the CML divider."""
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
    parser.add_argument("--extracted", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    drc, lvs, pex = args.drc.read_text(), args.lvs.read_text(), args.pex.read_text()
    extracted = json.loads(args.extracted.read_text())
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
    pex_hash = sha256_file(args.pex)
    component_results = {
        "drc": int(count.group(1)) == 0 if count else False,
        "lvs": lvs.count("Final result: Circuits match uniquely.") == 1,
        "full_rc": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)) >= 100
        and len(re.findall(r"^C\d+\s", pex, re.MULTILINE)) >= 20,
        "extracted_pvt": extracted.get("result") == "pass"
        and extracted.get("extraction") == "full_rc"
        and extracted.get("case_count") == 25
        and extracted.get("passing_environment_count") == 5
        and extracted.get("selected_load_length_um") == 7.5
        and extracted.get("pex_sha256") == pex_hash,
    }
    passed = all(component_results.values()) and args.render.stat().st_size >= 10_000
    result = {
        "schema_version": 1,
        "claim": "physical_static_cml_divide_by_two",
        "component_results": component_results,
        "drc_error_count": int(count.group(1)) if count else -1,
        "lvs_unique": component_results["lvs"],
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": pex_hash,
        "gds_sha256": sha256_file(args.gds),
        "layout_image_sha256": sha256_file(args.render),
        "layout_source_sha256": sha256_file(args.source / "divider_layout.tcl"),
        "schematic_source_sha256": sha256_file(args.source / "divider.spice"),
        "extracted_evidence_sha256": sha256_file(args.extracted),
        "checker_source_sha256": sha256_file(Path(__file__)),
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"CML divider physical: drc={result['drc_error_count']}; "
        f"lvs={result['lvs_unique']}; PEX={result['pex_resistor_count']}R/"
        f"{result['pex_capacitor_count']}C; extracted={extracted.get('result')}"
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
