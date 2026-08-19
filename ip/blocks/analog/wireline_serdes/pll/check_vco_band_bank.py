#!/usr/bin/env python3
"""Check a physical VCO-parent bank and bind it to range evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

VARIANTS = (
    "center", "fast", "ultra_fast", "slow", "high_gain", "ss_ff", "ss_ss",
    "margin_slow", "margin_fast", "typ_margin_slow", "ss_ff_margin_slow",
    "ss_ff_margin_fast",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--simulation", type=Path, required=True)
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS))
    parser.add_argument("--claim", default="twelve_complete_physical_vco_band_parents")
    parser.add_argument("--schematic-source", default="vco_band_variants.spice")
    parser.add_argument("--delay-schematic-source", default="physical_variants.spice")
    parser.add_argument(
        "--qualification", choices=("required_target", "design_guardband"),
        default="design_guardband",
    )
    args = parser.parse_args()
    variants = tuple(args.variants)
    simulation = json.loads(args.simulation.read_text())
    physical = {}
    for variant in variants:
        cell = f"cml_vco_band_{variant}"
        drc = (args.work / f"{cell}-drc.rpt").read_text()
        lvs = (args.work / f"{cell}-lvs.out").read_text()
        pex_path = args.work / f"{cell}.pex.spice"
        pex = pex_path.read_text()
        image_path = args.work / f"{cell}-layout.png"
        match = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
        record = {
            "drc_error_count": int(match.group(1)) if match else -1,
            "lvs_unique": lvs.count("Final result: Circuits match uniquely.") == 1,
            "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
            "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
            "pex_sha256": digest(pex_path),
            "layout_image_sha256": digest(image_path),
            "layout_image_bytes": image_path.stat().st_size,
        }
        passed = (
            record["drc_error_count"] == 0 and record["lvs_unique"]
            and record["pex_resistor_count"] >= 1000
            and record["pex_capacitor_count"] >= 280
            and record["layout_image_bytes"] >= 20_000
        )
        record["result"] = "pass" if passed else "fail"
        physical[variant] = record
    identities = {
        variant: physical[variant]["pex_sha256"]
        == simulation.get("band_pex_sha256", {}).get(variant)
        for variant in variants
    }
    required_target_pass = (
        simulation.get("target_environment_count")
        == len(simulation.get("environments", []))
    )
    design_guardband_pass = (
        simulation.get("guardband_environment_count")
        == len(simulation.get("environments", []))
    )
    electrical_pass = (
        required_target_pass if args.qualification == "required_target"
        else required_target_pass and design_guardband_pass
    )
    passed = (
        all(record["result"] == "pass" for record in physical.values())
        and all(identities.values())
        and electrical_pass
        and args.render.stat().st_size >= 100_000
    )
    result = {
        "schema_version": 1,
        "claim": args.claim,
        "member_count": len(variants),
        "physical": physical,
        "simulation": simulation,
        "pex_identity": identities,
        "qualification": args.qualification,
        "required_target_result": "pass" if required_target_pass else "fail",
        "design_guardband_result": "pass" if design_guardband_pass else "fail",
        "layout_source_sha256": digest(args.source / "vco_band_layout.tcl"),
        "schematic_source_sha256": digest(args.source / args.schematic_source),
        "delay_layout_source_sha256": digest(args.source / "layout.tcl"),
        "delay_schematic_source_sha256": digest(
            args.source / args.delay_schematic_source
        ),
        "startup_layout_source_sha256": digest(args.source / "startup_assist_layout.tcl"),
        "layout_index_sha256": digest(args.render),
        "layout_index_bytes": args.render.stat().st_size,
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"VCO-band bank closure: physical="
          f"{sum(r['result'] == 'pass' for r in physical.values())}/{len(variants)}; "
          f"required_target={'pass' if required_target_pass else 'fail'}; "
          f"design_guardband={'pass' if design_guardband_pass else 'fail'}; "
          f"identity={all(identities.values())}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
