#!/usr/bin/env python3
"""Record the extracted topology of the Wi-Fi die-side OSTL coupon.

The coupon exists to obtain silicon S-parameter and de-embedding evidence.
GF180's available lumped PEX cannot qualify its RF behavior, and the PDK's
three-terminal poly resistor retains an explicitly floating body.  This runner
therefore proves the exact PEX topology and fails if a future flow quietly
removes a required standard; it deliberately does not fabricate an RF result.
"""
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
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    pex = args.pex.read_text()
    subckt = re.search(r"^\.subckt\s+wifi_rf_ostl_coupon_pex\s+(.+)$", pex,
                       re.MULTILINE)
    poly = re.search(r"^X\d+\s+(\S+)\s+(\S+)\s+(\S+)\s+ppolyf_u\s+"
                     r"r_width=2u\s+r_length=40u$", pex, re.MULTILINE)
    expected_ports = {"VSS", "OPEN", "LOAD"}
    ports = set(subckt.group(1).split()) if subckt else set()
    result = {
        "schema_version": 1,
        "claim": "wifi_2p4g_die_side_ostl_coupon_extracted_structure",
        "result": "pass" if subckt and ports == expected_ports and poly else "fail",
        "pex_ports": sorted(ports),
        "poly_terminals": list(poly.groups()) if poly else [],
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "measurement_status": (
            "full-RC extracted topology only; wafer S-parameters, OTSC de-embedding, "
            "and model-validity review remain required"
        ),
        "floating_body_status": (
            "the PDK P+ poly model keeps its third terminal as an extracted local "
            "body node; no pre-silicon impedance qualification is claimed"
        ),
        "not_claimed": [
            "calibrated_load_impedance", "rf_deembedding_validity",
            "pad_package_qualification", "silicon_measurement",
            "wifi_receiver_performance",
        ],
        "source_sha256": digest(args.source / "rf_ostl_coupon.spice"),
        "layout_sha256": digest(args.source / "layout.tcl"),
        "test_plan_sha256": digest(args.source / "test_plan.json"),
        "runner_sha256": digest(Path(__file__)),
        "pex_sha256": digest(args.pex),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("wifi RF OSTL coupon extracted structure: "
          f"{result['result']}; {result['pex_resistor_count']}R/"
          f"{result['pex_capacitor_count']}C; silicon RF measurement remains required")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
