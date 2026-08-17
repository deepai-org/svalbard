#!/usr/bin/env python3
"""Enforce phase-interpolator schematic, extracted, physical, and stress evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("schematic-pvt", "extracted-pvt", "robustness", "drc", "lvs",
                 "pex", "render", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    schematic = load(args.schematic_pvt)
    extracted = load(args.extracted_pvt)
    robustness = load(args.robustness)
    pex_text = args.pex.read_text()
    resistor_count = len(re.findall(r"^R\d+\s", pex_text, re.MULTILINE))
    capacitor_count = len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE))
    checks = {
        "schematic.calibrated_pvt": (schematic.get("result") == "pass"
                                     and schematic.get("case_count") == 7533
                                     and schematic.get("passing_group_count") == 243),
        "extracted.calibrated_pvt": (extracted.get("result") == "pass"
                                     and extracted.get("case_count") == 7533
                                     and extracted.get("passing_group_count") == 243),
        "extracted.robustness": (robustness.get("result") == "pass"
                                 and robustness.get("case_count") == 279
                                 and robustness.get("passing_group_count") == 9),
        "magic.drc_zero": "[INFO] COUNT: 0" in args.drc.read_text(),
        "netgen.lvs_unique": "Final result: Circuits match uniquely." in args.lvs.read_text(),
        "pex.full_rc": (".subckt phase_interpolator_pex" in pex_text
                        and "extresist threshold=0 mOhm" in pex_text
                        and resistor_count >= 300 and capacitor_count >= 100),
        "layout.rendered": args.render.stat().st_size >= 10_000,
    }
    groups = extracted["groups"]
    selected_codes = [code for group in groups for code in group["observed"]["selected_codes"]]
    cases = [case["observed"] for case in extracted["cases"]]
    passed = all(checks.values())
    result = {
        "schema_version": 1, "result": "pass" if passed else "fail",
        "qualification": "experimental pre-silicon GF180 public-model evidence only",
        "checks": checks,
        "pex": {"mode": "full_rc_coupled", "resistor_count": resistor_count,
                "capacitor_count": capacitor_count},
        "observed": {
            "extracted_phase_span_s": [min(group["observed"]["span_s"] for group in groups),
                                        max(group["observed"]["span_s"] for group in groups)],
            "extracted_maximum_phase_error_s": max(
                group["observed"]["maximum_phase_error_s"] for group in groups),
            "extracted_selected_code_range": [min(selected_codes), max(selected_codes)],
            "extracted_output_swing_v": [min(min(case["diff_high"], -case["diff_low"])
                                               for case in cases),
                                         max(max(case["diff_high"], -case["diff_low"])
                                               for case in cases)],
            "extracted_supply_current_a": [min(case["supply_current"] for case in cases),
                                            max(case["supply_current"] for case in cases)],
        },
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not passed:
        raise SystemExit("phase_interpolator checks failed: "
                         + ", ".join(name for name, value in checks.items() if not value))
    print("phase_interpolator schematic/layout/PEX checks: PASS")


if __name__ == "__main__":
    main()
