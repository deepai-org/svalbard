#!/usr/bin/env python3
"""Verify extracted PI/restorer drive into the extracted rail converter."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
REQUIRED = {"raw_high", "raw_low", "clk_high", "clk_low", "clk_cm_avg",
            "cmos_p_high", "cmos_p_low", "cmos_n_high", "cmos_n_low",
            "p_rise", "p_fall", "p_rise_next", "n_rise", "n_fall",
            "supply_current"}
ENVIRONMENTS = (
    ("tt", "typical", "res_typical", 3.30, 27),
    ("ff_cold", "ff", "res_ff", 3.63, -40),
    ("ff_hot", "ff", "res_ss", 2.97, 125),
    ("ss_hot", "ss", "res_ff", 2.97, 125),
    ("ss_cold", "ss", "res_ss", 3.63, -40),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--pi-pex", required=True, type=Path)
parser.add_argument("--restorer-pex", required=True, type=Path)
parser.add_argument("--converter-pex", required=True, type=Path)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
template_path = args.source / "composed_clock_tb.spice.in"
template = template_path.read_text()
cases = []
for case_id, mos, res, vdd, temperature in ENVIRONMENTS:
  rest_biases = ((1.0, 1.15, 1.3, 1.45)
                  if case_id == "ss_hot" else (1.15,))
  converter_biases = ((0.9, 0.95, 1.0, 1.05, 1.1, 1.15)
                      if case_id == "ss_hot" else (1.15,))
  for rest_bias in rest_biases:
   for converter_bias in converter_biases:
    values = {
        "MOS_CORNER": mos, "RES_CORNER": res, "VDD_V": str(vdd),
        "TEMP_C": str(temperature), "INPUT_CM": str(vdd / 2),
        "OUTPUT_MID": str(vdd / 2), "PI_PEX": str(args.pi_pex),
        "RESTORER_PEX": str(args.restorer_pex),
        "CONVERTER_PEX": str(args.converter_pex),
        "REST_BIAS": str(rest_bias),
        "CONV_BIAS": str(converter_bias),
    }
    deck = args.work / f"{case_id}-{rest_bias:.2f}-{converter_bias:.2f}.spice"
    log = args.work / f"{case_id}-{rest_bias:.2f}-{converter_bias:.2f}.log"
    text = template
    for name, value in values.items():
        text = text.replace(f"@{name}@", value)
    deck.write_text(text)
    with log.open("w") as output:
        run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                             stderr=subprocess.STDOUT, timeout=600,
                             check=False)
    observed = {name: float(value)
                for name, value in MEASURE.findall(log.read_text())}
    complete = run.returncode == 0 and REQUIRED <= observed.keys()
    period = observed.get("p_rise_next", 0) - observed.get("p_rise", 0)
    high_time = observed.get("p_fall", 0) - observed.get("p_rise", 0)
    if high_time < 0:
        high_time += period
    duty = high_time / period if period > 0 else 0
    rise_skew = abs(observed.get("p_rise", 0) - observed.get("n_fall", 0))
    fall_skew = abs(observed.get("p_fall", 0) - observed.get("n_rise", 0))
    passed = (complete and observed["raw_high"] >= 0.15
              and observed["raw_low"] <= -0.15
              and observed["clk_high"] >= 0.40
              and observed["clk_low"] <= -0.40
              and observed["cmos_p_high"] >= vdd - 0.25
              and observed["cmos_n_high"] >= vdd - 0.25
              and observed["cmos_p_low"] <= 0.25
              and observed["cmos_n_low"] <= 0.25
              and abs(period - 800e-12) <= 15e-12
              and 0.35 <= duty <= 0.65
              and rise_skew <= 110e-12 and fall_skew <= 110e-12
              and 0 < observed["supply_current"] <= 0.025)
    cases.append({"case_id": case_id,
                  "restorer_bias_v": rest_bias,
                  "converter_bias_v": converter_bias,
                  "environment": [mos, res, vdd, temperature],
                  "complete": complete, "period_s": period,
                  "duty_cycle": duty, "rise_complement_skew_s": rise_skew,
                  "fall_complement_skew_s": fall_skew,
                  "observed": observed,
                  "result": "pass" if passed else "fail"})

covered = {case_id: any(case["case_id"] == case_id
                        and case["result"] == "pass" for case in cases)
           for case_id, *_ in ENVIRONMENTS}
result = {
    "schema_version": 1,
    "claim": "extracted_pi_restorer_to_extracted_cmos_clock_converter_pvt",
    "case_count": len(cases),
    "passing_case_count": sum(case["result"] == "pass" for case in cases),
    "environment_count": len(covered),
    "covered_environment_count": sum(covered.values()),
    "environment_coverage": covered,
    "cases": cases,
    "pex_sha256": {"phase_interpolator": digest(args.pi_pex),
                   "clock_restorer_cascade": digest(args.restorer_pex),
                   "clock_level_converter": digest(args.converter_pex)},
    "source_sha256": {"runner": digest(Path(__file__)),
                      "testbench": digest(template_path)},
    "physical_source_sha256": {
        "phase_interpolator_layout": digest(
            args.source.parent / "phase_interpolator/layout.tcl"),
        "phase_interpolator_schematic": digest(
            args.source.parent / "phase_interpolator/phase_interpolator.spice"),
        "clock_restorer_pex": digest(args.restorer_pex),
    },
}
result["result"] = ("pass" if result["covered_environment_count"] == len(covered)
                    else "fail")
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"extracted PI/restorer/converter: {result['covered_environment_count']}/"
      f"{len(covered)} environments covered; {result['passing_case_count']}/"
      f"{len(cases)} bias cases pass")
if result["result"] != "pass":
    raise SystemExit(1)
