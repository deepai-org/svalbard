#!/usr/bin/env python3
"""Verify identity and the deliberately open pulse-generator checkpoint."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(name: str) -> str:
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


physical = load("pulse_physical_checkpoint.json")
schematic = load("pulse_schematic_result.json")
nominal = load("pulse_pex_nominal_result.json")
pvt = load("pulse_pex_pvt_result.json")

require(physical.get("physical_legality_result") == "pass"
        and physical.get("result") == "fail"
        and physical.get("drc_error_count") == 0
        and physical.get("lvs_unique_pin_resolved") is True,
        "pulse physical checkpoint classification changed")
require((physical.get("device_count"), physical.get("layout_width_um"),
         physical.get("layout_height_um")) == (428, 499.6, 285.0),
        "pulse checkpoint geometry changed")
require((physical.get("pex_resistor_count"),
         physical.get("pex_capacitor_count")) == (9344, 6103),
        "pulse checkpoint extracted element count changed")
require(physical.get("schematic_source_sha256")
        == digest("clock_pulse_generator.spice")
        and physical.get("layout_source_sha256")
        == digest("generate_pulse_layout.py")
        and physical.get("layout_image") == "pulse_layout.png"
        and physical.get("layout_image_sha256") == digest("pulse_layout.png")
        and physical.get("testbench_source_sha256")
        == digest("clock_pulse_generator_tb.spice.in")
        and physical.get("runner_source_sha256")
        == digest("run_pulse_generator.py")
        and physical.get("schematic_evidence_sha256")
        == digest("pulse_schematic_result.json")
        and physical.get("pex_nominal_evidence_sha256")
        == digest("pulse_pex_nominal_result.json")
        and physical.get("pex_pvt_evidence_sha256")
        == digest("pulse_pex_pvt_result.json"),
        "pulse checkpoint source/evidence identity changed")

require(schematic.get("result") == "fail"
        and schematic.get("case_count") == 20
        and schematic.get("passing_case_count") == 0
        and schematic.get("environment_coverage") == {
            "tt": [], "ff_cold": [], "ff_hot": [],
            "ss_cold": [], "ss_hot": [],
        },
        "pulse schematic failure matrix changed; regenerate and review it")

require(nominal.get("result") == "pass"
        and nominal.get("case_count") == 1
        and nominal.get("passing_case_count") == 1
        and nominal.get("pex_sha256") == physical.get("pex_sha256"),
        "pulse nominal PEX identity/classification changed")
require(pvt.get("result") == "fail"
        and pvt.get("case_count") == 20
        and pvt.get("passing_case_count") == 1
        and pvt.get("environment_coverage") == {
            "tt": [[0, 8, 9]], "ff_cold": [], "ff_hot": [],
            "ss_cold": [], "ss_hot": [],
        }
        and pvt.get("pex_sha256") == physical.get("pex_sha256"),
        "pulse exact-PVT failure matrix changed")
case = nominal["cases"][0]
observed = case["observed"]
timing_pass = (
    case.get("complete") is True
    and 450e-12 <= case["sense_width_s"] <= 650e-12
    and 450e-12 <= case["odd_sense_width_s"] <= 650e-12
    and 100e-12 <= case["write_width_s"] <= 220e-12
    and 100e-12 <= case["odd_write_width_s"] <= 220e-12
    and 500e-12 <= case["write_delay_s"] <= 700e-12
    and 0 <= case["dead_time_s"] <= 150e-12
    and 350e-12 <= case["odd_spacing_s"] <= 450e-12
    and 0 < observed["supply_current"] <= 0.075
)
rail_pass = (
    min(observed[name] for name in ("es_high", "os_high", "ew_high", "ow_high"))
    >= 3.05
    and max(observed[name] for name in ("es_low", "os_low", "ew_low", "ow_low"))
    <= 0.25
)
require(timing_pass and rail_pass
        and physical.get("nominal_timing_limits_pass") is True
        and physical.get("nominal_rail_limits_pass") is True,
        "pulse nominal timing/rail boundary changed")

print("pulse checkpoint: PASS identity; 0 DRC, unique LVS, 9344R/6103C, "
      "nominal contract closed, exact PVT 1/5 and schematic 0/5")
