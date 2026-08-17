#!/usr/bin/env python3
"""Enforce electrical, DRC, LVS, and extraction limits for serdes_tx."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

MEASURE = re.compile(
    r"^(diff_high|diff_low|supply_current_avg|output_floor|output_floor_n|"
    r"diff_rise|diff_fall)\s*=\s*([-+0-9.eE]+)",
    re.MULTILINE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prelayout", required=True, type=Path)
    parser.add_argument("--postlayout", required=True, type=Path)
    parser.add_argument("--postlayout-1p25", required=True, type=Path)
    parser.add_argument("--drc", required=True, type=Path)
    parser.add_argument("--lvs", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--render", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def measurements(path: Path) -> dict[str, float]:
    found = {name: float(value) for name, value in MEASURE.findall(path.read_text())}
    required = {
        "diff_high",
        "diff_low",
        "supply_current_avg",
        "output_floor",
        "output_floor_n",
        "diff_rise",
        "diff_fall",
    }
    missing = required - found.keys()
    if missing:
        raise ValueError(f"{path} lacks measurements: {sorted(missing)}")
    return found


def main() -> None:
    args = parse_args()
    stages = {
        "prelayout": measurements(args.prelayout),
        "postlayout": measurements(args.postlayout),
        "postlayout_1p25": measurements(args.postlayout_1p25),
    }
    checks: dict[str, bool] = {}
    for stage, values in stages.items():
        checks[f"{stage}.finite"] = all(math.isfinite(value) for value in values.values())
        checks[f"{stage}.diff_high"] = values["diff_high"] <= -0.38
        checks[f"{stage}.diff_low"] = values["diff_low"] >= 0.38
        checks[f"{stage}.symmetry"] = (
            abs(abs(values["diff_high"]) - abs(values["diff_low"])) <= 0.005
        )
        checks[f"{stage}.supply_current"] = 0.0035 <= values["supply_current_avg"] <= 0.0048
        checks[f"{stage}.output_floor"] = min(
            values["output_floor"], values["output_floor_n"]
        ) >= 2.30
        checks[f"{stage}.crossing_time"] = max(
            values["diff_rise"], values["diff_fall"]
        ) <= 60e-12

    checks["postlayout.swing_retention"] = (
        abs(stages["postlayout"]["diff_high"])
        / abs(stages["prelayout"]["diff_high"])
        >= 0.80
    )
    drc_text = args.drc.read_text()
    checks["magic.drc_zero"] = "[INFO] COUNT: 0" in drc_text
    lvs_text = args.lvs.read_text()
    checks["netgen.lvs_unique"] = (
        "Final result: Circuits match uniquely." in lvs_text
        and "Property errors were found" not in lvs_text
    )
    pex_text = args.pex.read_text()
    checks["pex.coupling_capacitance"] = (
        ".subckt serdes_tx_pex" in pex_text
        and len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE)) >= 1
    )
    checks["layout.rendered"] = args.render.stat().st_size >= 10_000

    passed = all(checks.values())
    result = {
        "schema_version": 1,
        "result": "pass" if passed else "fail",
        "qualification": "experimental pre-silicon GF180 public-model evidence only",
        "rates_gt_s": [1.25, 2.5],
        "observed": stages,
        "checks": checks,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not passed:
        failed = [name for name, ok in checks.items() if not ok]
        raise SystemExit("serdes_tx checks failed: " + ", ".join(failed))
    print("serdes_tx transistor/layout/PEX checks: PASS")


if __name__ == "__main__":
    main()
