#!/usr/bin/env python3
"""Enforce schematic, physical, extracted, robustness, and aperture evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("schematic-pvt", "extracted-nominal", "extracted-pvt", "robustness",
                 "aperture", "supply-noise", "drc", "lvs", "pex", "render", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    schematic = load(args.schematic_pvt)
    nominal = load(args.extracted_nominal)
    extracted = load(args.extracted_pvt)
    robustness = load(args.robustness)
    aperture = load(args.aperture)
    supply_noise = load(args.supply_noise)
    pex_text = args.pex.read_text()
    resistor_count = len(re.findall(r"^R\d+\s", pex_text, re.MULTILINE))
    capacitor_count = len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE))
    checks = {
        "schematic.calibrated_pvt": (schematic.get("result") == "pass"
                                     and schematic.get("case_count") == 1701
                                     and schematic.get("passing_group_count") == 243),
        "magic.drc_zero": "[INFO] COUNT: 0" in args.drc.read_text(),
        "netgen.lvs_unique": "Final result: Circuits match uniquely." in args.lvs.read_text(),
        "pex.full_rc": (".subckt cdr_sampler_pex" in pex_text
                        and "extresist threshold=0 mOhm" in pex_text
                        and resistor_count >= 400 and capacitor_count >= 150),
        "extracted.nominal": (nominal.get("result") == "pass"
                              and nominal.get("case_count") == 7
                              and nominal.get("passing_case_count", 0) >= 3),
        "extracted.calibrated_pvt": (extracted.get("result") == "pass"
                                     and extracted.get("case_count") == 1701
                                     and extracted.get("passing_group_count") == 243
                                     and all(0.90 <= group["selected_case"]["bias_v"] <= 1.30
                                             and group["passing_bias_count"] >= 3
                                             for group in extracted["groups"])),
        "extracted.robustness": (robustness.get("result") == "pass"
                                 and robustness.get("case_count") == 720
                                 and robustness.get("passing_group_count") == 9
                                 and robustness.get("adversarial_case_count") == 270),
        "extracted.aperture": (aperture.get("result") == "pass"
                               and aperture.get("case_count") == 225
                               and aperture.get("passing_group_count") == 9
                               and aperture.get("required_shift_window_ps") == [-80, 80]),
        "extracted.supply_noise": (supply_noise.get("result") == "pass"
                                   and supply_noise.get("case_count") == 225
                                   and supply_noise.get("passing_group_count") == 9
                                   and supply_noise.get("qualified_ripple_peak_mv") == 50),
        "layout.rendered": args.render.stat().st_size >= 10_000,
    }
    selected = [group["selected_case"] for group in extracted["groups"]]
    selected_margins = [min(case["even_margin_v"], case["odd_margin_v"])
                        for case in selected]
    selected_currents = [case["observed"]["supply_current"] for case in selected]
    result = {
        "schema_version": 1, "result": "pass" if all(checks.values()) else "fail",
        "qualification": "experimental pre-silicon GF180 public-model evidence only",
        "checks": checks,
        "pex": {"mode": "full_rc_coupled", "resistor_count": resistor_count,
                "capacitor_count": capacitor_count},
        "observed": {
            "extracted_selected_decision_margin_v": [min(selected_margins),
                                                       max(selected_margins)],
            "extracted_selected_supply_current_a": [min(selected_currents),
                                                      max(selected_currents)],
            "aperture_qualified_shift_ps": aperture["required_shift_window_ps"],
            "aperture_common_passing_shift_ps": [
                max(group["minimum_passing_shift_ps"] for group in aperture["groups"]),
                min(group["maximum_passing_shift_ps"] for group in aperture["groups"]),
            ],
            "aperture_negative_boundary_censored": all(
                group["minimum_passing_shift_ps"] == -240
                for group in aperture["groups"]),
            "supply_noise_100mv_passing_cases":
                supply_noise["adversarial_100mv_passing_case_count"],
        },
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not all(checks.values()):
        raise SystemExit("cdr_sampler checks failed: "
                         + ", ".join(name for name, value in checks.items() if not value))
    print("cdr_sampler schematic/layout/PEX/timing checks: PASS")


if __name__ == "__main__":
    main()
