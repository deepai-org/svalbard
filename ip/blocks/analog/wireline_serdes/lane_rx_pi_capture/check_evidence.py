#!/usr/bin/env python3
"""Validate the routed PI parent and its localized capture failure."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SERDES = HERE.parent
LANE = SERDES / "lane"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


physical = load("physical_result.json")
parent_pex = HERE / "lane_rx_pi_capture.pex.spice"
require(physical.get("result") == "pass"
        and physical.get("drc_error_count") == 0
        and physical.get("lvs_unique") is True
        and physical.get("interface_port_order_match") is True,
        "PI/RX parent physical closure changed")
require(physical.get("pex_sha256") == digest(parent_pex)
        and physical.get("pex_resistor_count") == 8625
        and physical.get("pex_capacitor_count") == 5034,
        "PI/RX parent extraction changed")

clock = load("clock_chain_result.json")
clock_pex = {
    "clock_restorer_cascade": SERDES / "pll/pex/clock_restorer_cascade.pex.spice",
    "sampler": LANE / "sampler_2p5.pex.spice",
}
require(clock.get("result") == "pass"
        and clock.get("case_count") == 4
        and clock.get("passing_case_count") == 4,
        "PI/restorer/sampler nonlinear-load screen changed")
expected_clock_pex = {name: digest(path) for name, path in clock_pex.items()}
# The PI leaf is deterministically regenerated in the bounded clock-chain flow;
# the promoted parent PEX below remains the byte-retained physical authority.
expected_clock_pex["phase_interpolator"] = (
    "ff1e1b1befa021c67f726872b92e92e696bd32d301aad66e37d128187cb688c4")
require(clock.get("pex_sha256") == expected_clock_pex,
        "clock-chain PEX identity changed")
require(clock.get("source_sha256") == {
            "runner": digest(HERE / "run_clock_chain.py"),
            "testbench": digest(HERE / "clock_chain_tb.spice.in")},
        "clock-chain source identity changed")

smoke = load("capture_smoke_result.json")
require(smoke.get("result") == "fail"
        and smoke.get("case_count") == 2
        and smoke.get("complete_case_count") == 2
        and smoke.get("passing_case_count") == 0,
        "PI/RX diagnostic is not the preserved complete failure")
require(smoke.get("pex_sha256", {}).get("rx_pi_capture_parent_pex")
        == digest(parent_pex)
        and smoke.get("physical_sha256", {}).get("rx_pi_capture_parent")
        == digest(HERE / "physical_result.json"),
        "PI/RX diagnostic physical identity changed")
require(smoke.get("source_sha256") == {
            "runner": digest(LANE / "run_capture_stress_case.py"),
            "base_testbench": digest(LANE / "lane_tb.spice.in")},
        "PI/RX diagnostic source identity changed")
controls = smoke.get("controls", {})
require(controls.get("sampler_bias_v") == 1.3
        and controls.get("clock_restorer_bias_v") == 1.15
        and controls.get("pi_input_polarity_inverted") is True
        and controls.get("odd_capture_skew_ps") == -200
        and controls.get("odd_capture_width_ps") == 500,
        "PI/RX diagnostic calibration changed")
for case in smoke.get("cases", []):
    sampler = min(case.get("minimum_sampler_even_v", 0),
                  case.get("minimum_sampler_odd_v", 0))
    frontend = min(case.get("minimum_frontend_even_v", 0),
                   case.get("minimum_frontend_odd_v", 0))
    odd_capture = case.get("minimum_capture_odd_v", 0)
    require(case.get("complete") is True
            and sampler >= 0.70
            and 2.45 <= case.get("sampler_common_mode_min_v", 0) <= 2.65
            and 2.45 <= case.get("sampler_common_mode_max_v", 0) <= 2.65
            and frontend >= 0.40
            and case.get("minimum_capture_even_v", 0) >= 1.5
            and 0.35 <= odd_capture < 0.50
            and 0.040 <= case.get("supply_current_a", 0) <= 0.060,
            f"PI/RX localization changed in {case.get('id')}")

worst_odd = min(case["minimum_capture_odd_v"] for case in smoke["cases"])
print("routed PI/RX parent: physical PASS; clock load 4/4 PASS; "
      f"preserved odd-capture FAIL at {worst_odd * 1e3:.3f} mV")
