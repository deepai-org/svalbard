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
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
template = (args.source / "clock_chain_tb.spice.in").read_text()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

cases = []
for rest_bias in (0.8, 1.0, 1.15, 1.3):
    values = {
        "MOS_CORNER": "typical", "RES_CORNER": "res_typical", "TEMP_C": "27",
        "VDD_V": "3.3", "INPUT_CM": "1.65", "CTRL_A": "1.15",
        "CTRL_B": "1.15", "PI_BIAS": "1.15", "REST_BIAS": str(rest_bias),
        "SAMP_BIAS": "1.10", "DATA_P": "1.75", "DATA_N": "1.55",
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
