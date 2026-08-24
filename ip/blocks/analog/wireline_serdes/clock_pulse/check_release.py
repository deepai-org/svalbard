#!/usr/bin/env python3
"""Fail closed on the physically extracted recovered-clock converter release."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SERDES = HERE.parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


pex = HERE / "clock_level_converter.pex.spice"
render = HERE / "layout.png"
physical_path = HERE / "physical_result.json"
extracted_path = HERE / "extracted_result.json"
composed_path = HERE / "composed_result.json"
physical = load("physical_result.json")
extracted = load("extracted_result.json")
composed = load("composed_result.json")

require(physical.get("result") == "pass"
        and physical.get("drc_error_count") == 0
        and physical.get("lvs_unique") is True,
        "clock converter physical closure changed")
require((physical.get("pex_resistor_count"),
         physical.get("pex_capacitor_count")) == (540, 267),
        "clock converter extracted element count changed")
require(physical.get("pex_sha256") == digest(pex)
        and physical.get("layout_image_sha256") == digest(render)
        and physical.get("layout_source_sha256") == digest(HERE / "layout.tcl")
        and physical.get("schematic_source_sha256") == digest(
            HERE / "clock_level_converter.spice")
        and physical.get("checker_source_sha256") == digest(
            HERE / "check_physical.py")
        and physical.get("timing_evidence_sha256") == digest(extracted_path)
        and physical.get("composed_evidence_sha256") == digest(composed_path),
        "clock converter physical evidence identity changed")

require(extracted.get("result") == "pass"
        and extracted.get("case_count") == 5
        and extracted.get("passing_case_count") == 5
        and extracted.get("pex_sha256") == digest(pex),
        "standalone exact-PEX matrix is not 5/5 passing")
for case in extracted.get("cases", []):
    observed = case.get("observed", {})
    vdd = case.get("environment", [None, 0])[1]
    require(case.get("result") == "pass"
            and observed.get("outp_high", 0) >= vdd - 0.25
            and observed.get("outn_high", 0) >= vdd - 0.25
            and observed.get("outp_low", 1) <= 0.25
            and observed.get("outn_low", 1) <= 0.25
            and 0.35 <= case.get("duty_cycle", 0) <= 0.65
            and case.get("rise_complement_skew_s", 1) <= 110e-12
            and case.get("fall_complement_skew_s", 1) <= 110e-12
            and 0 < observed.get("supply_current", 0) <= 0.008,
            f"standalone extracted contract changed: {case.get('case_id')}")

require(composed.get("result") == "pass"
        and composed.get("case_count") == 28
        and composed.get("environment_count") == 5
        and composed.get("covered_environment_count") == 5
        and composed.get("passing_case_count") == 7,
        "composed PI/restorer/converter coverage changed")
require(composed.get("pex_sha256", {}).get("clock_level_converter")
        == digest(pex)
        and composed.get("pex_sha256", {}).get("clock_restorer_cascade")
        == digest(SERDES / "pll/pex/clock_restorer_cascade.pex.spice")
        and composed.get("source_sha256") == {
            "runner": digest(HERE / "run_composed_clock.py"),
            "testbench": digest(HERE / "composed_clock_tb.spice.in"),
        }
        and composed.get("physical_source_sha256") == {
            "phase_interpolator_layout": digest(
                SERDES / "phase_interpolator/layout.tcl"),
            "phase_interpolator_schematic": digest(
                SERDES / "phase_interpolator/phase_interpolator.spice"),
            "clock_restorer_pex": digest(
                SERDES / "pll/pex/clock_restorer_cascade.pex.spice"),
        }, "composed clock evidence identity changed")

passing = {(case.get("case_id"), case.get("restorer_bias_v"),
            case.get("converter_bias_v")): case
           for case in composed.get("cases", []) if case.get("result") == "pass"}
for case_id in ("tt", "ff_cold", "ff_hot", "ss_cold"):
    require((case_id, 1.15, 1.15) in passing,
            f"nominal composed clock code fails: {case_id}")
for point in (("ss_hot", 1.15, 1.0), ("ss_hot", 1.3, 1.0),
              ("ss_hot", 1.3, 1.05)):
    require(point in passing, f"SS/hot calibration point missing: {point}")
for point, case in passing.items():
    observed = case["observed"]
    require(observed.get("raw_high", 0) >= 0.15
            and observed.get("raw_low", 0) <= -0.15
            and observed.get("clk_high", 0) >= 0.40
            and observed.get("clk_low", 0) <= -0.40
            and 0 < observed.get("supply_current", 0) <= 0.025,
            f"composed intermediate contract changed: {point}")

print("clock converter release: PASS; zero DRC, unique LVS, 540R/267C, "
      "standalone 5/5 and composed 5/5 with adjacent SS/hot bias codes")
