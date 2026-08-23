#!/usr/bin/env python3
"""Fail closed on the committed exact-PEX 2.5 GT/s lane milestone."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SERDES = HERE.parent


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"2.5 GT/s evidence FAIL: {message}")


release_paths = {
    "tx_pex": SERDES / "serializer/integrated_serializer_tx.pex.spice",
    "termination_pex": HERE / "termination_2p5.pex.spice",
    "rx_pex": HERE / "rx_2p5.pex.spice",
    "sampler_pex": HERE / "sampler_2p5.pex.spice",
    "restorer_pex": SERDES / "data_restorer/data_restorer_2p5.pex.spice",
}
base_physical_path = HERE / "physical_2p5_result.json"
restorer_physical_path = SERDES / "data_restorer/physical_2p5_result.json"
nominal_path = HERE / "extracted_2p5_result.json"
regeneration_path = HERE / "regeneration_2p5_result.json"
pvt_paths = (
    HERE / "extracted_2p5_pvt_tt_result.json",
    HERE / "extracted_2p5_pvt_ff_cold_result.json",
    HERE / "extracted_2p5_pvt_ff_hot_result.json",
    HERE / "extracted_2p5_pvt_ss_hot_result.json",
    HERE / "extracted_2p5_pvt_ss_passive_result.json",
)

base_physical = load(base_physical_path)
restorer_physical = load(restorer_physical_path)
nominal = load(nominal_path)
regeneration = load(regeneration_path)
pvt = [load(path) for path in pvt_paths]
aggregate = load(HERE / "extracted_2p5_pvt_result.json")

require(base_physical.get("result") == "pass", "base physical record failed")
for cell, hash_key in (("termination", "termination_pex"),
                       ("rx", "rx_pex"), ("sampler", "sampler_pex")):
    record = base_physical.get("cells", {}).get(cell, {})
    require(record.get("drc_error_count") == 0, f"{cell} is not zero-DRC")
    require(record.get("lvs_unique") is True, f"{cell} lacks unique LVS")
    require(record.get("pex_resistor_count", 0) > 0, f"{cell} PEX lacks resistors")
    require(record.get("pex_capacitor_count", 0) > 0, f"{cell} PEX lacks capacitors")
    require(record.get("pex_sha256") == digest(release_paths[hash_key]),
            f"{cell} release PEX changed")

require(restorer_physical.get("result") == "pass", "restorer physical record failed")
require(restorer_physical.get("drc_error_count") == 0, "restorer is not zero-DRC")
require(restorer_physical.get("lvs_unique") is True, "restorer lacks unique LVS")
require(restorer_physical.get("pex_resistor_count", 0) > 0, "restorer PEX lacks resistors")
require(restorer_physical.get("pex_capacitor_count", 0) > 0, "restorer PEX lacks capacitors")
require(restorer_physical.get("pex_sha256") == digest(release_paths["restorer_pex"]),
        "restorer release PEX changed")

expected_hashes = {key: digest(path) for key, path in release_paths.items()}
expected_hashes.update({
    "base_physical": digest(base_physical_path),
    "restorer_physical": digest(restorer_physical_path),
})

all_runs = [nominal, *pvt]
for index, run in enumerate(all_runs):
    label = "nominal" if index == 0 else f"PVT case {index}"
    require(run.get("result") == "pass", f"{label} failed")
    require(run.get("claim") == "externally_clocked_2p5_gts_tx_to_sampler_composition",
            f"{label} has the wrong claim")
    require(run.get("serial_rate_hz") == 2.5e9, f"{label} has the wrong serial rate")
    require(run.get("extraction") == "full_rc_leaves", f"{label} is not full-RC")
    require(run.get("complete_case_count") == run.get("case_count"),
            f"{label} has incomplete phase simulations")
    require(run.get("passing_case_count", 0) >= 1, f"{label} has no passing phase")
    for key, value in expected_hashes.items():
        require(run.get("source_hashes", {}).get(key) == value,
                f"{label} does not bind exact {key}")
    selected = run.get("selected_case") or {}
    require(selected.get("selected_latency_ui") in (0, 1),
            f"{label} selected unsupported integer latency")
    window = selected.get("selected_rx_contract_window") or {}
    require(window.get("minimum_signed_v", 0) >= 0.04,
            f"{label} violates the raw-RX hold contract")
    require(selected.get("minimum_signed_restored_v", 0) >= 0.20,
            f"{label} violates the restorer margin contract")
    require(selected.get("minimum_signed_sample_v", 0) >= 0.10,
            f"{label} violates the sampler margin contract")

require(nominal.get("case_count") == 16, "nominal phase sweep is not exhaustive")
require(nominal.get("passing_case_count", 0) >= 3, "nominal phase aperture is too narrow")
require(nominal["selected_case"].get("selected_latency_ui") == 0,
        "nominal selection unexpectedly requires a UI shift")

expected_environments = {
    ("typical", "res_typical", 3.3, 27, 0.5),
    ("ff", "res_ff", 3.63, -40, 0.5),
    ("ff", "res_ss", 2.97, 125, 0.5),
    ("ss", "res_ff", 2.97, 125, 0.5),
    ("ss", "res_ss", 2.97, 125, 0.5),
}
require({tuple(run.get("environment", ())) for run in pvt} == expected_environments,
        "representative PVT environment set changed")
require(aggregate.get("result") == "pass", "PVT aggregate failed")
require(aggregate.get("environment_count") == 5, "PVT aggregate is incomplete")
require(aggregate.get("passing_environment_count") == 5, "not every PVT environment passes")
require([case.get("evidence_sha256") for case in aggregate.get("cases", [])]
        == [digest(path) for path in pvt_paths], "PVT aggregate does not bind its case files")

require(regeneration.get("result") == "pass", "fresh geometry regeneration failed")
require(all(regeneration.get("lane_pex_identity", {}).values()),
        "regeneration run did not simulate the exact release PEX")
require(all(regeneration.get("release_physical_identity", {}).values()),
        "regeneration run is not bound to release physical evidence")

minimum_sample_mv = min(run["selected_case"]["minimum_signed_sample_v"] for run in pvt) * 1e3
print(f"2.5 GT/s exact-PEX evidence: PASS; 16 nominal phases, "
      f"{nominal['passing_case_count']} pass; PVT 5/5; "
      f"worst selected sample margin {minimum_sample_mv:.3f} mV")

fast_deserializer_path = HERE / "capture_2p5_fast_deserializer.pex.spice"
fast_frontend_path = HERE / "capture_2p5_fast_frontend.pex.spice"
fast_physical_path = HERE / "capture_2p5_fast_physical_result.json"
fast_case_paths = {
    name: HERE / f"extracted_capture_2p5_fast_{name}_result.json"
    for name in ("ff_cold", "ff_hot")
}
fast_physical = load(fast_physical_path)
require(fast_physical.get("result") == "pass", "fast-corner capture physical failed")
require(fast_physical.get("drc_error_count") == 0,
        "fast-corner capture is not zero-DRC")
require(fast_physical.get("checks", {}).get("lvs_unique") is True,
        "fast-corner capture lacks unique LVS")
require(fast_physical.get("checks", {}).get("full_rc") is True,
        "fast-corner capture lacks full-RC extraction")
require(fast_physical.get("pex_sha256") == digest(fast_deserializer_path),
        "fast-corner physical record does not bind the committed capture PEX")
require(fast_physical.get("layout_source_sha256")
        == digest(SERDES / "deserializer_split/layout.tcl"),
        "fast-corner physical record does not bind the capture layout")
require(fast_physical.get("schematic_source_sha256")
        == digest(SERDES / "deserializer_split/deserializer_split.spice"),
        "fast-corner physical record does not bind the capture schematic")

fast_cases = {name: load(path) for name, path in fast_case_paths.items()}
expected_fast_environments = {
    "ff_cold": ("ff", "res_ff", 3.63, -40, 0.5),
    "ff_hot": ("ff", "res_ss", 2.97, 125, 0.5),
}
expected_fast_controls = {
    "ff_cold": {"tx_bias_v": 1.1, "sampler_phase_deg": 67.5,
                "rx_window_start_ps": 50},
    "ff_hot": {"tx_bias_v": 1.6, "sampler_phase_deg": 16.875,
               "rx_window_start_ps": 100},
}
for name, run in fast_cases.items():
    require(run.get("result") == "pass", f"2.5 GT/s {name} calibration failed")
    require(run.get("claim") == "extracted_2p5_gts_lane_dual_cmos_capture",
            f"2.5 GT/s {name} has the wrong claim")
    require(tuple(run.get("environment", ())) == expected_fast_environments[name],
            f"2.5 GT/s {name} environment changed")
    require(run.get("complete_case_count") == 1
            and run.get("passing_case_count") == 1,
            f"2.5 GT/s {name} is not a complete passing single-point proof")
    controls = run.get("controls", {})
    require(controls.get("capture_width_ps") == 380
            and controls.get("tx_load_code") == 2
            and controls.get("latency_ui") == 0,
            f"2.5 GT/s {name} structural controls changed")
    for key, value in expected_fast_controls[name].items():
        require(controls.get(key) == value,
                f"2.5 GT/s {name} control {key} changed")
    hashes = run.get("pex_sha256", {})
    for key in ("tx_pex", "termination_pex", "rx_pex", "sampler_pex",
                "restorer_pex"):
        require(hashes.get(key) == expected_hashes[key],
                f"2.5 GT/s {name} does not bind exact {key}")
    require(hashes.get("frontend_pex") == digest(fast_frontend_path),
            f"2.5 GT/s {name} does not bind the committed converter PEX")
    require(hashes.get("deserializer_pex") == digest(fast_deserializer_path),
            f"2.5 GT/s {name} does not bind the committed capture PEX")
    physical_hashes = run.get("physical_sha256", {})
    require(physical_hashes.get("base_lane") == expected_hashes["base_physical"]
            and physical_hashes.get("restorer") == expected_hashes["restorer_physical"]
            and physical_hashes.get("deserializer_split") == digest(fast_physical_path),
            f"2.5 GT/s {name} physical evidence identity changed")
    source_hashes = run.get("source_sha256", {})
    require(source_hashes.get("runner") == digest(HERE / "run_capture_stress_case.py")
            and source_hashes.get("base_testbench") == digest(HERE / "lane_tb.spice.in"),
            f"2.5 GT/s {name} source identity changed")
    measured = run.get("selected_case") or {}
    require(measured.get("result") == "pass" and measured.get("complete") is True,
            f"2.5 GT/s {name} selected measurement is incomplete")
    require(min(measured.get("minimum_pin_even_v", 0),
                measured.get("minimum_pin_odd_v", 0)) >= 0.10,
            f"2.5 GT/s {name} violates the pin-eye contract")
    require(min(measured.get("minimum_capture_even_v", 0),
                measured.get("minimum_capture_odd_v", 0)) >= 0.50,
            f"2.5 GT/s {name} violates the final-capture contract")
    require(0.010 <= measured.get("supply_current_a", 0) <= 0.060,
            f"2.5 GT/s {name} violates the current contract")

print("2.5 GT/s fast-corner calibration: PASS; FF/cold and FF/hot close "
      "through exact-PEX final capture")

precal_path = HERE / "extracted_capture_2p5_stress_precal_result.json"
precal = load(precal_path)
precal_case_paths = {
    name: HERE / f"extracted_capture_2p5_stress_precal_{name}_result.json"
    for name in ("tt", "ff_cold", "ff_hot", "ss_hot", "ss_passive")
}
require(precal.get("claim") == "precalibration_2p5_gts_combined_stress_pvt",
        "combined-stress pre-calibration claim changed")
require(precal.get("result") == "fail" and precal.get("passing_case_count") == 1,
        "combined-stress pre-calibration no longer records the expected 1/5 result")
precal_cases = {case.get("case_id"): case for case in precal.get("cases", [])}
require(set(precal_cases) == {"tt", "ff_cold", "ff_hot", "ss_hot", "ss_passive"},
        "combined-stress pre-calibration environment set changed")
require(precal_cases["tt"].get("result") == "pass",
        "combined-stress nominal environment regressed")
require(precal_cases["ff_cold"]["measurements"].get("supply_current_a", 0) > 0.060,
        "FF/cold failure mechanism is no longer the recorded current overrun")
require(precal_cases["ff_hot"]["measurements"].get("minimum_capture_odd_v", 1) < 0.50,
        "FF/hot failure mechanism is no longer the recorded odd capture margin")
for case_id in ("ss_hot", "ss_passive"):
    require(precal_cases[case_id]["measurements"].get(
        "minimum_frontend_even_v", 1) < 0.0,
        f"{case_id} failure mechanism is no longer the converter schedule")
for case in precal_cases.values():
    hashes = case.get("pex_sha256", {})
    for key, value in expected_hashes.items():
        if key.endswith("_pex"):
            require(hashes.get(key) == value,
                    f"combined-stress pre-calibration does not bind exact {key}")
    physical_hashes = case.get("physical_sha256", {})
    require(physical_hashes.get("base_lane") == expected_hashes["base_physical"],
            "combined-stress pre-calibration does not bind base physical evidence")
    require(physical_hashes.get("restorer") == expected_hashes["restorer_physical"],
            "combined-stress pre-calibration does not bind restorer physical evidence")
    source_hashes = case.get("source_sha256", {})
    require(source_hashes.get("runner")
            == "f11e93fa80cee44bb95ddb6eb2bd231967889740693b809f7412b36618507f1f",
            "combined-stress historical runner identity changed")
    require(source_hashes.get("base_testbench") == digest(HERE / "lane_tb.spice.in"),
            "combined-stress pre-calibration testbench changed")
for name, path in precal_case_paths.items():
    require(precal_cases[name].get("evidence_sha256") == digest(path),
            f"combined-stress pre-calibration does not bind {name} evidence")

print("2.5 GT/s combined-stress pre-calibration: preserved FAIL; "
      "1/5 environments pass with four localized mechanisms")
