#!/usr/bin/env python3
"""Fail closed on the staged Wi-Fi LNA narrowband PEX noise screen."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


EXPECTED_ENVIRONMENTS = {
    "tt_b1.50": ("typical", 3.30, 27),
    "ff_cold_b1.50": ("ff", 3.63, -40),
    "ff_hot_b1.50": ("ff", 2.97, 125),
    "ss_hot_b1.50": ("ss", 2.97, 125),
    "ss_cold_b1.50": ("ss", 3.63, -40),
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
            "LNA noise screen did not complete all five PVT cases")
    require(result.get("claim") ==
            "wifi_2p4g_external_passive_lna_core_full_rc_noise_screen"
            and result.get("rf_center_hz") == 2.4e9
            and result.get("external_common_bias_v") == 1.5
            and result.get("source_resistance_ohm") == 50.0,
            "LNA noise screen operating boundary changed")
    require(result.get("measurement_status") == (
        "lumped full-RC PEX compact-model narrowband screen; estimated noise "
        "figure is bench-relative and is not RF-model qualification or receiver sensitivity"
    ), "LNA noise model scope changed")
    require(result.get("source_sha256") == digest(args.source / "lna_cs_core.spice")
            and result.get("testbench_sha256") ==
            digest(args.source / "lna_noise_tb.spice.in")
            and result.get("runner_sha256") ==
            digest(args.source / "run_lna_noise.py")
            and result.get("pex_sha256") == digest(args.pex),
            "LNA noise evidence identity changed")
    cases = {case.get("case_id"): case for case in result.get("cases", [])}
    require(set(cases) == set(EXPECTED_ENVIRONMENTS),
            "LNA noise environment set changed")
    for name, expected_environment in EXPECTED_ENVIRONMENTS.items():
        case = cases[name]
        require(tuple(case.get("environment", ())) == expected_environment
                and case.get("bias_v") == 1.5
                and case.get("complete") is True
                and case.get("result") == "pass",
                f"{name} is not a complete fixed-bias noise case")
        require(abs(case.get("ac_frequency_hz", 0.0) - 2.4e9) <= 0.05e9
                and abs(case.get("noise_frequency_hz", 0.0) - 2.4e9) <= 0.05e9
                and case.get("signal_gain_v_per_v", 0.0) > 0.0
                and case.get("output_noise_density_v_per_sqrt_hz", 0.0) > 0.0
                and math.isfinite(case.get("estimated_noise_factor", math.nan))
                and math.isfinite(case.get("estimated_noise_figure_db", math.nan)),
                f"{name} lacks a finite 2.4 GHz noise measurement")
    worst = max(case["estimated_noise_figure_db"] for case in cases.values())
    print("wifi LNA narrowband PEX noise screen: PASS; 5/5 PVT; worst "
          f"bench-relative estimate {worst:.3f} dB")


if __name__ == "__main__":
    main()
