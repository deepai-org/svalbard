#!/usr/bin/env python3
"""Fail closed on the direct-regenerative 2.5 GT/s RX/capture evidence."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SERDES = HERE.parent
LANE = SERDES / "lane"
FRONT = SERDES / "lane_rx_regenerative_frontend"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


parent_pex = HERE / "lane_rx_regenerative_capture.pex.spice"
parent_physical_path = HERE / "physical_result.json"
front_pex = FRONT / "lane_rx_regenerative_frontend.pex.spice"
front_physical_path = FRONT / "physical_result.json"
tx_pex = SERDES / "serializer/integrated_serializer_tx_2p5.pex.spice"
tx_physical_path = SERDES / "serializer/integrated_tx_2p5_physical_result.json"
runner = LANE / "run_capture_stress_case.py"
testbench = LANE / "lane_tb.spice.in"
merger = LANE / "merge_capture_2p5_regenerative.py"

parent_physical = load(parent_physical_path)
front_physical = load(front_physical_path)
for name, physical, pex, layout, schematic, render, checker, counts in (
    ("capture parent", parent_physical, parent_pex, HERE / "layout.tcl",
     HERE / "lane_rx_regenerative_capture.spice", HERE / "layout.png",
     HERE / "check_physical.py", (7108, 4348)),
    ("regenerative front end", front_physical, front_pex, FRONT / "layout.tcl",
     FRONT / "lane_rx_regenerative_frontend.spice", FRONT / "layout.png",
     FRONT / "check_physical.py", (5139, 2949)),
):
    require(physical.get("result") == "pass"
            and physical.get("drc_error_count") == 0
            and physical.get("lvs_unique") is True,
            f"{name} lacks physical closure")
    require(physical.get("pex_sha256") == digest(pex),
            f"{name} PEX identity changed")
    require(physical.get("layout_source_sha256") == digest(layout)
            and physical.get("schematic_source_sha256") == digest(schematic)
            and physical.get("layout_image_sha256") == digest(render)
            and physical.get("checker_source_sha256") == digest(checker),
            f"{name} physical source identity changed")
    require((physical.get("pex_resistor_count"),
             physical.get("pex_capacitor_count")) == counts,
            f"{name} extracted element count changed")

case_paths = {
    name: HERE / f"capture_2p5_{name}_result.json"
    for name in ("tt", "ff_cold", "ff_hot", "ss_hot", "ss_passive")
}
cases = {name: load(path) for name, path in case_paths.items()}
aggregate = load(HERE / "capture_2p5_pvt_result.json")
composition = "routed_termination_rx_dual_regenerative_sampler_capture_parent"
expected_environments = {
    "tt": ("typical", "res_typical", 3.3, 27, 0.5),
    "ff_cold": ("ff", "res_ff", 3.63, -40, 0.5),
    "ff_hot": ("ff", "res_ss", 2.97, 125, 0.5),
    "ss_hot": ("ss", "res_ff", 2.97, 125, 0.5),
    "ss_passive": ("ss", "res_ss", 2.97, 125, 0.5),
}
expected_frontend_latencies = {
    "tt": 2, "ff_cold": 0, "ff_hot": 2, "ss_hot": 2, "ss_passive": 2,
}
expected_package_boundary = {
    "topology": "per_leg_pad_ac_coupling_series_rl_with_rx_bias_returns",
    "tx_pad_capacitance_f": 300e-15,
    "rx_pad_capacitance_f": 500e-15,
    "ac_coupling_capacitance_f": 100e-9,
    "series_resistance_ohm_per_leg": 2.0,
    "series_inductance_h_per_leg": 1e-9,
    "bias_return_resistance_ohm_per_leg": 2e3,
    "model_status": "explicit_unqualified_lumped_screen_assumption",
    "unmodeled": [
        "pad_esd_nonlinearity", "bond_mutual_inductance",
        "package_s_parameters", "board_connector_channel", "em_and_ir",
    ],
}
pex_hashes = {
    "tx_pex": digest(tx_pex),
    "rx_regenerative_capture_parent_pex": digest(parent_pex),
}
physical_hashes = {
    "tx": digest(tx_physical_path),
    "rx_regenerative_capture_parent": digest(parent_physical_path),
}
source_hashes = {
    "base_testbench": digest(testbench),
    "runner": digest(runner),
}

require(aggregate.get("result") == "pass"
        and aggregate.get("case_count") == 5
        and aggregate.get("passing_case_count") == 5,
        "regenerative capture PVT is not 5/5 passing")
require(aggregate.get("claim") ==
        "routed_regenerative_rx_capture_extracted_2p5_gts_combined_stress_pvt"
        and aggregate.get("physical_composition") == composition,
        "regenerative capture aggregate claim changed")
require(aggregate.get("package_boundary") == expected_package_boundary,
        "regenerative capture aggregate package boundary changed")
require(aggregate.get("aggregate_source_sha256") == digest(merger),
        "regenerative capture merger identity changed")
aggregate_cases = {case.get("case_id"): case
                   for case in aggregate.get("cases", [])}
require(set(aggregate_cases) == set(case_paths),
        "regenerative capture environment set changed")

stage_minima = {stage: [] for stage in ("pin", "sampler", "write", "capture")}
currents = []
for name, run in cases.items():
    require(run.get("result") == "pass"
            and run.get("case_count") == 1
            and run.get("complete_case_count") == 1
            and run.get("passing_case_count") == 1,
            f"{name} is not one complete passing case")
    require(tuple(run.get("environment", ())) == expected_environments[name],
            f"{name} environment changed")
    require(run.get("evidence_class") == "exact_pex"
            and run.get("physical_composition") == composition,
            f"{name} is not exact routed-parent evidence")
    require(run.get("package_boundary") == expected_package_boundary,
            f"{name} package boundary changed")
    require(run.get("pex_sha256") == pex_hashes
            and run.get("physical_sha256") == physical_hashes
            and run.get("source_sha256") == source_hashes,
            f"{name} evidence identity changed")
    stimulus = run.get("stimulus", {})
    controls = run.get("controls", {})
    channel = run.get("channel_stress", {})
    supply = run.get("supply_stress", {})
    require(stimulus.get("serial_rate_hz") == 2.5e9
            and stimulus.get("pattern") == "prbs7"
            and stimulus.get("bit_count") == 24
            and stimulus.get("scored_pair_count") == 8
            and stimulus.get("tx_clock_jitter_peak_s") == 30e-12
            and stimulus.get("tx_clock_duty") == 0.47
            and channel.get("series_resistance_ohm_per_leg") == 6.0
            and channel.get("differential_shunt_capacitance_f") == 1e-12
            and supply.get("vdd_ripple_peak_v") == 20e-3
            and supply.get("vdd_ripple_frequency_hz") == 100e6,
            f"{name} combined stress changed")
    require(controls.get("restorer_mode") == "none"
            and controls.get("frontend_tail_boost") is True
            and controls.get("frontend_sense_width_ps") == 550
            and controls.get("capture_delay_ps") == 200
            and controls.get("capture_width_ps") == 150
            and controls.get("frontend_latency_ui") ==
                expected_frontend_latencies[name]
            and controls.get("frontend_write_latency_ui") == 2
            and controls.get("capture_latency_ui") == 2,
            f"{name} timing contract changed")
    selected = run.get("selected_case") or {}
    measurements = {
        "pin": min(selected.get("minimum_pin_even_v", 0),
                   selected.get("minimum_pin_odd_v", 0)),
        "sampler": min(selected.get("minimum_sampler_even_v", 0),
                       selected.get("minimum_sampler_odd_v", 0)),
        "write": min(selected.get("minimum_frontend_write_even_v", 0),
                     selected.get("minimum_frontend_write_odd_v", 0)),
        "capture": min(selected.get("minimum_capture_even_v", 0),
                       selected.get("minimum_capture_odd_v", 0)),
    }
    require(measurements["pin"] >= 0.10
            and measurements["sampler"] >= 0.04
            and measurements["write"] >= 0.30
            and measurements["capture"] >= 0.50
            and 0.010 <= selected.get("supply_current_a", 0) <= 0.060,
            f"{name} violates a measured contract")
    require(aggregate_cases[name].get("evidence_sha256") ==
            digest(case_paths[name]),
            f"aggregate does not bind {name}")
    for stage, value in measurements.items():
        stage_minima[stage].append(value)
    currents.append(selected["supply_current_a"])

aperture = load(HERE / "capture_2p5_ss_hot_aperture_result.json")
require(aperture.get("result") == "pass"
        and aperture.get("case_count") == 5
        and aperture.get("complete_case_count") == 5
        and aperture.get("passing_case_count") == 5,
        "SS/hot aperture is not 5/5 passing")
require(tuple(aperture.get("environment", ())) == expected_environments["ss_hot"]
        and aperture.get("physical_composition") == composition
        and aperture.get("evidence_class") == "exact_pex",
        "SS/hot aperture environment or composition changed")
require(aperture.get("package_boundary") == expected_package_boundary,
        "SS/hot aperture package boundary changed")
require(aperture.get("pex_sha256") == pex_hashes
        and aperture.get("physical_sha256") == physical_hashes
        and aperture.get("source_sha256") == source_hashes,
        "SS/hot aperture evidence identity changed")
require(aperture.get("controls", {}).get("capture_delay_ps") == 200
        and aperture.get("controls", {}).get("capture_width_ps") == 150
        and aperture.get("controls", {}).get("frontend_write_latency_ui") == 2
        and aperture.get("controls", {}).get("capture_latency_ui") == 2,
        "SS/hot aperture timing contract changed")
require([case.get("conversion_offset_s") for case in aperture.get("cases", [])]
        == [0.0, 50e-12, 100e-12, 150e-12, 200e-12],
        "SS/hot aperture offset set changed")
for case in aperture.get("cases", []):
    require(case.get("result") == "pass"
            and min(case.get("minimum_pin_even_v", 0),
                    case.get("minimum_pin_odd_v", 0)) >= 0.10
            and min(case.get("minimum_sampler_even_v", 0),
                    case.get("minimum_sampler_odd_v", 0)) >= 0.04
            and min(case.get("minimum_frontend_write_even_v", 0),
                    case.get("minimum_frontend_write_odd_v", 0)) >= 0.30
            and min(case.get("minimum_capture_even_v", 0),
                    case.get("minimum_capture_odd_v", 0)) >= 0.50,
            f"SS/hot aperture case {case.get('id')} violates a contract")

print("direct-regenerative 2.5 GT/s RX/capture: PASS; exact PEX 5/5 PVT "
      "and 5/5 SS/hot aperture; worst pin "
      f"{min(stage_minima['pin']) * 1e3:.3f} mV; sampler "
      f"{min(stage_minima['sampler']) * 1e3:.3f} mV; write "
      f"{min(stage_minima['write']):.5f} V; capture "
      f"{min(stage_minima['capture']):.5f} V; max current "
      f"{max(currents) * 1e3:.3f} mA")
