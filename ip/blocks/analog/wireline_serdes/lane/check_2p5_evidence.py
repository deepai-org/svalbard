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
