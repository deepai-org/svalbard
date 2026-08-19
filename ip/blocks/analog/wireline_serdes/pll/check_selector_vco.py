#!/usr/bin/env python3
"""Bind two-VCO selector composition to fresh physical extractions."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical(drc: Path, lvs: Path, pex: Path) -> dict[str, object]:
    drc_text, lvs_text, pex_text = drc.read_text(), lvs.read_text(), pex.read_text()
    match = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc_text)
    record = {
        "drc_error_count": int(match.group(1)) if match else -1,
        "lvs_unique": lvs_text.count("Final result: Circuits match uniquely.") == 1,
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex_text, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE)),
        "pex_sha256": digest(pex),
    }
    passed = (record["drc_error_count"] == 0 and record["lvs_unique"]
              and record["pex_resistor_count"] > 0 and record["pex_capacitor_count"] > 0)
    record["result"] = "pass" if passed else "fail"
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--simulation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cells = {
        "vco_delay": physical(args.work / "vco-drc.rpt", args.work / "vco-lvs.out",
                              args.work / "cml_vco_delay.pex.spice"),
        "startup_assist": physical(args.work / "assist-drc.rpt", args.work / "assist-lvs.out",
                                   args.work / "startup-assist.pex.spice"),
        "selector": physical(args.work / "selector-drc.rpt", args.work / "selector-lvs.out",
                             args.work / "phase_interpolator.pex.spice"),
    }
    simulation = json.loads(args.simulation.read_text())
    passed = all(cell["result"] == "pass" for cell in cells.values()) and simulation.get("result") == "pass"
    result = {"schema_version": 1, "claim": "physical_two_vco_selector_composition",
              "physical": cells, "simulation": simulation,
              "result": "pass" if passed else "fail"}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"physical two-VCO selector: cells="
          f"{sum(cell['result'] == 'pass' for cell in cells.values())}/{len(cells)}; "
          f"simulation={simulation.get('result')}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
