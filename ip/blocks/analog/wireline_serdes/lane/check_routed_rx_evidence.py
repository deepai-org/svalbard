#!/usr/bin/env python3
"""Fail closed on the routed 2.5 GT/s RX-spine milestone."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SERDES = HERE.parent
SPINE = SERDES / "lane_rx_spine"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


pex_paths = {
    "tx_pex": SERDES / "serializer/integrated_serializer_tx_2p5.pex.spice",
    "termination_pex": HERE / "termination_2p5.pex.spice",
    "rx_spine_pex": SPINE / "lane_rx_spine.pex.spice",
    "frontend_pex": HERE / "capture_2p5_calibrated_frontend.pex.spice",
    "deserializer_pex": HERE / "capture_2p5_calibrated_deserializer.pex.spice",
}
physical_paths = {
    "tx": SERDES / "serializer/integrated_tx_2p5_physical_result.json",
    "termination": HERE / "physical_2p5_result.json",
    "rx_spine": SPINE / "physical_result.json",
    "frontend": HERE / "capture_2p5_calibrated_frontend_physical_result.json",
    "deserializer_split": HERE / "capture_2p5_calibrated_physical_result.json",
}
case_paths = {
    name: HERE / f"extracted_capture_2p5_routed_rx_{name}_result.json"
    for name in ("tt", "ff_cold", "ff_hot", "ss_hot", "ss_passive")
}
pex_hashes = {name: digest(path) for name, path in pex_paths.items()}
physical_hashes = {name: digest(path) for name, path in physical_paths.items()}

spine_physical = load(physical_paths["rx_spine"])
require(spine_physical.get("result") == "pass"
        and spine_physical.get("drc_error_count") == 0
        and spine_physical.get("lvs_unique") is True,
        "routed RX spine lacks physical closure")
require(spine_physical.get("pex_sha256") == pex_hashes["rx_spine_pex"],
        "routed RX-spine physical/PEX identity changed")
require(spine_physical.get("pex_resistor_count") == 1309
        and spine_physical.get("pex_capacitor_count") == 464,
        "routed RX-spine extraction changed")

aggregate_path = HERE / "extracted_capture_2p5_routed_rx_result.json"
aggregate = load(aggregate_path)
cases = {name: load(path) for name, path in case_paths.items()}
require(aggregate.get("claim")
        == "routed_rx_parent_extracted_2p5_gts_combined_stress_pvt",
        "routed RX aggregate claim changed")
require(aggregate.get("physical_composition")
        == "routed_rx_restorer_sampler_parent",
        "routed RX aggregate is not a physical parent")
require(aggregate.get("result") == "pass"
        and aggregate.get("case_count") == 5
        and aggregate.get("passing_case_count") == 5,
        "routed RX combined-stress matrix is not 5/5 passing")

aggregate_cases = {case.get("case_id"): case
                   for case in aggregate.get("cases", [])}
require(set(aggregate_cases) == set(case_paths),
        "routed RX environment set changed")
expected_environments = {
    "tt": ("typical", "res_typical", 3.3, 27, 0.5),
    "ff_cold": ("ff", "res_ff", 3.63, -40, 0.5),
    "ff_hot": ("ff", "res_ss", 2.97, 125, 0.5),
    "ss_hot": ("ss", "res_ff", 2.97, 125, 0.5),
    "ss_passive": ("ss", "res_ss", 2.97, 125, 0.5),
}
runner_hash = digest(HERE / "run_capture_stress_case.py")
bench_hash = digest(HERE / "lane_tb.spice.in")
minimums = []
for name, run in cases.items():
    require(run.get("result") == "pass"
            and run.get("case_count") == 1
            and run.get("complete_case_count") == 1
            and run.get("passing_case_count") == 1,
            f"routed RX {name} is not one complete passing case")
    require(tuple(run.get("environment", ())) == expected_environments[name],
            f"routed RX {name} environment changed")
    require(run.get("physical_composition")
            == "routed_rx_restorer_sampler_parent",
            f"routed RX {name} fell back to ideal-wire leaves")
    require(run.get("pex_sha256") == pex_hashes,
            f"routed RX {name} PEX identity changed")
    require(run.get("physical_sha256") == physical_hashes,
            f"routed RX {name} physical identity changed")
    require(run.get("source_sha256") == {
        "base_testbench": bench_hash, "runner": runner_hash},
        f"routed RX {name} source identity changed")
    require(run.get("stimulus", {}).get("serial_rate_hz") == 2.5e9
            and run.get("stimulus", {}).get("pattern") == "prbs7"
            and run.get("stimulus", {}).get("bit_count") == 24
            and run.get("stimulus", {}).get("scored_pair_count") == 8,
            f"routed RX {name} stimulus changed")
    require(run.get("channel_stress", {}).get(
        "series_resistance_ohm_per_leg") == 6.0
            and run.get("channel_stress", {}).get(
                "differential_shunt_capacitance_f") == 1e-12
            and run.get("stimulus", {}).get(
                "tx_clock_jitter_peak_s") == 30e-12
            and run.get("stimulus", {}).get("tx_clock_duty") == 0.47
            and run.get("supply_stress", {}).get(
                "vdd_ripple_peak_v") == 20e-3,
            f"routed RX {name} combined stress changed")
    selected = run.get("selected_case") or {}
    stage_values = {
        "pin": min(selected.get("minimum_pin_even_v", 0),
                   selected.get("minimum_pin_odd_v", 0)),
        "raw_rx": min(selected.get("minimum_rx_even_v", 0),
                      selected.get("minimum_rx_odd_v", 0),
                      selected.get("minimum_rx_hold_even_v", 0),
                      selected.get("minimum_rx_hold_odd_v", 0)),
        "restored": min(selected.get("minimum_restored_even_v", 0),
                        selected.get("minimum_restored_odd_v", 0)),
        "frontend": min(selected.get("minimum_frontend_even_v", 0),
                        selected.get("minimum_frontend_odd_v", 0)),
        "capture": min(selected.get("minimum_capture_even_v", 0),
                       selected.get("minimum_capture_odd_v", 0)),
    }
    require(stage_values["pin"] >= 0.10
            and stage_values["raw_rx"] >= 0.04
            and stage_values["restored"] >= 0.20
            and stage_values["frontend"] >= 0.30
            and stage_values["capture"] >= 0.50
            and 0.010 <= selected.get("supply_current_a", 0) <= 0.060,
            f"routed RX {name} violates a measured contract")
    require(aggregate_cases[name].get("evidence_sha256")
            == digest(case_paths[name]),
            f"routed RX aggregate does not bind {name}")
    minimums.append((stage_values, selected["supply_current_a"]))

worst = {stage: min(values[stage] for values, _ in minimums)
         for stage in ("pin", "raw_rx", "restored", "frontend", "capture")}
maximum_current = max(current for _, current in minimums)
print("routed 2.5 GT/s RX parent: PASS; PVT 5/5; "
      f"worst pin {worst['pin'] * 1e3:.3f} mV; "
      f"raw {worst['raw_rx'] * 1e3:.3f} mV; "
      f"restored {worst['restored'] * 1e3:.3f} mV; "
      f"frontend {worst['frontend']:.5f} V; "
      f"capture {worst['capture'] * 1e3:.3f} mV; "
      f"max current {maximum_current * 1e3:.3f} mA")
