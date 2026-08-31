#!/usr/bin/env python3
"""Validate bounded, explicitly non-RF-qualified Wi-Fi OSTL coupon evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--physical", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    physical = json.loads(args.physical.read_text())
    require(physical.get("result") == "pass" and physical.get("drc_error_count") == 0
            and physical.get("lvs_unique")
            and physical.get("pex_sha256") == digest(args.pex),
            "RF OSTL coupon lacks physical closure")
    require(result.get("result") == "pass"
            and result.get("pex_ports") == ["LOAD", "OPEN", "VSS"]
            and len(result.get("poly_terminals", [])) == 3
            and result.get("pex_resistor_count", 0) >= 2
            and result.get("pex_capacitor_count", 0) >= 4,
            "RF OSTL coupon PEX topology changed")
    require(result.get("source_sha256") == digest(args.source / "rf_ostl_coupon.spice")
            and result.get("layout_sha256") == digest(args.source / "layout.tcl")
            and result.get("test_plan_sha256") == digest(args.source / "test_plan.json")
            and result.get("runner_sha256") == digest(args.source / "run_coupon.py")
            and result.get("pex_sha256") == digest(args.pex),
            "RF OSTL coupon identity changed")
    require({"calibrated_load_impedance", "rf_deembedding_validity",
             "pad_package_qualification", "silicon_measurement"}
            <= set(result.get("not_claimed", [])),
            "RF OSTL coupon made an unsound qualification claim")
    print("wifi RF OSTL coupon: PASS; physical closure plus extracted OTSC topology; "
          "RF/EM and silicon characterization remain explicit")


if __name__ == "__main__":
    main()
