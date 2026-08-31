#!/usr/bin/env python3
"""Fail closed on the bounded Wi-Fi routed-parent two-tone diagnostic."""
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
    require(physical.get("result") == "pass" and physical.get("drc_error_count") == 0
            and physical.get("lvs_unique") is True
            and physical.get("pex_sha256") == digest(args.pex),
            "Wi-Fi two-tone diagnostic lacks physical-parent closure")
    expected_sources = {
        "parent": digest(args.source / "rf_rx_external_lo_parent.spice"),
        "lna": digest(args.source.parent / "rf_lna" / "lna_cs_core.spice"),
        "mixer": digest(args.source.parent / "rf_switch_mixer" / "mixer.spice"),
    }
    require(result.get("result") == "pass"
            and result.get("claim") == "wifi_2p4g_routed_parent_fixed_two_tone_diagnostic"
            and result.get("case_count") == 5 and result.get("passing_case_count") == 5
            and result.get("rf_desired_hz") == 2.4e9
            and result.get("rf_blocker_hz") == 2.425e9
            and result.get("external_lo_hz") == 2.3e9
            and result.get("if_desired_hz") == 100e6
            and result.get("if_blocker_hz") == 125e6
            and result.get("desired_input_peak_v") == 1e-3
            and result.get("blocker_input_peak_v") == 100e-3
            and result.get("blocker_to_desired_input_ratio_db") == 40.0
            and result.get("external_common_lna_bias_v") == 1.5
            and result.get("source_sha256") == expected_sources
            and result.get("testbench_sha256") ==
            digest(args.source / "parent_blocker_tb.spice.in")
            and result.get("runner_sha256") == digest(args.source / "run_parent_blocker.py")
            and result.get("pex_sha256") == digest(args.pex),
            "Wi-Fi two-tone diagnostic identity changed")
    cases = {case.get("case_id"): case for case in result.get("cases", [])}
    require(set(cases) == set(EXPECTED_ENVIRONMENTS),
            "Wi-Fi two-tone environment set changed")
    for name, environment in EXPECTED_ENVIRONMENTS.items():
        case = cases[name]
        require(tuple(case.get("environment", ())) == environment
                and case.get("complete") is True and case.get("result") == "pass",
                f"{name} lacks a complete two-tone observation")
        for tone in ("reference", "with_blocker"):
            observed = case.get(tone, {})
            require(observed.get("complete") is True and observed.get("result") == "pass"
                    and observed.get("sample_count", 0) >= 1_000
                    and math.isfinite(observed.get("desired_if_peak_v", math.nan))
                    and observed.get("desired_if_peak_v", 0.0) > 0.0
                    and math.isfinite(observed.get("blocker_if_peak_v", math.nan)),
                    f"{name} {tone} lacks a finite IF observation")
        require(math.isfinite(case.get("desired_retention_db", math.nan))
                and math.isfinite(case.get("blocker_to_desired_if_ratio_db", math.nan)),
                f"{name} lacks derived two-tone measures")
    worst = min(case["desired_retention_db"] for case in cases.values())
    print("wifi routed-parent two-tone diagnostic: PASS; 5/5 PVT; "
          f"worst fixed-aggressor desired retention {worst:.3f} dB; "
          "not a blocker-tolerance claim")


if __name__ == "__main__":
    main()
