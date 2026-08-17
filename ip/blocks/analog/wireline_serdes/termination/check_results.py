#!/usr/bin/env python3
"""Enforce schematic, extracted, DRC, LVS, PEX, and render evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("prelayout", "extracted", "linearity", "drc", "lvs", "pex", "render", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    prelayout = json.loads(args.prelayout.read_text())
    extracted = json.loads(args.extracted.read_text())
    linearity = json.loads(args.linearity.read_text())
    pex_text = args.pex.read_text()
    resistor_count = len(re.findall(r"^R\d+\s", pex_text, re.MULTILINE))
    capacitor_count = len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE))
    checks = {
        "prelayout.full_pvt": prelayout.get("result") == "pass" and prelayout.get("case_count") == 1944,
        "extracted.full_pvt": extracted.get("result") == "pass" and extracted.get("case_count") == 1944,
        "extracted.linearity": linearity.get("result") == "pass" and linearity.get("case_count") == 243,
        "magic.drc_zero": "[INFO] COUNT: 0" in args.drc.read_text(),
        "netgen.lvs_unique": "Final result: Circuits match uniquely." in args.lvs.read_text(),
        "pex.full_rc": ".subckt serdes_termination_pex" in pex_text
                           and "extresist threshold=0 mOhm" in pex_text
                           and resistor_count >= 100 and capacitor_count >= 1,
        "layout.rendered": args.render.stat().st_size >= 10_000,
    }
    calibrated = [entry["selected_case"] for entry in extracted["calibrated_groups"]]
    z25 = [float(entry["observed"]["zmag_2p5g"]) for entry in calibrated]
    z50 = [float(entry["observed"]["zmag_5g"]) for entry in calibrated]
    spreads = [float(entry["relative_spread"]) for entry in linearity["cases"]]
    passed = all(checks.values())
    result = {
        "schema_version": 1,
        "result": "pass" if passed else "fail",
        "qualification": "experimental pre-silicon GF180 public-model evidence only",
        "checks": checks,
        "pex": {"mode": "full_rc_coupled", "resistor_count": resistor_count,
                "capacitor_count": capacitor_count},
        "observed": {"extracted_calibrated_zmag_2p5g_ohm": [min(z25), max(z25)],
                     "extracted_calibrated_zmag_5g_ohm": [min(z50), max(z50)],
                     "maximum_large_signal_resistance_spread": max(spreads)},
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not passed:
        raise SystemExit("termination checks failed: " + ", ".join(k for k, v in checks.items() if not v))
    print("serdes_termination schematic/layout/PEX checks: PASS")


if __name__ == "__main__":
    main()
