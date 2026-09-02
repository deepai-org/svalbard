#!/usr/bin/env python3
"""Replay a sampled routed-parent SENSE waveform at the exact leaf boundary."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--parent-result", required=True, type=Path)
dut_group = parser.add_mutually_exclusive_group(required=True)
dut_group.add_argument("--pex", type=Path)
dut_group.add_argument("--dut-source", type=Path)
parser.add_argument("--consumer-pex", required=True, type=Path)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--allow-fail", action="store_true")
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)

parent = json.loads(args.parent_result.read_text())
dut_path = args.pex or args.dut_source
dut_subckt = "reference_level_receiver_pex" if args.pex else "reference_level_receiver"
samples = parent.get("waveform_samples", {})
indexed = sorted((int(key.rsplit("_", 1)[1]), value)
                 for key, value in samples.items() if key.startswith("wave_se_in_"))
if len(indexed) != 81 or [index for index, _ in indexed] != list(range(81)):
    raise ValueError("parent result must contain 81 contiguous 10 ps SENSE samples")

points = [(0.0, 0.0), (0.5e-9, indexed[0][1])]
for cycle in range(9):
    origin = 0.8e-9 + cycle * 0.8e-9
    points.extend((origin + index * 10e-12, value) for index, value in indexed)
pwl = " ".join(f"{time:.12g} {value:.9g}" for time, value in points)
deck = args.work / "parent-waveform-replay.spice"
log = args.work / "parent-waveform-replay.log"
deck.write_text(f"""* SPDX-License-Identifier: Apache-2.0
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include {dut_path.resolve()}
.include {args.consumer_pex.resolve()}
.temp 27
VDD VDD 0 PWL(0 0 500p 3.3)
VBIAS VBIAS 0 PWL(0 0 500p 1.4)
VIN IN 0 PWL({pwl})
VREF REF 0 PWL(0 0 500p 1.9)
VLOADP LOAD_INP 0 PWL(0 0 500p 1.75)
VLOADN LOAD_INN 0 PWL(0 0 500p 1.55)
XDUT IN REF VBIAS VDD 0 OUTP OUTN {dut_subckt}
CLOADP OUTP 0 50f
XLOAD LOAD_INP LOAD_INN OUTN 0 0 0 0 VDD 0 LOADP LOADN VDD cml_to_cmos_pex
CLOADP2 LOADP 0 50f
CLOADN2 LOADN 0 50f
.control
tran 2p 8n uic
let isupply = -i(VDD)
meas tran input_high max v(IN) from=4n to=8n
meas tran input_low min v(IN) from=4n to=8n
meas tran outn_high max v(OUTN) from=4n to=8n
meas tran outn_low min v(OUTN) from=4n to=8n
meas tran outn_rise when v(OUTN)=1.65 rise=1 td=4n
meas tran outn_fall when v(OUTN)=1.65 fall=1 td=4n
meas tran outn_rise_next when v(OUTN)=1.65 rise=2 td=4n
meas tran supply_current avg isupply from=4n to=8n
.endc
.end
""")
with log.open("w") as stream:
    run = subprocess.run(["ngspice", "-b", str(deck)], stdout=stream,
                         stderr=subprocess.STDOUT, check=False, timeout=180)
observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
required = {"input_high", "input_low", "outn_high", "outn_low", "outn_rise",
            "outn_fall", "outn_rise_next", "supply_current"}
complete = run.returncode == 0 and required <= observed.keys()
period = observed.get("outn_rise_next", 0) - observed.get("outn_rise", 0)
current_limit = 0.025 if args.consumer_pex else 0.008
passed = (complete and observed["outn_high"] >= 3.05 and observed["outn_low"] <= 0.25
          and abs(period - 800e-12) <= 8e-12
          and 0 < observed["supply_current"] <= current_limit)
result = {
    "schema_version": 1,
    "claim": (("exact_leaf" if args.pex else "schematic_leaf")
              + "_replay_of_sampled_parent_sense_waveform"),
    "scope": "TT, one measured parent period repeated at the exact leaf boundary",
    "parent_result_sha256": digest(args.parent_result),
    "dut_sha256": digest(dut_path),
    "dut_kind": "pex" if args.pex else "schematic",
    "consumer_pex_sha256": digest(args.consumer_pex),
    "deck_sha256": digest(deck), "log_sha256": digest(log),
    "sample_count": len(indexed), "sample_step_s": 10e-12,
    "load_p_f": 50e-15, "consumer": "exact_cml_to_cmos_fast_pex",
    "supply_current_limit_a": current_limit,
    "complete": complete, "observed": observed,
    "not_a_claim": ["routed-parent closure", "PVT coverage", "PCIe compliance"],
    "result": "pass" if passed else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"complete": complete, "result": result["result"],
                  "observed": observed}, sort_keys=True))
if not passed and not args.allow_fail:
    raise SystemExit(1)
