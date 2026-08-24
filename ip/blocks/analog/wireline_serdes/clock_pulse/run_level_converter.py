#!/usr/bin/env python3
"""Qualify the CML-clock to CMOS-clock converter over bounded PVT inputs."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
REQUIRED = {
    "outp_high", "outp_low", "outn_high", "outn_low", "outp_rise",
    "outp_fall", "outp_rise_next", "outn_rise", "outn_fall",
    "inp_rise", "inp_fall", "supply_current",
}
ENVIRONMENTS = (
    ("tt", "typical", 3.30, 27, 0.80, 3.00),
    ("ff_cold", "ff", 3.63, -40, 0.80, 3.00),
    ("ff_hot", "ff", 2.97, 125, 1.10, 2.55),
    ("ss_hot", "ss", 2.97, 125, 1.20, 2.45),
    ("ss_cold", "ss", 3.63, -40, 1.20, 2.45),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
template_path = args.source / "clock_level_converter_tb.spice.in"
template = template_path.read_text()
cases = []
for name, corner, vdd, temperature, low, high in ENVIRONMENTS:
    values = {
        "MOS_CORNER": corner,
        "TEMP_C": str(temperature),
        "VDD_V": f"{vdd:.2f}",
        "INPUT_LOW": f"{low:.3f}",
        "INPUT_HIGH": f"{high:.3f}",
        "INPUT_MID": f"{(low + high) / 2:.6f}",
        "OUTPUT_MID": f"{vdd / 2:.6f}",
    }
    deck = args.work / f"{name}.spice"
    log = args.work / f"{name}.log"
    text = template
    for key, value in values.items():
        text = text.replace(f"@{key}@", value)
    deck.write_text(text)
    with log.open("w") as output:
        run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                             stderr=subprocess.STDOUT, timeout=180, check=False)
    observed = {key: float(value)
                for key, value in MEASURE.findall(log.read_text())}
    complete = run.returncode == 0 and REQUIRED <= observed.keys()
    period = observed.get("outp_rise_next", 0) - observed.get("outp_rise", 0)
    high_time = observed.get("outp_fall", 0) - observed.get("outp_rise", 0)
    if high_time < 0:
        high_time += period
    duty = high_time / period if period > 0 else 0
    rise_delay = observed.get("outp_rise", 0) - observed.get("inp_rise", 0)
    fall_delay = observed.get("outp_fall", 0) - observed.get("inp_fall", 0)
    if period > 0:
        rise_delay = (rise_delay + period / 2) % period - period / 2
        fall_delay = (fall_delay + period / 2) % period - period / 2
    rise_complement_skew = abs(observed.get("outp_rise", 0)
                               - observed.get("outn_fall", 0))
    fall_complement_skew = abs(observed.get("outp_fall", 0)
                               - observed.get("outn_rise", 0))
    passed = (complete
              and observed["outp_high"] >= vdd - 0.25
              and observed["outn_high"] >= vdd - 0.25
              and observed["outp_low"] <= 0.25
              and observed["outn_low"] <= 0.25
              and abs(period - 800e-12) <= 8e-12
              and 0.40 <= duty <= 0.60
              and abs(rise_delay) <= 375e-12
              and abs(fall_delay) <= 375e-12
              and rise_complement_skew <= 60e-12
              and fall_complement_skew <= 60e-12
              and 0 < observed["supply_current"] <= 0.008)
    cases.append({
        "case_id": name,
        "environment": [corner, vdd, temperature],
        "input_low_v": low,
        "input_high_v": high,
        "complete": complete,
        "period_s": period,
        "duty_cycle": duty,
        "rise_delay_s": rise_delay,
        "fall_delay_s": fall_delay,
        "rise_complement_skew_s": rise_complement_skew,
        "fall_complement_skew_s": fall_complement_skew,
        "observed": observed,
        "result": "pass" if passed else "fail",
    })

result = {
    "schema_version": 1,
    "claim": "cml_clock_to_rail_cmos_schematic_pvt",
    "case_count": len(cases),
    "passing_case_count": sum(case["result"] == "pass" for case in cases),
    "load_f_per_output": 100e-15,
    "cases": cases,
    "source_sha256": {
        "dut": digest(args.source / "clock_level_converter.spice"),
        "testbench": digest(template_path),
        "runner": digest(Path(__file__)),
    },
}
result["result"] = ("pass" if result["passing_case_count"] == len(cases)
                    else "fail")
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"clock level converter schematic: {result['passing_case_count']}/"
      f"{len(cases)} pass")
if result["result"] != "pass":
    raise SystemExit(1)
