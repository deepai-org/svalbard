#!/usr/bin/env python3
"""Qualify the active-high OUTN role, optionally with the exact consumer PEX."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


ENVIRONMENTS = (
    ("tt", "typical", 3.30, 27, 0.80, 3.00),
    ("ff_cold", "ff", 3.63, -40, 0.80, 3.00),
    ("ff_hot", "ff", 2.97, 125, 1.10, 2.55),
    ("ss_hot", "ss", 2.97, 125, 1.20, 2.45),
    ("ss_cold", "ss", 3.63, -40, 1.20, 2.45),
)
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--dut", required=True, type=Path)
parser.add_argument("--dut-subckt", required=True)
parser.add_argument("--consumer-pex", type=Path)
parser.add_argument("--biases", nargs="+", type=float,
                    default=(0.85, 0.90, 1.00, 1.08, 1.20, 1.40, 1.60, 1.80))
parser.add_argument("--reference-offsets", nargs="+", type=float,
                    default=(0.0, 0.10, 0.20, 0.30))
parser.add_argument("--control-plan", type=Path)
parser.add_argument("--environment-ids", nargs="+")
parser.add_argument("--pulse-high-ps", type=float, default=510.0)
parser.add_argument("--minimum-duty", type=float, default=0.20)
parser.add_argument("--maximum-duty", type=float, default=0.60)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
environments = tuple(item for item in ENVIRONMENTS
                     if not args.environment_ids or item[0] in args.environment_ids)
if not environments:
    raise ValueError("no selected environments")
runs = []
if args.control_plan:
    control_plan = json.loads(args.control_plan.read_text())
    control_pairs = sorted({(item["bias_v"], item["reference_offset_v"])
                            for item in control_plan.values()})
else:
    control_plan = None
    control_pairs = [(bias, offset) for bias in args.biases
                     for offset in args.reference_offsets]
for bias, reference_offset in control_pairs:
    cases = []
    for case_id, corner, vdd, temperature, low, high in environments:
        if control_plan and control_plan[case_id] != {
                "bias_v": bias, "reference_offset_v": reference_offset}:
            continue
        stem = (f"b{bias:.2f}-r{reference_offset:.2f}".replace(".", "p")
                + "-" + case_id)
        deck, log = args.work / f"{stem}.spice", args.work / f"{stem}.log"
        consumer_include = f".include {args.consumer_pex.resolve()}" if args.consumer_pex else ""
        consumer = ("XLOAD LOAD_INP LOAD_INN OUTN 0 0 0 0 VDD 0 LOADP LOADN VDD cml_to_cmos_pex\n"
                    "CLOADP2 LOADP 0 50f\nCLOADN2 LOADN 0 50f"
                    if args.consumer_pex else "CLOADN OUTN 0 100f")
        midpoint = (low + high) / 2
        reference = midpoint + reference_offset
        deck.write_text(f"""* SPDX-License-Identifier: Apache-2.0
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {corner}
.include {args.dut.resolve()}
{consumer_include}
.temp {temperature}
VDD VDD 0 PWL(0 0 500p {vdd})
VBIAS VBIAS 0 PWL(0 0 500p {bias})
VIN IN 0 PULSE({low} {high} 1n 30p 30p {args.pulse_high_ps}p 800p)
VREF REF 0 PWL(0 0 500p {reference})
VLOADP LOAD_INP 0 PWL(0 0 500p {midpoint + 0.1})
VLOADN LOAD_INN 0 PWL(0 0 500p {midpoint - 0.1})
XDUT IN REF VBIAS VDD 0 OUTP OUTN {args.dut_subckt}
CLOADP OUTP 0 50f
{consumer}
.control
tran 2p 8n uic
let isupply = -i(VDD)
meas tran outn_high max v(OUTN) from=4n to=8n
meas tran outn_low min v(OUTN) from=4n to=8n
meas tran outn_rise when v(OUTN)={vdd/2} rise=1 td=4n
meas tran outn_fall when v(OUTN)={vdd/2} fall=1 td=4n
meas tran outn_rise_next when v(OUTN)={vdd/2} rise=2 td=4n
meas tran supply_current avg isupply from=4n to=8n
.endc
.end
""")
        with log.open("w") as stream:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=stream,
                                 stderr=subprocess.STDOUT, timeout=240, check=False)
        observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
        required = {"outn_high", "outn_low", "outn_rise", "outn_fall",
                    "outn_rise_next", "supply_current"}
        complete = run.returncode == 0 and required <= observed.keys()
        period = observed.get("outn_rise_next", 0) - observed.get("outn_rise", 0)
        high_time = observed.get("outn_fall", 0) - observed.get("outn_rise", 0)
        if high_time < 0 and period > 0:
            high_time += period
        duty = high_time / period if period > 0 else 0
        current_limit = 0.025 if args.consumer_pex else 0.008
        passed = (complete and observed["outn_high"] >= vdd - 0.25
                  and observed["outn_low"] <= 0.25
                  and abs(period - 800e-12) <= 8e-12
                  and args.minimum_duty <= duty <= args.maximum_duty
                  and 0 < observed["supply_current"] <= current_limit)
        cases.append({"case_id": case_id, "environment": [corner, vdd, temperature],
                      "complete": complete, "period_s": period, "duty_cycle": duty,
                      "observed": observed, "result": "pass" if passed else "fail"})
    runs.append({"bias_v": bias, "reference_offset_v": reference_offset,
                 "cases": cases,
                 "passing_case_count": sum(x["result"] == "pass" for x in cases)})
windows = {}
for case_id, *_ in environments:
    passing = [{"bias_v": run["bias_v"],
                "reference_offset_v": run["reference_offset_v"]}
               for run in runs for case in run["cases"]
               if case["case_id"] == case_id and case["result"] == "pass"]
    windows[case_id] = {"passing_controls": passing,
                        "result": "pass" if passing else "fail"}
result = {"schema_version": 1, "claim": "active_high_sense_output_programmable_pvt",
          "dut_sha256": digest(args.dut),
          "consumer_pex_sha256": digest(args.consumer_pex) if args.consumer_pex else None,
          "biases_v": args.biases, "reference_offsets_v": args.reference_offsets,
          "pulse_high_s": args.pulse_high_ps * 1e-12,
          "duty_limits": [args.minimum_duty, args.maximum_duty],
          "control_plan_sha256": digest(args.control_plan) if args.control_plan else None,
          "runs": runs, "calibration_windows": windows,
          "covered_case_count": sum(x["result"] == "pass" for x in windows.values()),
          "case_count": len(environments),
          "not_a_claim": ["mismatch yield", "parent closure", "PCIe compliance"]}
result["result"] = "pass" if result["covered_case_count"] == len(environments) else "fail"
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"sense OUTN coverage: {result['covered_case_count']}/{len(environments)}")
if result["result"] != "pass":
    raise SystemExit(1)
