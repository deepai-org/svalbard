#!/usr/bin/env python3
"""Fail closed on the staged full-RC external-LO switching-mixer screen."""
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
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    require(result.get("result") == "pass"
            and result.get("case_count") == 5
            and result.get("passing_case_count") == 5,
            "switching-mixer screen did not complete all five PVT cases")
    require(result.get("claim") ==
            "wifi_2p4g_external_lo_switch_mixer_full_rc_conversion_screen"
            and result.get("rf_hz") == 2.4e9
            and result.get("external_lo_hz") == 2.3e9
            and result.get("intermediate_frequency_hz") == 100e6
            and result.get("rf_input_peak_v") == 10e-3,
            "switching-mixer signal boundary changed")
    require(result.get("source_sha256") == digest(args.source / "mixer.spice")
            and result.get("testbench_sha256") ==
            digest(args.source / "mixer_tb.spice.in")
            and result.get("runner_sha256") == digest(args.source / "run_mixer.py")
            and result.get("pex_sha256") == digest(args.pex),
            "switching-mixer evidence identity changed")
    cases = {case.get("case_id"): case for case in result.get("cases", [])}
    require(set(cases) == set(EXPECTED_ENVIRONMENTS),
            "switching-mixer environment set changed")
    for name, environment in EXPECTED_ENVIRONMENTS.items():
        case = cases[name]
        require(tuple(case.get("environment", ())) == environment
                and case.get("complete") is True
                and case.get("result") == "pass"
                and case.get("sample_count", 0) >= 1_000
                and case.get("if_peak_v", 0.0) > 0.0
                and math.isfinite(case.get("conversion_gain_v_per_v", math.nan))
                and math.isfinite(case.get("conversion_gain_db", math.nan)),
                f"{name} lacks a finite externally driven IF measurement")
    worst = min(case["conversion_gain_db"] for case in cases.values())
    print("wifi external-LO switching mixer PEX screen: PASS; 5/5 PVT; "
          f"worst 100 MHz conversion {worst:.3f} dB")


if __name__ == "__main__":
    main()
