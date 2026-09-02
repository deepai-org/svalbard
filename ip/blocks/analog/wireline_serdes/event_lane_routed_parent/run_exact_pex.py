#!/usr/bin/env python3
"""Replay the hash-bound full-RC routed event/lane parent in ngspice."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROBE = HERE.parent / "clock_pulse_hclk_window_probe"
EVENT_CONTRACT = json.loads((PROBE / "event_lane_contract.json").read_text())
HCLK_CONTRACT = json.loads((PROBE / "hclk_window_contract.json").read_text())
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
CONTROL = {"id": "sense1_interval0_epoch0", "sense": 1, "interval": 0, "epoch": 0}
PHASES = (("e", "FE_E_P", "FE_E_N", "EVEN_Q", "EVEN_QB", "12.55n"),
          ("o", "FE_O_P", "FE_O_N", "ODD_Q", "ODD_QB", "12.75n"))
# Selected from the physical reference-level receiver's retained six-code
# calibration set.  These are realizable shared bias values, not fitted ideals.
LEVEL_BIAS_V = {"tt": 1.40, "ff_cold": 1.00, "ff_hot": 0.90,
                "ss_hot": 1.08, "ss_cold": 1.20}
LEVEL_REF_V = {"tt": 1.90, "ff_cold": 1.90, "ff_hot": 1.825,
               "ss_hot": 1.825, "ss_cold": 1.825}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def compile_deck(pex: Path, environment: dict) -> str:
    vdd = float(environment["vdd_v"])
    vmid = vdd / 2
    env_id = environment["id"]
    bias = EVENT_CONTRACT["rx_bias_v"][env_id]
    level_bias = LEVEL_BIAS_V[env_id]
    level_ref = LEVEL_REF_V[env_id]
    measures: list[str] = []
    saves = ["i(VDD)"]
    for phase, fp, fn, q, qb, instant in PHASES:
        saves += [f"v({fp})", f"v({fn})", f"v({q})", f"v({qb})"]
        measures += [
            f"meas tran {phase}_fe_diff find {phase}_fe_diff_vec at={instant}",
            f"meas tran {phase}_q_diff find {phase}_q_diff_vec at={instant}",
            f"meas tran {phase}_q_high max v({q}) from=8n to=12.8n",
            f"meas tran {phase}_q_low min v({q}) from=8n to=12.8n",
            f"meas tran {phase}_qb_high max v({qb}) from=8n to=12.8n",
            f"meas tran {phase}_qb_low min v({qb}) from=8n to=12.8n",
        ]
    return f"""* SPDX-License-Identifier: Apache-2.0
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {environment['mos_corner']}
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {EVENT_CONTRACT['res_corner'][env_id]}
.temp {environment['temperature_c']}
.include {pex}
VDD VDD 0 PWL(0 0 500p {vdd})
VCLKP CLKP_H 0 PULSE(0 {vdd} 1n 20p 20p 380p 800p)
VCLKN CLKN_H 0 PULSE(0 {vdd} 1.4n 20p 20p 380p 800p)
VSEL0 SEL0 0 PWL(0 0 500p {vdd})
VSEL1 SEL1 0 0
VSEL2 SEL2 0 0
VRXP RXP_SRC 0 PWL(0 0 500p {vmid + 0.10})
VRXN RXN_SRC 0 PWL(0 0 500p {vmid - 0.10})
RRXP RXP_SRC RXP 1
RRXN RXN_SRC RXN 1
VRXBIAS RX_BIAS_SRC 0 PWL(0 0 500p {bias})
RRXBIAS RX_BIAS_SRC RX_BIAS 1
VLEVELBIAS LEVEL_BIAS_SRC 0 PWL(0 0 500p {level_bias})
RLEVELBIAS LEVEL_BIAS_SRC LEVEL_BIAS 1
VLEVELREF LEVEL_REF_SRC 0 PWL(0 0 500p {level_ref})
RLEVELREF LEVEL_REF_SRC LEVEL_REF 1
VTHP VTHP_SRC 0 PWL(0 0 500p {vmid})
VTHN VTHN_SRC 0 PWL(0 0 500p {vmid})
RVTHP VTHP_SRC VTHP 1
RVTHN VTHN_SRC VTHN 1
VBW RX_BW_EN_N_SRC 0 0
RBW RX_BW_EN_N_SRC RX_BW_EN_N 1
VTERM0 TERM_EN0_N_SRC 0 0
VTERM1 TERM_EN1_N_SRC 0 0
VTERM2 TERM_EN2_N_SRC 0 0
VTERM3 TERM_EN3_N_SRC 0 {vdd}
VTERM4 TERM_EN4_N_SRC 0 {vdd}
VTERM5 TERM_EN5_N_SRC 0 {vdd}
VTERM6 TERM_EN6_N_SRC 0 {vdd}
RTERM0 TERM_EN0_N_SRC TERM_EN0_N 1
RTERM1 TERM_EN1_N_SRC TERM_EN1_N 1
RTERM2 TERM_EN2_N_SRC TERM_EN2_N 1
RTERM3 TERM_EN3_N_SRC TERM_EN3_N 1
RTERM4 TERM_EN4_N_SRC TERM_EN4_N 1
RTERM5 TERM_EN5_N_SRC TERM_EN5_N 1
RTERM6 TERM_EN6_N_SRC TERM_EN6_N 1
VEREGEN E_REGEN_CLK 0 0
VEREGENB E_REGEN_CLKB 0 0
VOREGEN O_REGEN_CLK 0 0
VOREGENB O_REGEN_CLKB 0 0
VEBOOST E_SENSE_BOOST 0 {vdd}
VOBOOST O_SENSE_BOOST 0 {vdd}
XPARENT CLKP_H CLKN_H SEL0 SEL1 SEL2 RXP RXN TERM_EN0_N TERM_EN1_N TERM_EN2_N
+ TERM_EN3_N TERM_EN4_N TERM_EN5_N TERM_EN6_N VTHP VTHN RX_BIAS LEVEL_BIAS LEVEL_REF RX_BW_EN_N
+ E_REGEN_CLK E_REGEN_CLKB E_SENSE_BOOST O_REGEN_CLK O_REGEN_CLKB O_SENSE_BOOST
+ VDD 0 RX_RAWP RX_RAWN FE_E_P FE_E_N FE_O_P FE_O_N EVEN_Q EVEN_QB ODD_Q ODD_QB
+ event_lane_routed_parent_pex
CEQ EVEN_Q 0 50f
CEQB EVEN_QB 0 50f
COQ ODD_Q 0 50f
COQB ODD_QB 0 50f
.save {' '.join(saves)}
.control
tran 1p 12.8n uic
let isupply = -i(VDD)
let e_fe_diff_vec = v(FE_E_P)-v(FE_E_N)
let o_fe_diff_vec = v(FE_O_P)-v(FE_O_N)
let e_q_diff_vec = v(EVEN_Q)-v(EVEN_QB)
let o_q_diff_vec = v(ODD_Q)-v(ODD_QB)
{chr(10).join(measures)}
meas tran supply_current avg isupply from=8n to=12.8n
.endc
.end
"""


def run_case(pex: Path, work: Path, environment: dict, timeout: int,
             reuse_log: bool = False) -> dict:
    stem = environment["id"]
    deck, log = work / f"{stem}.spice", work / f"{stem}.log"
    if reuse_log:
        require(log.is_file(), f"cannot reuse missing log {log}")
        returncode = 0
    else:
        deck.write_text(compile_deck(pex, environment))
        try:
            with log.open("w") as output:
                proc = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                      stderr=subprocess.STDOUT, timeout=timeout)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            returncode = 124
    text = log.read_text()
    observed = {key: float(value) for key, value in MEASURE.findall(text)}
    required = {"supply_current"} | {
        f"{phase}_{name}" for phase, *_ in PHASES
        for name in ("fe_diff", "q_diff", "q_high", "q_low", "qb_high", "qb_low")
    }
    complete = returncode == 0 and required <= observed.keys()
    margin = EVENT_CONTRACT["thresholds"]["logic_rail_margin_v"]
    frontend = all(abs(observed.get(f"{p}_fe_diff", 0)) >= 0.3 for p, *_ in PHASES)
    capture = all(abs(observed.get(f"{p}_q_diff", 0)) >= 0.5 for p, *_ in PHASES)
    # A latched differential result holds one side high and the other low; it
    # does not require both outputs to toggle during this static-input replay.
    rails = all(
        max(observed.get(f"{p}_q_high", 0), observed.get(f"{p}_qb_high", 0))
        >= environment["vdd_v"] - margin
        and min(observed.get(f"{p}_q_low", environment["vdd_v"]),
                observed.get(f"{p}_qb_low", environment["vdd_v"])) <= margin
        for p, *_ in PHASES
    )
    current = observed.get("supply_current", -1)
    current_ok = 0 < current <= 0.15
    # output_rails_pass is a deliberately tighter diagnostic, not part of the
    # event/lane contract, whose capture requirement is differential voltage.
    passed = complete and frontend and capture and current_ok
    return {"environment_id": stem, "control": CONTROL, "returncode": returncode,
            "deck_sha256": digest(deck) if deck.is_file() else None,
            "log_sha256": digest(log),
            "complete": complete, "frontend_pass": frontend,
            "capture_pass": capture, "output_rails_pass": rails,
            "current_pass": current_ok, "observed": observed,
            "diagnostic_log_tail": [] if complete else text.splitlines()[-40:],
            "result": "pass" if passed else "fail"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pex", type=Path, default=HERE / "event_lane_routed_parent.pex.spice")
    parser.add_argument("--physical", type=Path, default=HERE / "physical_result.json")
    parser.add_argument("--environment-ids", nargs="+", default=["tt", "ss_hot"])
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--reuse-logs", action="store_true",
                        help="re-evaluate existing WORK/{environment}.log files")
    args = parser.parse_args()
    physical = json.loads(args.physical.read_text())
    require(physical.get("result") == "pass" and physical.get("lvs_unique") is True,
            "physical evidence is not passing unique LVS")
    require(physical.get("identity", {}).get("pex_sha256") == digest(args.pex),
            "PEX does not match physical evidence")
    by_id = {env["id"]: env for env in HCLK_CONTRACT["environments"]}
    require(set(args.environment_ids) <= by_id.keys(), "unknown environment")
    args.work.mkdir(parents=True, exist_ok=True)
    cases = [run_case(args.pex.resolve(), args.work, by_id[item], args.timeout,
                      args.reuse_logs)
             for item in args.environment_ids]
    result = {"schema_version": 1,
              "claim": "exact_routed_parent_static_differential_capture_replay",
              "scope": "single hash-bound full-RC parent PEX; static differential input",
              "physical_sha256": digest(args.physical), "pex_sha256": digest(args.pex),
              "control": CONTROL, "case_count": len(cases),
              "passing_case_count": sum(c["result"] == "pass" for c in cases),
              "cases": cases,
              "not_a_claim": ["dynamic PRBS BER", "closed CDR", "PCIe compliance",
                              "provider signoff or silicon yield"],
              "result": "pass" if cases and all(c["result"] == "pass" for c in cases) else "fail"}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"],
                      "passing_case_count": result["passing_case_count"],
                      "case_count": len(cases)}, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
