#!/usr/bin/env python3
"""Fail closed on the full-RC external-passive Wi-Fi LNA/mixer parent."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


EXPECTED_ENVIRONMENTS = {
    "tt": ("typical", 3.30, 27),
    "ff_cold": ("ff", 3.63, -40),
    "ff_hot": ("ff", 2.97, 125),
    "ss_hot": ("ss", 2.97, 125),
    "ss_cold": ("ss", 3.63, -40),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
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
    require(physical.get("result") == "pass"
            and physical.get("drc_error_count") == 0
            and physical.get("lvs_unique") is True
            and physical.get("pex_resistor_count", 0) >= 200
            and physical.get("pex_capacitor_count", 0) >= 150
            and physical.get("pex_sha256") == digest(args.pex),
            "routed Wi-Fi parent lacks physical closure")
    expected_sources = {
        "parent": digest(args.source / "rf_rx_external_lo_parent.spice"),
        "lna": digest(args.source.parent / "rf_lna" / "lna_cs_core.spice"),
        "mixer": digest(args.source.parent / "rf_switch_mixer" / "mixer.spice"),
    }
    require(result.get("result") == "pass"
            and result.get("case_count") == 5
            and result.get("passing_case_count") == 5
            and result.get("claim") ==
            "wifi_2p4g_lna_external_lo_mixer_routed_parent_full_rc_screen"
            and result.get("rf_hz") == 2.4e9
            and result.get("external_lo_hz") == 2.3e9
            and result.get("intermediate_frequency_hz") == 100e6
            and result.get("external_common_lna_bias_v") == 1.5
            and result.get("source_sha256") == expected_sources
            and result.get("pex_sha256") == digest(args.pex)
            and result.get("testbench_sha256") ==
            digest(args.source / "parent_tb.spice.in")
            and result.get("runner_sha256") == digest(args.source / "run_parent.py"),
            "routed Wi-Fi parent evidence identity changed")
    cases = {case.get("case_id"): case for case in result.get("cases", [])}
    require(set(cases) == set(EXPECTED_ENVIRONMENTS),
            "routed Wi-Fi parent environment set changed")
    for name, environment in EXPECTED_ENVIRONMENTS.items():
        case = cases[name]
        require(tuple(case.get("environment", ())) == environment
                and case.get("complete") is True
                and case.get("result") == "pass"
                and case.get("sample_count", 0) >= 1_000
                and case.get("if_peak_v", 0.0) > 0.0
                and math.isfinite(case.get("conversion_gain_v_per_v", math.nan))
                and math.isfinite(case.get("conversion_gain_db", math.nan)),
                f"{name} lacks a finite extracted parent IF measurement")
    worst = min(case["conversion_gain_db"] for case in cases.values())
    print("wifi LNA/mixer routed parent PEX screen: PASS; 0 DRC, unique LVS, "
          f"5/5 PVT; worst 100 MHz conversion {worst:.3f} dB")


if __name__ == "__main__":
    main()
