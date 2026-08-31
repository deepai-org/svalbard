#!/usr/bin/env python3
"""Localize the FF/cold WRITE collapse in the PCIe capture boundary.

This is deliberately a one-corner, product-specific counterfactual.  It
compares the qualified 650 fF placeholder used by the pulse leaf with the
actual extracted bridge input while retaining the same SENSE/BOOST placeholder
loads.  The composed lane result remains the source of truth; this probe only
separates a known WRITE-output failure from bridge input loading and from the
actual lane SENSE/BOOST input network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
VDD = 3.63


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--pulse-pex", required=True, type=Path)
parser.add_argument("--pulse-physical", required=True, type=Path)
parser.add_argument("--bridge-pex", required=True, type=Path)
parser.add_argument("--bridge-physical", required=True, type=Path)
parser.add_argument("--lane-pex", required=True, type=Path)
parser.add_argument("--lane-physical", required=True, type=Path)
parser.add_argument("--work", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)


def require_bound(pex: Path, physical: Path, name: str) -> None:
    record = json.loads(physical.read_text())
    if record.get("result") != "pass" or record.get("pex_sha256") != digest(pex):
        raise SystemExit(f"{name} PEX does not match a passing physical record")


require_bound(args.pulse_pex, args.pulse_physical, "pulse")
require_bound(args.bridge_pex, args.bridge_physical, "bridge")
require_bound(args.lane_pex, args.lane_physical, "lane")


def deck(consumer: str) -> str:
    bridge = ""
    if consumer == "bridge_pex":
        bridge = """
* Actual extracted WRITE consumer; its outputs are locally loaded but no lane
* is present.  Keep the pulse leaf's established SENSE/BOOST load constant so
* the comparison changes only the WRITE consumer.
CES E_SENSE_CLK 0 350f
CEB E_SENSE_BOOST 0 350f
COS O_SENSE_CLK 0 350f
COB O_SENSE_BOOST 0 350f
XBRIDGE E_WRITE O_WRITE E_CAPTURE_CLK E_CAPTURE_CLKB
+ O_CAPTURE_CLK O_CAPTURE_CLKB VDD 0 capture_clock_bridge_pex
CECLK E_CAPTURE_CLK 0 50f
CECLKB E_CAPTURE_CLKB 0 50f
COCLK O_CAPTURE_CLK 0 50f
COCLKB O_CAPTURE_CLKB 0 50f
"""
    elif consumer == "lane_sense_pex":
        bridge = """
* Actual extracted direct-regenerative SENSE/BOOST consumer.  The capture and
* retained REGEN compatibility pins are clamped to VSS, so this does not claim
* a working lane; it changes only the pulse's SENSE-side load from placeholder
* capacitors to the real extracted parent.  WRITE retains the 650 fF baseline.
VRXP RXP_SRC 0 PWL(0 0 500p 1.915)
VRXN RXN_SRC 0 PWL(0 0 500p 1.715)
VRXBIAS RX_BIAS_SRC 0 PWL(0 0 500p 1.200)
VTHP VTHP_SRC 0 PWL(0 0 500p 1.815)
VTHN VTHN_SRC 0 PWL(0 0 500p 1.815)
VBW RX_BW_EN_N_SRC 0 0
RRXP RXP_SRC RXP 1
RRXN RXN_SRC RXN 1
RRXBIAS RX_BIAS_SRC RX_BIAS 1
RVTHP VTHP_SRC VTHP 1
RVTHN VTHN_SRC VTHN 1
RBW RX_BW_EN_N_SRC RX_BW_EN_N 1
VTERM0 TERM_EN0_N_SRC 0 0
VTERM1 TERM_EN1_N_SRC 0 0
VTERM2 TERM_EN2_N_SRC 0 0
VTERM3 TERM_EN3_N_SRC 0 3.63
VTERM4 TERM_EN4_N_SRC 0 3.63
VTERM5 TERM_EN5_N_SRC 0 3.63
VTERM6 TERM_EN6_N_SRC 0 3.63
RTERM0 TERM_EN0_N_SRC TERM_EN0_N 1
RTERM1 TERM_EN1_N_SRC TERM_EN1_N 1
RTERM2 TERM_EN2_N_SRC TERM_EN2_N 1
RTERM3 TERM_EN3_N_SRC TERM_EN3_N 1
RTERM4 TERM_EN4_N_SRC TERM_EN4_N 1
RTERM5 TERM_EN5_N_SRC TERM_EN5_N 1
RTERM6 TERM_EN6_N_SRC TERM_EN6_N 1
REREGEN E_REGEN_CLK 0 1m
REREGENB E_REGEN_CLKB 0 1m
ROREGEN O_REGEN_CLK 0 1m
ROREGENB O_REGEN_CLKB 0 1m
RECAPTURE E_CAPTURE_CLK 0 1m
RECAPTUREB E_CAPTURE_CLKB 0 1m
ROCAPTURE O_CAPTURE_CLK 0 1m
ROCAPTUREB O_CAPTURE_CLKB 0 1m
CEW E_WRITE 0 650f
COW O_WRITE 0 650f
XREGENCAP RXP RXN TERM_EN0_N TERM_EN1_N TERM_EN2_N TERM_EN3_N
+ TERM_EN4_N TERM_EN5_N TERM_EN6_N VTHP VTHN RX_BIAS RX_BW_EN_N
+ E_SENSE_CLK E_REGEN_CLK E_REGEN_CLKB E_CAPTURE_CLK
+ E_CAPTURE_CLKB E_SENSE_BOOST O_SENSE_CLK O_REGEN_CLK
+ O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB O_SENSE_BOOST
+ VDD 0 RXOP RXON FE_E_P FE_E_N FE_O_P FE_O_N
+ EVEN_Q EVEN_QB ODD_Q ODD_QB lane_rx_regenerative_capture_pex
CEQ EVEN_Q 0 50f
CEQB EVEN_QB 0 50f
COQ ODD_Q 0 50f
COQB ODD_QB 0 50f
"""
    else:
        bridge = """
