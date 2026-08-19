#!/usr/bin/env python3
"""Check physical legality and extracted endpoint coverage of VCO margin tiles."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


LIMITS = {
    "margin_slow": ("at_or_below", 2.45e9, 1),
    "margin_fast": ("at_or_above", 2.55e9, 2),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    members: dict[str, object] = {}
    passed = True
    for name, (direction, limit_hz, minimum_codes) in LIMITS.items():
        cell = f"cml_vco_delay_{name}"
        drc_path = args.work / f"{cell}-drc.rpt"
        lvs_path = args.work / f"{cell}-lvs.out"
        pex_path = args.work / f"{cell}.pex.spice"
        screen_path = args.work / f"{name.replace('margin_', 'margin-')}-ring.json"
        drc = drc_path.read_text()
        lvs = lvs_path.read_text()
        pex = pex_path.read_text()
        screen = json.loads(screen_path.read_text())
        group = screen["groups"][0]
        clean = "[INFO] COUNT: 0" in drc
        unique = ("Netlists match uniquely." in lvs
                  and "Final result: Circuits match uniquely." in lvs)
        resistors = len(re.findall(r"^R\d+ ", pex, re.MULTILINE))
        capacitors = len(re.findall(r"^C\d+ ", pex, re.MULTILINE))
        valid_codes = int(group["valid_control_count"])
        endpoint_hz = (float(group["minimum_hz"]) if direction == "at_or_below"
                       else float(group["maximum_hz"]))
        endpoint_pass = (endpoint_hz <= limit_hz if direction == "at_or_below"
                         else endpoint_hz >= limit_hz)
        member_pass = (clean and unique and resistors > 0 and capacitors > 0
                       and screen.get("case_count") == 6
                       and screen.get("output_buffer") == "full_delay_tile"
                       and valid_codes >= minimum_codes and endpoint_pass)
        passed &= member_pass
        members[name] = {
            "result": "pass" if member_pass else "fail",
            "drc_error_count": 0 if clean else None,
            "lvs_unique": unique,
            "pex_resistor_count": resistors,
            "pex_capacitor_count": capacitors,
            "pex_sha256": digest(pex_path),
            "valid_control_count": valid_codes,
            "minimum_hz": group["minimum_hz"],
            "maximum_hz": group["maximum_hz"],
            "endpoint_limit_hz": limit_hz,
            "endpoint_direction": direction,
            "screen_sha256": digest(screen_path),
        }

    result = {
        "schema_version": 1,
        "cell_family": "cml_vco_delay_margin_tiles",
        "environment": ["ss", "res_ss", 2.97, 125],
        "guardband_hz": [2.45e9, 2.55e9],
        "result": "pass" if passed else "fail",
        "members": members,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("VCO margin physical: " + ", ".join(
        f"{name}={member['result']}" for name, member in members.items()))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
