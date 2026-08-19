#!/usr/bin/env python3
"""Bind physical startup-assist and composed extracted simulation evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

VARIANTS = (
    "center", "slow", "fast", "ss_ff_margin_slow",
    "ss_ff_margin_fast", "margin_slow", "margin_fast",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical_record(drc: Path, lvs: Path, pex: Path) -> dict[str, object]:
    drc_text = drc.read_text()
    lvs_text = lvs.read_text()
    pex_text = pex.read_text()
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc_text)
    drc_errors = int(count.group(1)) if count else -1
    unique = lvs_text.count("Final result: Circuits match uniquely.") == 1
    resistors = len(re.findall(r"^R\d+\s", pex_text, re.MULTILINE))
    capacitors = len(re.findall(r"^C\d+\s", pex_text, re.MULTILINE))
    passed = drc_errors == 0 and unique and resistors > 0 and capacitors > 0
    return {
        "drc_error_count": drc_errors,
        "lvs_unique": unique,
        "pex_resistor_count": resistors,
        "pex_capacitor_count": capacitors,
        "pex_sha256": digest(pex),
        "result": "pass" if passed else "fail",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--simulation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    assist = physical_record(
        args.work / "startup-assist-drc.rpt",
        args.work / "startup-assist-lvs.out",
        args.work / "startup-assist.pex.spice",
    )
    render = args.work / "cml_vco_startup_assist-layout.png"
    assist["layout_image_sha256"] = digest(render)
    assist["layout_image_bytes"] = render.stat().st_size
    assist["layout_source_sha256"] = digest(args.source / "startup_assist_layout.tcl")
    assist["schematic_source_sha256"] = digest(args.source / "startup_assist.spice")
    if assist["layout_image_bytes"] < 10_000:
        assist["result"] = "fail"

    tiles = {}
    for variant in VARIANTS:
        cell = "cml_vco_delay" if variant == "center" else f"cml_vco_delay_{variant}"
        tiles[variant] = physical_record(
            args.work / f"{cell}-drc.rpt",
            args.work / f"{cell}-lvs.out",
            args.work / f"{cell}.pex.spice",
        )

    simulation = json.loads(args.simulation.read_text())
    passed = (assist["result"] == "pass"
              and all(record["result"] == "pass" for record in tiles.values())
              and simulation.get("result") == "pass")
    result = {
        "schema_version": 1,
        "claim": "physical_deterministic_vco_startup_assist",
        "assist_physical": assist,
        "tile_physical": tiles,
        "composed_extracted_startup": simulation,
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"startup physical+composed: assist={assist['result']}; "
          f"tiles={sum(record['result'] == 'pass' for record in tiles.values())}/{len(tiles)}; "
          f"simulation={simulation.get('result')}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
