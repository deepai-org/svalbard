#!/usr/bin/env python3
"""Enforce phase-error combiner schematic, extracted, and physical evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("schematic", "extracted", "drc", "lvs", "pex", "gds", "render", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    schematic = json.loads(args.schematic.read_text())
    extracted = json.loads(args.extracted.read_text())
    pex_text = args.pex.read_text()
    resistor_count = len(re.findall(r"^R\d+\s", pex_text, re.MULTILINE))
    capacitor_count = len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE))
    checks = {
        "schematic.calibrated_pvt": (schematic.get("result") == "pass"
                                      and schematic.get("case_count") == 108
                                      and schematic.get("passing_group_count") == 9),
        "extracted.calibrated_pvt": (extracted.get("result") == "pass"
                                      and extracted.get("case_count") == 108
                                      and extracted.get("passing_group_count") == 9),
        "magic.drc_zero": "[INFO] COUNT: 0" in args.drc.read_text(),
        "netgen.lvs_unique": "Final result: Circuits match uniquely." in args.lvs.read_text(),
        "pex.full_rc": (".subckt cml_phase_error_filter_pex" in pex_text
                        and "extresist threshold=0 mOhm" in pex_text
                        and resistor_count >= 100 and capacitor_count >= 50),
        "layout.rendered": args.render.stat().st_size >= 10_000,
    }
    selected = [case for group in extracted["groups"] for case in extracted["cases"]
                if case["environment"] == group["environment"]
                and case["bias_v"] == group["selected_bias_v"]]
    result = {
        "schema_version": 1,
        "result": "pass" if all(checks.values()) else "fail",
        "qualification": "experimental pre-silicon GF180 public-model evidence only",
        "checks": checks,
        "layout_sha256": hashlib.sha256(args.gds.read_bytes()).hexdigest(),
        "pex": {"mode": "full_rc_coupled", "resistor_count": resistor_count,
                "capacitor_count": capacitor_count,
                "sha256": hashlib.sha256(args.pex.read_bytes()).hexdigest()},
        "observed": {
            "selected_bias_v": [min(case["bias_v"] for case in selected),
                                max(case["bias_v"] for case in selected)],
            "selected_one_error_margin_v": [min(case["one_error_margin_v"] for case in selected),
                                             max(case["one_error_margin_v"] for case in selected)],
            "selected_two_error_margin_v": [min(case["two_error_margin_v"] for case in selected),
                                             max(case["two_error_margin_v"] for case in selected)],
            "selected_neutral_error_v_max": max(case["neutral_error_v"] for case in selected),
        },
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if result["result"] != "pass":
        raise SystemExit("phase-error checks failed: "
                         + ", ".join(name for name, passed in checks.items() if not passed))
    print("cml_phase_error_filter schematic/layout/PEX checks: PASS")


if __name__ == "__main__":
    main()
