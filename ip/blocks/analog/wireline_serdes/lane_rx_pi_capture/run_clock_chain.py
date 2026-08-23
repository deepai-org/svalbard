#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
REQUIRED = {
    "raw_high", "raw_low", "clk_high", "clk_low", "clk_cm_avg",
    "phase_a_rise", "raw_rise", "clk_rise", "even_high", "even_low",
    "odd_high", "odd_low", "supply_current",
}


parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--pi-pex", required=True, type=Path)
parser.add_argument("--restorer-pex", required=True, type=Path)
parser.add_argument("--sampler-pex", required=True, type=Path)
parser.add_argument("--case-id", default="tt")
parser.add_argument("--mos-corner", default="typical")
parser.add_argument("--res-corner", default="res_typical")
parser.add_argument("--temperature", type=float, default=27.0)
parser.add_argument("--vdd", type=float, default=3.3)
parser.add_argument("--input-common-mode", type=float, default=1.65)
parser.add_argument("--sampler-bias", type=float, default=1.10)
parser.add_argument("--data-p", type=float, default=1.75)
parser.add_argument("--data-n", type=float, default=1.55)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
template = (args.source / "clock_chain_tb.spice.in").read_text()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

cases = []
for rest_bias in (0.8, 1.0, 1.15, 1.3):
    values = {
        "MOS_CORNER": args.mos_corner, "RES_CORNER": args.res_corner,
        "TEMP_C": str(args.temperature), "VDD_V": str(args.vdd),
        "INPUT_CM": str(args.input_common_mode), "CTRL_A": "1.15",
        "CTRL_B": "1.15", "PI_BIAS": "1.15", "REST_BIAS": str(rest_bias),
        "SAMP_BIAS": str(args.sampler_bias), "DATA_P": str(args.data_p),
        "DATA_N": str(args.data_n),
        "PI_PEX": str(args.pi_pex), "RESTORER_PEX": str(args.restorer_pex),
        "SAMPLER_PEX": str(args.sampler_pex),
    }
    deck = args.work / f"rest_{rest_bias:.2f}.spice"
    log = args.work / f"rest_{rest_bias:.2f}.log"
    text = template
    for name, value in values.items():
        text = text.replace(f"@{name}@", value)
    deck.write_text(text)
    with log.open("w") as output:
        run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                             stderr=subprocess.STDOUT, timeout=300, check=False)
    observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
    complete = run.returncode == 0 and REQUIRED <= observed.keys()
    passed = complete and (
        observed["raw_high"] >= 0.15 and observed["raw_low"] <= -0.15
        and observed["clk_high"] >= 0.40 and observed["clk_low"] <= -0.40
        and 0.0 < observed["supply_current"] <= 0.040
    )
    cases.append({"restorer_bias_v": rest_bias, "complete": complete,
                  "observed": observed, "result": "pass" if passed else "fail"})

passing = [case for case in cases if case["result"] == "pass"]
result = {
    "schema_version": 1,
    "claim": "extracted_pi_limiter_nonlinear_dual_sampler_clock_drive",
    "case_id": args.case_id,
    "environment": [args.mos_corner, args.res_corner, args.vdd, args.temperature],
    "stimulus": {"input_common_mode_v": args.input_common_mode,
                 "sampler_bias_v": args.sampler_bias,
                 "data_p_v": args.data_p, "data_n_v": args.data_n},
    "case_count": len(cases),
    "passing_case_count": len(passing),
    "selected_case": max(passing, key=lambda case: min(
        case["observed"]["clk_high"], -case["observed"]["clk_low"]))
        if passing else None,
    "cases": cases,
    "pex_sha256": {
        "phase_interpolator": sha256(args.pi_pex),
        "clock_restorer_cascade": sha256(args.restorer_pex),
        "sampler": sha256(args.sampler_pex),
    },
    "source_sha256": {
        "runner": sha256(Path(__file__)),
        "testbench": sha256(args.source / "clock_chain_tb.spice.in"),
    },
    "result": "pass" if passing else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(f"PI/restorer/sampler clock chain: {len(passing)}/{len(cases)} pass")
if not passing:
    raise SystemExit(1)
