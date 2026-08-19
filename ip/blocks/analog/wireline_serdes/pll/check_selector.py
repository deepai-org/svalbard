#!/usr/bin/env python3
"""Bind the reused selector layout to its extracted endpoint/handoff evidence."""
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
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--simulation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    drc = (args.work / "selector-drc.rpt").read_text()
    lvs = (args.work / "selector-lvs.out").read_text()
    pex_path = args.work / "phase_interpolator.pex.spice"
    pex = pex_path.read_text()
    render = args.work / "phase_interpolator-layout.png"
    simulation = json.loads(args.simulation.read_text())
    physical = {
        "drc_error_count": (int(match.group(1)) if (match := re.search(
            r"\[INFO\] COUNT:\s*(\d+)", drc)) else -1),
        "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": digest(pex_path),
        "layout_image_sha256": digest(render),
        "layout_source_sha256": digest(args.source / "phase_interpolator/layout.tcl"),
        "schematic_source_sha256": digest(args.source / "phase_interpolator/phase_interpolator.spice"),
    }
    physical_pass = (physical["drc_error_count"] == 0 and physical["lvs_unique"]
                     and physical["pex_resistor_count"] >= 300
                     and physical["pex_capacitor_count"] >= 100
                     and render.stat().st_size >= 10_000)
    physical["result"] = "pass" if physical_pass else "fail"
    passed = physical_pass and simulation.get("result") == "pass"
    result = {
        "schema_version": 1,
        "claim": "physical_two_input_break_before_make_vco_selector",
        "reused_macro": "phase_interpolator",
        "physical": physical,
        "extracted_selector": simulation,
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"selector physical+extracted: physical={physical['result']}; "
          f"simulation={simulation.get('result')}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
