#!/usr/bin/env python3
"""Enforce receiver schematic, extracted, physical, and noise evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("schematic-ac", "schematic-threshold", "schematic-transient",
                 "extracted-ac", "extracted-threshold", "extracted-transient",
                 "noise", "drc", "lvs", "pex", "render", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    sac, sth, strn = load(args.schematic_ac), load(args.schematic_threshold), load(args.schematic_transient)
    eac, eth, etrn, noise = (load(args.extracted_ac), load(args.extracted_threshold),
                             load(args.extracted_transient), load(args.noise))
    pex_text = args.pex.read_text()
    resistor_count = len(re.findall(r"^R\d+\s", pex_text, re.MULTILINE))
    capacitor_count = len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE))
    checks = {
        "schematic.ac_pvt": sac.get("result") == "pass" and sac.get("case_count") == 3402,
        "schematic.threshold_pvt": sth.get("result") == "pass" and sth.get("group_count") == 486,
        "schematic.transient_pvt": strn.get("result") == "pass" and strn.get("case_count") == 486,
        "extracted.ac_pvt": eac.get("result") == "pass" and eac.get("case_count") == 3402,
        "extracted.threshold_pvt": eth.get("result") == "pass" and eth.get("group_count") == 486,
        "extracted.transient_pvt": etrn.get("result") == "pass" and etrn.get("case_count") == 486,
        "extracted.noise": noise.get("result") == "pass" and noise.get("case_count") == 2,
        "magic.drc_zero": "[INFO] COUNT: 0" in args.drc.read_text(),
        "netgen.lvs_unique": "Final result: Circuits match uniquely." in args.lvs.read_text(),
        "pex.full_rc": ".subckt serdes_rx_pex" in pex_text
                           and "extresist threshold=0 mOhm" in pex_text
                           and resistor_count >= 400 and capacitor_count >= 100,
        "layout.rendered": args.render.stat().st_size >= 10_000,
    }
    selected = [entry["selected_case"] for entry in eac["calibrated_groups"]]
    low, high = ([case for case in selected if not case["high_bandwidth"]],
                 [case for case in selected if case["high_bandwidth"]])
    transients = [case["observed"] for case in etrn["cases"]]
    threshold_trips = [values["trip_input"] for group in eth["groups"]
                       for values in group["observed"].values()]
    input_noise = [case["observed"]["inoise_total"] for case in noise["cases"]]
    passed = all(checks.values())
    result = {
        "schema_version": 1, "result": "pass" if passed else "fail",
        "qualification": "experimental pre-silicon GF180 public-model evidence only",
        "checks": checks,
        "pex": {"mode": "full_rc_coupled", "resistor_count": resistor_count,
                "capacitor_count": capacitor_count},
        "observed": {
            "extracted_low_bw_hz": [min(c["observed"]["bandwidth"] for c in low),
                                     max(c["observed"]["bandwidth"] for c in low)],
            "extracted_high_bw_hz": [min(c["observed"]["bandwidth"] for c in high),
                                      max(c["observed"]["bandwidth"] for c in high)],
            "extracted_max_delay_s": max(max(x["delay_rise"], x["delay_fall"]) for x in transients),
            "extracted_min_output_magnitude_v": min(min(x["diff_high"], -x["diff_low"])
                                                     for x in transients),
            "extracted_threshold_trip_range_v": [min(threshold_trips), max(threshold_trips)],
            "nominal_input_referred_noise_v_rms": [min(input_noise), max(input_noise)],
        },
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not passed:
        raise SystemExit("serdes_rx checks failed: " + ", ".join(k for k, v in checks.items() if not v))
    print("serdes_rx schematic/layout/PEX checks: PASS")


if __name__ == "__main__":
    main()
