#!/usr/bin/env python3
"""Enforce phase-detector schematic, extracted, physical, and stress evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("schematic-pvt", "extracted-pvt", "stress", "drc", "lvs",
                 "pex", "render", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    schematic = load(args.schematic_pvt)
    extracted = load(args.extracted_pvt)
    stress = load(args.stress)
    pex_text = args.pex.read_text()
    resistor_count = len(re.findall(r"^R\d+\s", pex_text, re.MULTILINE))
    capacitor_count = len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE))
    checks = {
        "schematic.calibrated_pvt": (schematic.get("result") == "pass"
                                     and schematic.get("case_count") == 3645
                                     and schematic.get("passing_group_count") == 243
                                     and schematic.get("symbol_rate_hz") == 1.25e9),
        "extracted.calibrated_pvt": (extracted.get("result") == "pass"
                                     and extracted.get("case_count") == 3645
                                     and extracted.get("passing_group_count") == 243
                                     and extracted.get("symbol_rate_hz") == 1.25e9),
        "extracted.fixed_code_guardbands": (stress.get("result") == "pass"
                                             and stress.get("case_count") == 360
                                             and stress.get("complete_case_count") == 360
                                             and stress.get("design_passing_case_count") == 243),
        "magic.drc_zero": "[INFO] COUNT: 0" in args.drc.read_text(),
        "netgen.lvs_unique": "Final result: Circuits match uniquely." in args.lvs.read_text(),
        "pex.full_rc": (".subckt cml_alexander_boundary_pex" in pex_text
                        and "extresist threshold=0 mOhm" in pex_text
                        and resistor_count >= 400 and capacitor_count >= 150),
        "layout.rendered": args.render.stat().st_size >= 10_000,
    }
    selected = [group["selected_case"] for group in extracted["groups"]]
    design = [case for case in stress["cases"] if case["classification"] == "design"]
    exploratory = [case for case in stress["cases"]
                   if case["classification"] == "exploratory"]
    passed = all(checks.values())
    result = {
        "schema_version": 1,
        "result": "pass" if passed else "fail",
        "qualification": "experimental pre-silicon GF180 public-model evidence only",
        "checks": checks,
        "pex": {"mode": "full_rc_coupled", "resistor_count": resistor_count,
                "capacitor_count": capacitor_count},
        "observed": {
            "extracted_selected_margin_v": [
                min(min(case["early_margin_v"], case["late_margin_v"]) for case in selected),
                max(min(case["early_margin_v"], case["late_margin_v"]) for case in selected),
            ],
            "extracted_selected_bias_v": [min(case["bias_v"] for case in selected),
                                           max(case["bias_v"] for case in selected)],
            "design_guardband_margin_v": [min(case["minimum_signed_margin_v"] for case in design),
                                            max(case["minimum_signed_margin_v"] for case in design)],
            "exploratory_passing_cases": sum(case["result"] == "pass"
                                               for case in exploratory),
            "exploratory_case_count": len(exploratory),
        },
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not passed:
        raise SystemExit("phase-detector checks failed: "
                         + ", ".join(name for name, value in checks.items() if not value))
    print("cml_alexander_boundary schematic/layout/PEX checks: PASS")


if __name__ == "__main__":
    main()
