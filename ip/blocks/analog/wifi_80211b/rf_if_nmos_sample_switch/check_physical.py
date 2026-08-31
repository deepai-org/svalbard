#!/usr/bin/env python3
"""Fail closed on physical closure of the Wi-Fi NMOS sampling-switch probe."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("source", "drc", "lvs", "pex", "gds", "render", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    count = re.search(r"\[INFO\] COUNT:\s*(\d+)", args.drc.read_text())
    pex = args.pex.read_text()
    result = {
        "schema_version": 1,
        "claim": "wifi_real_if_differential_nmos_sampling_switch_physical_probe",
        "drc_error_count": int(count.group(1)) if count else -1,
        "lvs_unique": args.lvs.read_text().count(
            "Final result: Circuits match uniquely.") == 1,
        "nfet_03v3_4u_028u_count": len(re.findall(
            r"^X\d+\s+\S+\s+\S+\s+\S+\s+\S+\s+nfet_03v3\s+"
            r"[^\n]*\bw=4u\s+l=0\.28u$", pex, re.MULTILINE)),
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "pex_sha256": digest(args.pex),
        "gds_sha256": digest(args.gds),
        "layout_image_sha256": digest(args.render),
        "layout_source_sha256": digest(args.source / "layout.tcl"),
        "schematic_source_sha256": digest(args.source / "rf_if_nmos_sample_switch.spice"),
        "checker_source_sha256": digest(Path(__file__)),
    }
    result["result"] = "pass" if (
        result["drc_error_count"] == 0 and result["lvs_unique"]
        and result["nfet_03v3_4u_028u_count"] == 16
        and result["pex_resistor_count"] >= 2
        and result["pex_capacitor_count"] >= 4
        and Path(args.render).stat().st_size > 10_000
    ) else "fail"
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("Wi-Fi IF NMOS sample-switch physical: "
          f"DRC={result['drc_error_count']} LVS={result['lvs_unique']} "
          f"devices={result['nfet_03v3_4u_028u_count']} "
          f"PEX={result['pex_resistor_count']}R/{result['pex_capacitor_count']}C")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