* The established pulse-leaf boundary: 350 fF SENSE/BOOST and 650 fF WRITE.
* It represents the load assumed by the original pulse PEX screen.
CES E_SENSE_CLK 0 350f
CEB E_SENSE_BOOST 0 350f
CEW E_WRITE 0 650f
COS O_SENSE_CLK 0 350f
COB O_SENSE_BOOST 0 350f
COW O_WRITE 0 650f
"""
    return f"""* SPDX-License-Identifier: Apache-2.0
* FF/cold load-localization counterfactual for the PCIe capture boundary.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice ff
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_ff
.include {args.pulse_pex}
.include {args.bridge_pex}
.include {args.lane_pex}
.temp -40

VDD VDD 0 PWL(0 0 500p 3.63)
VCPCLKP CP_CLKP 0 PULSE(0 3.63 1n 20p 20p 380p 800p)
VCPCLKN CP_CLKN 0 PULSE(3.63 0 1n 20p 20p 380p 800p)
VSEL0 SEL0 0 0
VSEL1 SEL1 0 0
VSEL2 SEL2 0 PWL(0 0 500p 3.63)
VSEL3 SEL3 0 0

XPULSE CP_CLKP CP_CLKN SEL0 SEL1 SEL2 SEL3 VDD 0 VDD VDD 0 0
+ CP_CLKP CP_CLKN E_SENSE_CLK E_SENSE_BOOST E_WRITE
+ O_SENSE_CLK O_SENSE_BOOST O_WRITE clock_pulse_generator_pex
{bridge}
.control
tran 2p 5n uic
let isupply = -i(VDD)
meas tran e_sense_high max v(E_SENSE_CLK) from=3n to=5n
meas tran o_sense_high max v(O_SENSE_CLK) from=3n to=5n
meas tran e_write_high max v(E_WRITE) from=3n to=5n
meas tran o_write_high max v(O_WRITE) from=3n to=5n
meas tran supply_current avg isupply from=3n to=5n
quit
.endc
.end
"""


cases = []
for consumer in ("placeholder_caps", "bridge_pex", "lane_sense_pex"):
    path = args.work / f"{consumer}.spice"
    log = args.work / f"{consumer}.log"
    path.write_text(deck(consumer))
    with log.open("w") as output:
        process = subprocess.run(["ngspice", "-b", str(path)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=600, check=False)
    observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
    complete = process.returncode == 0 and {
        "e_sense_high", "o_sense_high", "e_write_high", "o_write_high", "supply_current"
    } <= observed.keys()
    passed = complete and min(observed.get("e_write_high", 0),
                              observed.get("o_write_high", 0)) >= VDD - 0.25
    cases.append({"consumer": consumer, "complete": complete, "observed": observed,
                  "result": "pass" if passed else "fail"})

result = {
    "schema_version": 1,
    "claim": "ff_cold_pulse_write_load_localization",
    "scope": "counterfactual diagnostic; not PCIe lane closure",
    "environment": ["ff", "res_ff", VDD, -40],
    "profile": [0, 8, 9],
    "cases": cases,
    "pulse_pex_sha256": digest(args.pulse_pex),
    "pulse_physical_sha256": digest(args.pulse_physical),
    "bridge_pex_sha256": digest(args.bridge_pex),
    "bridge_physical_sha256": digest(args.bridge_physical),
    "lane_pex_sha256": digest(args.lane_pex),
    "lane_physical_sha256": digest(args.lane_physical),
    "result": "pass" if all(case["result"] == "pass" for case in cases) else "fail",
}
args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": result["result"], "cases": cases}, sort_keys=True))
if result["result"] != "pass":
    raise SystemExit(1)
