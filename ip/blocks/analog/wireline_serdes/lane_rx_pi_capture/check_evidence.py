#!/usr/bin/env python3
"""Validate routed PI/RX/capture evidence and preserve open PVT failures."""

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

clock_sources = {
    "runner": digest(HERE / "run_clock_chain.py"),
    "testbench": digest(HERE / "clock_chain_tb.spice.in"),
}
fixed_clock_pex = {
    "clock_restorer_cascade": digest(
        SERDES / "pll/pex/clock_restorer_cascade.pex.spice"),
    "sampler": digest(LANE / "sampler_2p5.pex.spice"),
}
for name, environment in (
        ("clock_chain_result.json", ["typical", "res_typical", 3.3, 27.0]),
        ("clock_chain_ss_result.json", ["ss", "res_ss", 2.97, 125.0])):
    clock = load(name)
    require(clock.get("result") == "pass"
            and clock.get("case_count") == 4
            and clock.get("passing_case_count") == 4
            and clock.get("environment") == environment,
            f"{name} clock-load screen changed")
    require(clock.get("source_sha256") == clock_sources,
            f"{name} source identity changed")
    for cell, expected in fixed_clock_pex.items():
        require(clock.get("pex_sha256", {}).get(cell) == expected,
                f"{name} {cell} PEX changed")
    require(len(clock.get("pex_sha256", {}).get("phase_interpolator", "")) == 64,
            f"{name} regenerated PI PEX identity missing")

timing = load("capture_timing_result.json")
require(timing.get("result") == "pass"
        and timing.get("case_count") == 8
        and timing.get("complete_case_count") == 8
        and timing.get("passing_case_count") == 2,
        "nominal PI/RX timing screen changed")
require({case["id"] for case in timing["cases"] if case["result"] == "pass"}
        == {"convert_200p", "convert_300p"},
        "nominal PI/RX passing aperture changed")
controls = timing.get("controls", {})
require(controls.get("capture_delay_ps") == 550
        and controls.get("capture_width_ps") == 380
        and controls.get("capture_output_delay_ps") == 1050
        and controls.get("sampler_bias_v") == 1.3
        and controls.get("pi_input_phase_deg") == 0.0
        and controls.get("pi_input_polarity_inverted") is True,
        "nominal PI/RX controls changed")

expected_pex = {
    "rx_pi_capture_parent_pex": digest(parent_pex),
    "tx_pex": digest(SERDES / "serializer/integrated_serializer_tx_2p5.pex.spice"),
}
expected_physical = {
    "rx_pi_capture_parent": digest(HERE / "physical_result.json"),
    "tx": digest(SERDES / "serializer/integrated_tx_2p5_physical_result.json"),
}
expected_sources = {
    "runner": digest(LANE / "run_capture_stress_case.py"),
    "base_testbench": digest(LANE / "lane_tb.spice.in"),
}
require(timing.get("pex_sha256") == expected_pex
        and timing.get("physical_sha256") == expected_physical
        and timing.get("source_sha256") == expected_sources,
        "nominal PI/RX evidence identity changed")
for case in timing["cases"]:
    require(case.get("complete") is True
            and case.get("pi_clock_rise_s") is not None
            and case.get("pi_clock_fall_s") is not None,
            f"incomplete timing case {case.get('id')}")
for case in timing["cases"]:
    if case["result"] != "pass":
        continue
    require(min(case["minimum_pin_even_v"], case["minimum_pin_odd_v"]) >= 0.10
            and min(case["minimum_sampler_even_v"],
                    case["minimum_sampler_odd_v"]) >= 0.50
            and min(case["minimum_frontend_even_v"],
                    case["minimum_frontend_odd_v"]) >= 0.30
            and min(case["minimum_capture_even_v"],
                    case["minimum_capture_odd_v"]) >= 1.20,
            f"nominal passing margin changed in {case.get('id')}")

pvt = load("capture_pvt_result.json")
require(pvt.get("result") == "fail"
        and pvt.get("case_count") == 5
        and pvt.get("passing_case_count") == 1,
        "PVT result must preserve one pass and four failures")
require(pvt.get("aggregate_source_sha256")
        == digest(LANE / "merge_capture_2p5_calibrated.py"),
        "PVT aggregate source identity changed")
pvt_cases = {case["case_id"]: case for case in pvt["cases"]}
require(set(pvt_cases) == {"tt", "ff_cold", "ff_hot", "ss_hot", "ss_passive"}
        and pvt_cases["tt"]["result"] == "pass"
        and all(pvt_cases[name]["result"] == "fail"
                for name in ("ff_cold", "ff_hot", "ss_hot", "ss_passive")),
        "PVT case classification changed")
for name, case in pvt_cases.items():
    require(case.get("pex_sha256") == expected_pex
            and case.get("physical_sha256") == expected_physical
            and case.get("source_sha256") == expected_sources,
            f"PVT identity changed in {name}")
ff_cold = pvt_cases["ff_cold"]["measurements"]
require(min(ff_cold["minimum_frontend_even_v"],
            ff_cold["minimum_frontend_odd_v"]) >= 2.30
        and max(ff_cold["minimum_capture_even_v"],
                ff_cold["minimum_capture_odd_v"]) < 0.01,
        "FF/cold capture-regeneration localization changed")
ss_passive = pvt_cases["ss_passive"]["measurements"]
require(min(ss_passive["minimum_frontend_even_v"],
            ss_passive["minimum_frontend_odd_v"]) < -2.0,
        "SS/passive dynamic-decision failure localization changed")

print("routed PI/RX parent: physical PASS; TT/SS clock load 4/4 PASS; "
      "nominal timing 2/8 PASS; composed PVT 1/5 PASS (open)")
