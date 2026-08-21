#!/usr/bin/env python3
"""Measure optimistic native-3.3 V GF180 inverter speed bounds."""

import json
import re
import subprocess
from pathlib import Path


WORK = Path("/work")
PDK = "/foss/pdks/gf180mcuD/libs.tech/ngspice"
ENVIRONMENTS = (
    ("tt_3v30_25c", "typical", "res_typical", 3.30, 25),
    ("ff_3v63_n40c", "ff", "res_ff", 3.63, -40),
    ("ss_2v97_125c", "ss", "res_ss", 2.97, 125),
)
MEASURE = re.compile(r"^(tplh|tphl|trise|tfall|period)\s*=\s*([-+0-9.eE]+)", re.M)


def preamble(mos: str, resistor: str, voltage: float, temperature: int) -> str:
    return f""".include {PDK}/design.ngspice
.lib {PDK}/sm141064.ngspice {mos}
.lib {PDK}/sm141064.ngspice {resistor}
.temp {temperature}
.param V={voltage}
.subckt inv A Y VDD VSS
MN Y A VSS VSS nfet_03v3 w=0.22u l=0.28u
MP Y A VDD VDD pfet_03v3 w=0.44u l=0.28u
.ends inv
"""


def chain_deck(env: tuple) -> str:
    _, mos, resistor, voltage, temperature = env
    return preamble(mos, resistor, voltage, temperature) + f"""
V0 d0 0 {voltage}
V1 d1 0 {voltage}
V2 d2 0 {voltage}
VIN in 0 PULSE(0 {voltage} 0.5n 5p 5p 0.5n 1n)
X0 in n0 d0 0 inv
X1 n0 n1 d1 0 inv
X2 n1 n2 d2 0 inv
.control
tran 0.25p 5n
meas tran tplh trig v(n0) val={voltage / 2} fall=2 targ v(n1) val={voltage / 2} rise=2
meas tran tphl trig v(n0) val={voltage / 2} rise=2 targ v(n1) val={voltage / 2} fall=2
meas tran trise trig v(n1) val={voltage * .2} rise=2 targ v(n1) val={voltage * .8} rise=2
meas tran tfall trig v(n1) val={voltage * .8} fall=2 targ v(n1) val={voltage * .2} fall=2
.endc
.end
"""


def ring_deck(env: tuple) -> str:
    _, mos, resistor, voltage, temperature = env
    return preamble(mos, resistor, voltage, temperature) + f"""
VDD VDD 0 {voltage}
X0 n0 n1 VDD 0 inv
X1 n1 n2 VDD 0 inv
X2 n2 n0 VDD 0 inv
.ic v(n0)=0 v(n1)={voltage} v(n2)=0
.control
tran 0.25p 10n uic
meas tran period trig v(n0) val={voltage / 2} rise=20 targ v(n0) val={voltage / 2} rise=21
.endc
.end
"""


def simulate(label: str, kind: str, deck: str) -> dict:
    deck_path = WORK / f"{label}-{kind}.spice"
    log_path = WORK / f"{label}-{kind}.log"
    deck_path.write_text(deck)
    with log_path.open("w") as log:
        run = subprocess.run(
            ["ngspice", "-b", str(deck_path)],
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
        )
    measures = {key: float(value) for key, value in MEASURE.findall(log_path.read_text())}
    if run.returncode or (kind == "chain" and not {"tplh", "tphl"} <= measures.keys()):
        raise RuntimeError(f"simulation failed: {label}-{kind}; inspect {log_path}")
    if kind == "ring" and "period" not in measures:
        raise RuntimeError(f"oscillation measure failed: {label}; inspect {log_path}")
    return measures


results = []
for environment in ENVIRONMENTS:
    label = environment[0]
    chain = simulate(label, "chain", chain_deck(environment))
    ring = simulate(label, "ring", ring_deck(environment))
    results.append(
        {
            "environment": label,
            "schematic_only": True,
            "input_edge_ps": 5.0,
            "fanout": 1,
            "wn_um": 0.22,
            "wp_um": 0.44,
            "l_um": 0.28,
            "worst_fo1_delay_ps": max(chain["tplh"], chain["tphl"]) * 1e12,
            "worst_20_80_transition_ps": max(chain["trise"], chain["tfall"]) * 1e12,
            "unloaded_three_stage_ring_ghz": 1.0 / ring["period"] / 1e9,
        }
    )

document = {
    "intent": "optimistic transistor/model speed bound, not a realizable CPU timing claim",
    "device": "nfet_03v3/pfet_03v3",
    "limitations": [
        "schematic only",
        "ideal supplies",
        "no extracted interconnect or junction-layout parasitics",
        "ring has no external load or clock distribution",
    ],
    "results": results,
}
(WORK / "result.json").write_text(json.dumps(document, indent=2) + "\n")
print(json.dumps(document, indent=2))
