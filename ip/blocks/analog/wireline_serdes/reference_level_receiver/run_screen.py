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
parser.add_argument("--pex", type=Path)
parser.add_argument("--dut-source", type=Path)
parser.add_argument("--dut-subckt")
parser.add_argument("--vbias", type=float, default=1.15)
parser.add_argument("--pulse-high-ps", type=float, default=370.0)
parser.add_argument("--source-resistance-ohm", type=float, default=0.0)
parser.add_argument("--load-f", type=float, default=100e-15)
parser.add_argument("--load-p-f", type=float)
parser.add_argument("--load-n-f", type=float)
parser.add_argument("--reference-input", action="store_true",
                    help="hold INN at the input midpoint instead of driving its complement")
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
load_p = args.load_p_f if args.load_p_f is not None else args.load_f
load_n = args.load_n_f if args.load_n_f is not None else args.load_f
args.work.mkdir(parents=True, exist_ok=True)
template_path = args.source / "clock_level_converter_tb.spice.in"
template = template_path.read_text()
if args.pex:
    dut_path = args.pex
    dut_subckt = args.dut_subckt or "clock_level_converter_pex"
else:
    dut_path = args.dut_source or args.source / "clock_level_converter.spice"
    dut_subckt = args.dut_subckt or "clock_level_converter"
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
        "VBIAS_V": f"{args.vbias:.6f}",
        "DUT_PATH": str(dut_path),
        "DUT_SUBCKT": dut_subckt,
    }
    deck = args.work / f"{name}.spice"
    log = args.work / f"{name}.log"
    text = template
    for key, value in values.items():
        text = text.replace(f"@{key}@", value)
    text = text.replace("30p 30p 370p 800p",
                        f"30p 30p {args.pulse_high_ps:.6g}p 800p")
    text = text.replace("CLOADP OUTP 0 100f",
                        f"CLOADP OUTP 0 {load_p:.12g}")
    text = text.replace("CLOADN OUTN 0 100f",
                        f"CLOADN OUTN 0 {load_n:.12g}")
    if args.source_resistance_ohm > 0:
        text = re.sub(r"^VINP INP 0 (PULSE\([^\n]+\))$",
                      (f"VINP INP_SRC 0 \\1\nRINP INP_SRC INP "
                       f"{args.source_resistance_ohm:.9g}"), text,
                      flags=re.MULTILINE)
    if args.reference_input:
        text = re.sub(r"^VINN INN 0 PULSE\([^\n]+\)$",
                      f"VINN INN 0 {(low + high) / 2:.6f}", text,
                      flags=re.MULTILINE)
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
    def cyclic_separation(first: float, second: float) -> float:
        delta = first - second
        return abs((delta + period / 2) % period - period / 2) if period > 0 else abs(delta)

    rise_complement_skew = cyclic_separation(
        observed.get("outp_rise", 0), observed.get("outn_fall", 0))
    fall_complement_skew = cyclic_separation(
        observed.get("outp_fall", 0), observed.get("outn_rise", 0))
    complement_skew_limit = 200e-12 if args.reference_input else 110e-12
    passed = (complete
              and observed["outp_high"] >= vdd - 0.25
              and observed["outn_high"] >= vdd - 0.25
              and observed["outp_low"] <= 0.25
              and observed["outn_low"] <= 0.25
              and abs(period - 800e-12) <= 8e-12
              and 0.35 <= duty <= 0.65
              and abs(rise_delay) <= 400e-12
              and abs(fall_delay) <= 400e-12
              and rise_complement_skew <= complement_skew_limit
              and fall_complement_skew <= complement_skew_limit
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
        "complement_skew_limit_s": complement_skew_limit,
        "observed": observed,
        "result": "pass" if passed else "fail",
    })

result = {
    "schema_version": 1,
    "claim": (("single_ended_reference_to_rail_cmos_" if args.reference_input
               else "cml_clock_to_rail_cmos_")
              + ("extracted_pvt" if args.pex else "schematic_pvt")),
    "case_count": len(cases),
    "passing_case_count": sum(case["result"] == "pass" for case in cases),
    "load_f_per_output": args.load_f,
    "load_p_f": load_p,
    "load_n_f": load_n,
    "pulse_high_s": args.pulse_high_ps * 1e-12,
    "source_resistance_ohm": args.source_resistance_ohm,
    "vbias_v": args.vbias,
    "input_mode": "single_ended_reference" if args.reference_input else "differential",
    "cases": cases,
    "source_sha256": {
        "dut": digest(dut_path),
        "testbench": digest(template_path),
        "runner": digest(Path(__file__)),
    },
}
if args.pex:
    result["pex_sha256"] = digest(args.pex)
result["result"] = ("pass" if result["passing_case_count"] == len(cases)
                    else "fail")
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"clock level converter schematic: {result['passing_case_count']}/"
      f"{len(cases)} pass")
if result["result"] != "pass":
    raise SystemExit(1)
