#!/usr/bin/env python3
"""Record extracted identity for the active Wi-Fi RF NFET-array coupon.

This runner proves that the measured transistor structure is physically the
same 16-finger NFET array used by the Wi-Fi LNA.  It does not simulate S
parameters or infer an RF model from lumped PEX; that would defeat the purpose
of the wafer-characterization obligation.
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
    subckt = re.search(r"^\.subckt\s+wifi_rf_nfet_array_coupon_pex\s+(.+)$", pex,
                       re.MULTILINE)
    ports = set(subckt.group(1).split()) if subckt else set()
    devices = re.findall(
        r"^X\d+\s+\S+\s+\S+\s+\S+\s+\S+\s+nfet_03v3\s+"
        r"[^\n]*\bw=4u\s+l=0\.28u$", pex, re.MULTILINE)
    result = {
        "schema_version": 1,
        "claim": "wifi_2p4g_lna_nfet_array_extracted_identity",
        "result": "pass" if ports == {"GATE", "DRAIN", "SOURCE", "VSS"}
        and len(devices) == 16 else "fail",
        "pex_ports": sorted(ports),
        "nfet_03v3_4u_028u_count": len(devices),
        "pex_resistor_count": len(re.findall(r"^R\d+\s", pex, re.MULTILINE)),
        "pex_capacitor_count": len(re.findall(r"^C\d+\s", pex, re.MULTILINE)),
        "measurement_status": (
            "full-RC extracted active-device identity only; calibrated wafer S-parameters "
            "and RF compact-model review remain required"
        ),
        "not_claimed": [
            "rf_compact_model_validity", "noise_parameters", "ft_fmax", "linearity",
            "probe_pad_package_qualification", "silicon_measurement",
            "wifi_receiver_performance",
        ],
        "source_sha256": digest(args.source / "rf_nfet_array_coupon.spice"),
        "layout_sha256": digest(args.source / "layout.tcl"),
        "test_plan_sha256": digest(args.source / "test_plan.json"),
        "runner_sha256": digest(Path(__file__)),
        "pex_sha256": digest(args.pex),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("wifi RF NFET-array coupon extracted identity: "
          f"{result['result']}; {len(devices)} devices; "
          f"{result['pex_resistor_count']}R/{result['pex_capacitor_count']}C; "
          "silicon RF measurement remains required")
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
