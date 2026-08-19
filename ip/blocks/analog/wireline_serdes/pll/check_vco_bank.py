#!/usr/bin/env python3
"""Summarize physical closure and extracted PVT coverage of the VCO bank."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

VARIANTS = ("fast", "ultra_fast", "slow", "high_gain")
SCREENS = {
    "slow": "slow-ring.json",
    "fast": "fast-ring.json",
    "ultra_fast": "ultra-fast-ring.json",
    "high_gain": "high-gain-ring.json",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def env_key(group: dict[str, object]) -> str:
    return "/".join(str(value) for value in group["environment"])


def groups(screen: dict[str, object]) -> list[dict[str, object]]:
    if "groups" in screen:
        return screen["groups"]  # type: ignore[return-value]
    return [{
        "environment": entry["corner"],
        "minimum_hz": entry["frequency_range_hz"][0],
        "maximum_hz": entry["frequency_range_hz"][1],
        "valid_control_count": None,
        "target_brackets_v": ([{"source": "fixed_tile_extracted_screen"}]
                              if entry["target_covered"] else []),
    } for entry in screen["environments"]]  # type: ignore[index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    physical = {}
    structural_pass = True
    for variant in VARIANTS:
        cell = f"cml_vco_delay_{variant}"
        drc_path = args.work / f"{cell}-drc.rpt"
        lvs_path = args.work / f"{cell}-lvs.out"
        pex_path = args.work / f"{cell}.pex.spice"
        image_path = args.work / f"{cell}-layout.png"
        drc = drc_path.read_text()
        lvs = lvs_path.read_text()
        pex = pex_path.read_text()
        clean = "[INFO] COUNT: 0" in drc
        unique = ("Netlists match uniquely." in lvs and
                  "Final result: Circuits match uniquely." in lvs)
        resistors = len(re.findall(r"^R\d+ ", pex, re.MULTILINE))
        capacitors = len(re.findall(r"^C\d+ ", pex, re.MULTILINE))
        member_pass = clean and unique and resistors > 0 and capacitors > 0 and image_path.stat().st_size > 10000
        structural_pass &= member_pass
        physical[variant] = {
            "result": "pass" if member_pass else "fail",
            "drc_error_count": 0 if clean else None,
            "lvs_unique": unique,
            "pex_resistor_count": resistors,
            "pex_capacitor_count": capacitors,
            "pex_sha256": digest(pex_path),
            "layout_image_sha256": digest(image_path),
        }

    screens = {"center": json.loads((args.source / "extracted_pvt_screen.json").read_text())}
    screens.update({name: json.loads((args.work / filename).read_text())
                    for name, filename in SCREENS.items()})
    screen_integrity = all(
        screens[name].get("case_count") == 7
        and screens[name].get("passing_case_count") == 7
        and screens[name].get("output_buffer") == "full_delay_tile"
        for name in SCREENS
    )
    coverage: dict[str, dict[str, object]] = {}
    for member, screen in screens.items():
        for group in groups(screen):
            key = env_key(group)
            entry = coverage.setdefault(key, {"members": [], "covered_by": []})
            entry["members"].append({
                "member": member,
                "minimum_hz": group["minimum_hz"],
                "maximum_hz": group["maximum_hz"],
                "valid_control_count": group["valid_control_count"],
                "target_brackets_v": group["target_brackets_v"],
            })
            if group["target_brackets_v"]:
                entry["covered_by"].append(member)
    covered = sum(bool(entry["covered_by"]) for entry in coverage.values())
    evidence_pass = (structural_pass and screen_integrity
                     and len(coverage) == 5 and covered >= 3)
    result = {
        "schema_version": 1,
        "cell_family": "cml_vco_delay_bank",
        "physical_result": "pass" if structural_pass else "fail",
        "screen_integrity_result": "pass" if screen_integrity else "fail",
        "qualification_result": "partial" if evidence_pass and covered < len(coverage) else ("pass" if evidence_pass else "fail"),
        "covered_environment_count": covered,
        "environment_count": len(coverage),
        "uncovered_environments": [key for key, value in coverage.items() if not value["covered_by"]],
        "physical": physical,
        "coverage": coverage,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"vco bank: {len(physical)}/{len(VARIANTS)} physical; {covered}/{len(coverage)} environments")
    if not evidence_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
