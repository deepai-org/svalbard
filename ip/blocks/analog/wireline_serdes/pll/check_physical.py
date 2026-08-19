#!/usr/bin/env python3
"""Fail closed on structural closure and nominal extracted-ring evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--lvs", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--nominal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    drc = args.drc.read_text()
    lvs = args.lvs.read_text()
    pex = args.pex.read_text()
    nominal = json.loads(args.nominal.read_text())
    resistor_count = len(re.findall(r"^R\d+ ", pex, re.MULTILINE))
    capacitor_count = len(re.findall(r"^C\d+ ", pex, re.MULTILINE))
    groups = nominal.get("groups", [])
    passed = ("[INFO] COUNT: 0" in drc
              and "Netlists match uniquely." in lvs
              and "Final result: Circuits match uniquely." in lvs
              and ".subckt cml_vco_delay_pex INP INN OUTP OUTN VCTRL VDD VSS" in pex
              and resistor_count > 0 and capacitor_count > 0
              and args.render.stat().st_size > 10000
              and nominal.get("result") == "pass"
              and nominal.get("case_count") == 7
              and nominal.get("passing_case_count") == 7
              and len(groups) == 1 and bool(groups[0].get("target_brackets_v")))
    result = {
        "schema_version": 1,
        "cell": "cml_vco_delay",
        "result": "pass" if passed else "fail",
        "layout_bbox_um": [54.0, 56.0],
        "drc_error_count": 0 if "[INFO] COUNT: 0" in drc else None,
        "lvs_unique": ("Netlists match uniquely." in lvs
                       and "Final result: Circuits match uniquely." in lvs),
        "pex_resistor_count": resistor_count,
        "pex_capacitor_count": capacitor_count,
        "pex_sha256": sha256(args.pex),
        "layout_image_sha256": sha256(args.render),
        "nominal_ring_result_sha256": sha256(args.nominal),
        "nominal_case_count": nominal.get("case_count"),
        "nominal_passing_case_count": nominal.get("passing_case_count"),
        "nominal_frequency_range_hz": [groups[0].get("minimum_hz"), groups[0].get("maximum_hz")],
        "nominal_target_brackets_v": groups[0].get("target_brackets_v"),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
