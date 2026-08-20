#!/usr/bin/env python3
"""Bind integrated serializer/TX physical and changing-word evidence."""
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
    for name in ("drc", "lvs", "pex", "gds", "render", "rate1", "rate2", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    drc, lvs, pex = args.drc.read_text(), args.lvs.read_text(), args.pex.read_text()
    rate1, rate2 = json.loads(args.rate1.read_text()), json.loads(args.rate2.read_text())
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", drc)
    pex_hash = sha256(args.pex)
    resistor_count = len(re.findall(r"^R\d+\s", pex, re.MULTILINE))
    capacitor_count = len(re.findall(r"^C\d+\s", pex, re.MULTILINE))
    components = {
        "drc": int(count.group(1)) == 0 if count else False,
        "lvs": lvs.count("Final result: Circuits match uniquely.") == 1,
        "full_rc": resistor_count >= 500 and capacitor_count >= 100,
        "changing_word_1p25": rate1.get("result") == "pass"
        and rate1.get("extraction") == "full_rc"
        and rate1.get("serial_rate_hz") == 1.25e9
        and rate1.get("verification_case_count") == 35
        and rate1.get("pex_sha256") == pex_hash,
        "changing_word_2p5": rate2.get("result") == "pass"
        and rate2.get("extraction") == "full_rc"
        and rate2.get("serial_rate_hz") == 2.5e9
        and rate2.get("verification_case_count") == 35
        and rate2.get("pex_sha256") == pex_hash,
    }
    passed = all(components.values()) and args.render.stat().st_size > 10_000
    result = {
        "schema_version": 1,
        "claim": "physical_integrated_half_rate_serializer_tx",
        "component_results": components,
        "drc_error_count": int(count.group(1)) if count else -1,
        "lvs_unique": components["lvs"],
        "pex_resistor_count": resistor_count,
        "pex_capacitor_count": capacitor_count,
        "pex_sha256": pex_hash, "gds_sha256": sha256(args.gds),
        "layout_image_sha256": sha256(args.render),
        "layout_source_sha256": sha256(args.source / "serializer" / "integrated_tx_layout.tcl"),
        "schematic_source_sha256": sha256(args.source / "serializer" / "serializer_tx.spice"),
        "rate1_evidence_sha256": sha256(args.rate1),
        "rate2_evidence_sha256": sha256(args.rate2),
        "checker_source_sha256": sha256(Path(__file__)),
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"Integrated serializer/TX physical: DRC={result['drc_error_count']}; "
          f"LVS={result['lvs_unique']}; PEX={resistor_count}R/{capacitor_count}C; "
          f"rates={rate1.get('result')}/{rate2.get('result')}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
