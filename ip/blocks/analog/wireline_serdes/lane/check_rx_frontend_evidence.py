#!/usr/bin/env python3
"""Fail closed on the routed 2.5 GT/s RX-front-end parent milestone."""

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SERDES = HERE.parent
FRONT = SERDES / "lane_rx_frontend"
WORK = Path(sys.argv[1]) if len(sys.argv) == 2 else HERE
IN_CONTAINER = len(sys.argv) == 2


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


pex_paths = {
    "tx_pex": SERDES / "serializer/integrated_serializer_tx_2p5.pex.spice",
    "rx_frontend_parent_pex": FRONT / "lane_rx_frontend.pex.spice",
    "deserializer_pex": HERE / "capture_2p5_calibrated_deserializer.pex.spice",
}
physical_paths = {
    "tx": SERDES / "serializer/integrated_tx_2p5_physical_result.json",
    "rx_frontend_parent": FRONT / "physical_result.json",
    "deserializer_split": HERE / "capture_2p5_calibrated_physical_result.json",
}
case_paths = {
    name: WORK / (f"capture-2p5-front-{name}.json" if IN_CONTAINER else
                  f"extracted_capture_2p5_rx_frontend_{name}_result.json")
    for name in ("tt", "ff_cold", "ff_hot", "ss_hot", "ss_passive")
}
pex_hashes = {name: digest(path) for name, path in pex_paths.items()}
physical_hashes = {name: digest(path) for name, path in physical_paths.items()}

front_physical = load(physical_paths["rx_frontend_parent"])
require(front_physical.get("result") == "pass"
        and front_physical.get("drc_error_count") == 0
        and front_physical.get("lvs_unique") is True,
        "routed RX front end lacks physical closure")
require(front_physical.get("pex_sha256")
        == pex_hashes["rx_frontend_parent_pex"],
        "RX-front-end physical/PEX identity changed")
require(front_physical.get("pex_resistor_count") == 5926
        and front_physical.get("pex_capacitor_count") == 3405,
        "RX-front-end extraction changed")

aggregate = load(WORK / ("capture-2p5-front.json" if IN_CONTAINER else
                         "extracted_capture_2p5_rx_frontend_result.json"))
cases = {name: load(path) for name, path in case_paths.items()}
require(aggregate.get("claim")
        == "routed_rx_frontend_parent_extracted_2p5_gts_combined_stress_pvt",
        "RX-front-end aggregate claim changed")
require(aggregate.get("physical_composition")
        == "routed_termination_rx_spine_dual_converter_parent",
        "RX-front-end aggregate is not the physical parent")
require(aggregate.get("result") == "pass"
        and aggregate.get("case_count") == 5
        and aggregate.get("passing_case_count") == 5,
        "RX-front-end combined-stress matrix is not 5/5 passing")

aggregate_cases = {case.get("case_id"): case
                   for case in aggregate.get("cases", [])}
require(set(aggregate_cases) == set(case_paths),
        "RX-front-end environment set changed")
expected_environments = {
    "tt": ("typical", "res_typical", 3.3, 27, 0.5),
    "ff_cold": ("ff", "res_ff", 3.63, -40, 0.5),
    "ff_hot": ("ff", "res_ss", 2.97, 125, 0.5),
    "ss_hot": ("ss", "res_ff", 2.97, 125, 0.5),
    "ss_passive": ("ss", "res_ss", 2.97, 125, 0.5),
}
# Historical campaign generator; newer PI diagnostics must not rewrite it.
runner_hash = "fd43983feed45e3fa231602d05c6237ee3a6eaa9169708b58bcbde3415d628d4"
bench_hash = digest(HERE / "lane_tb.spice.in")
minimums = []
for name, run in cases.items():
    require(run.get("result") == "pass"
            and run.get("case_count") == 1
            and run.get("complete_case_count") == 1
            and run.get("passing_case_count") == 1,
            f"RX-front-end {name} is not one complete passing case")
    require(tuple(run.get("environment", ())) == expected_environments[name],
            f"RX-front-end {name} environment changed")
    require(run.get("physical_composition")
            == "routed_termination_rx_spine_dual_converter_parent",
            f"RX-front-end {name} fell back to ideal-wire leaves")
    require(run.get("pex_sha256") == pex_hashes,
            f"RX-front-end {name} PEX identity changed")
    require(run.get("physical_sha256") == physical_hashes,
            f"RX-front-end {name} physical identity changed")
    require(run.get("source_sha256") == {
        "base_testbench": bench_hash, "runner": runner_hash},
        f"RX-front-end {name} source identity changed")
    stimulus = run.get("stimulus", {})
    channel = run.get("channel_stress", {})
    supply = run.get("supply_stress", {})
    require(stimulus.get("serial_rate_hz") == 2.5e9
            and stimulus.get("pattern") == "prbs7"
            and stimulus.get("bit_count") == 24
            and stimulus.get("scored_pair_count") == 8
            and channel.get("series_resistance_ohm_per_leg") == 6.0
            and channel.get("differential_shunt_capacitance_f") == 1e-12
            and stimulus.get("tx_clock_jitter_peak_s") == 30e-12
            and stimulus.get("tx_clock_duty") == 0.47
            and supply.get("vdd_ripple_peak_v") == 20e-3,
            f"RX-front-end {name} combined stress changed")
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
            f"RX-front-end {name} violates a measured contract")
    require(aggregate_cases[name].get("evidence_sha256")
            == digest(case_paths[name]),
            f"RX-front-end aggregate does not bind {name}")
    minimums.append((stage_values, selected["supply_current_a"]))

worst = {stage: min(values[stage] for values, _ in minimums)
         for stage in ("pin", "raw_rx", "restored", "frontend", "capture")}
maximum_current = max(current for _, current in minimums)
print("routed 2.5 GT/s RX front end: PASS; PVT 5/5; "
      f"worst pin {worst['pin'] * 1e3:.3f} mV; "
      f"raw {worst['raw_rx'] * 1e3:.3f} mV; "
      f"restored {worst['restored'] * 1e3:.3f} mV; "
      f"frontend {worst['frontend']:.5f} V; "
      f"capture {worst['capture'] * 1e3:.3f} mV; "
      f"max current {maximum_current * 1e3:.3f} mA")
