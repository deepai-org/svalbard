#!/usr/bin/env python3
"""Compose extracted events with the extracted regenerative RX/capture parent."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import compile_event_capture_source as event_source
import compile_event_capture_physical_source as event_physical_source
import run_event_capture_schematic as event_runner
import run_hclk_window_probe as base


ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "event_lane_contract.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text())
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
PHASES = ("e", "o")
DEBUG_STAGES = ("hsn", "sb1", "sib", "sdrv")
INTERFACE_DEBUG_STAGES = (
    "if_sense_src", "if_sense_b", "if_boost_src", "if_boost_b",
    "if_clk_src", "if_clk_b", "if_clkb_src", "if_clkb_b",
    "sr_setb", "sr_resetb", "sr_q", "sr_qb", "sr_o0", "sr_o1", "sr_o2",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_physical_pex(pex: Path, physical_path: Path, nested: bool) -> dict:
    physical = json.loads(physical_path.read_text())
    recorded = (physical.get("identity", {}).get("pex_sha256") if nested
                else physical.get("pex_sha256"))
    require(physical.get("result") == "pass", f"{physical_path}: not passing")
    require(recorded == digest(pex), f"{pex}: physical identity mismatch")
    return physical


def compile_deck(event_pex: Path, lane_pex: Path, environment: dict[str, Any],
                 control: dict[str, Any],
                 debug_stages: tuple[str, ...] = DEBUG_STAGES,
                 local_interface_buffer: bool = False,
                 schematic_debug_nodes: tuple[tuple[str, str], ...] = (),
                 direct_sampler_clock: bool = False,
                 sampler_clock_buffer: tuple[int, int] | None = None,
                 sampler_boost_mode: str = "event",
                 capture_clock_buffer: tuple[int, int] | None = None,
                 clock_fanout_pex: Path | None = None) -> str:
    vdd = float(environment["vdd_v"])
    vmid = vdd / 2
    rx_bias = float(CONTRACT["rx_bias_v"][environment["id"]])
    measures = []
    save_vectors = ["i(VDD)"]
    for phase in PHASES:
        upper = phase.upper()
        sense_node = (f"{upper}_SAMPLER_CLK" if (sampler_clock_buffer or
                      clock_fanout_pex) else
                      f"{upper}_{'CLK' if direct_sampler_clock else 'SENSE'}")
        boost_node = ({"event": f"{upper}_BOOST", "on": "VDD",
                       "off": "0"}[sampler_boost_mode])
        clock_nodes = {"clk": f"{upper}_CAPTURE_CLK",
                       "clkb": f"{upper}_CAPTURE_CLKB"}
        for signal in ("sense", "boost", "clk", "clkb"):
            if signal == "sense":
                node = sense_node
            elif signal == "boost":
                node = boost_node
            else:
                node = (clock_nodes[signal] if (capture_clock_buffer or
                        clock_fanout_pex) else
                        f"{upper}_{signal.upper()}")
            save_vectors.append(f"v({node})")
            measures.extend([
                f"meas tran {phase}_{signal}_high max v({node}) from=8n to=12.8n",
                f"meas tran {phase}_{signal}_low min v({node}) from=8n to=12.8n",
            ])
            if local_interface_buffer:
                source_node = f"{upper}_{signal.upper()}_SRC"
                save_vectors.append(f"v({source_node})")
                measures.extend([
                    f"meas tran {phase}_{signal}_src_high max v({source_node}) from=8n to=12.8n",
                    f"meas tran {phase}_{signal}_src_low min v({source_node}) from=8n to=12.8n",
                ])
        measures.extend([
            f"meas tran {phase}_fe_diff find {phase}_fe_diff_vec "
            f"at={'12.55n' if phase == 'e' else '12.75n'}",
            f"meas tran {phase}_q_diff find {phase}_q_diff_vec "
            f"at={'12.55n' if phase == 'e' else '12.75n'}",
        ])
        measures.extend([
            f"meas tran {phase}_sense_low_exit when v({sense_node})={CONTRACT['thresholds']['logic_rail_margin_v']} rise=1 td=12n",
            f"meas tran {phase}_sense_high_enter when v({sense_node})={vdd - CONTRACT['thresholds']['logic_rail_margin_v']:.6f} rise=1 td=12n",
            f"meas tran {phase}_sense_high_exit when v({sense_node})={vdd - CONTRACT['thresholds']['logic_rail_margin_v']:.6f} fall=1 td=12n",
            f"meas tran {phase}_sense_low_enter when v({sense_node})={CONTRACT['thresholds']['logic_rail_margin_v']} fall=1 td=12n",
        ])
        save_vectors.extend([
            f"v(FE_{upper}_P)", f"v(FE_{upper}_N)",
            f"v({'EVEN' if phase == 'e' else 'ODD'}_Q)",
            f"v({'EVEN' if phase == 'e' else 'ODD'}_QB)",
        ])
        for stage in debug_stages:
            node = f"xevent.DBG_{upper}_{stage.upper()}"
            save_vectors.append(f"v({node})")
            measures.extend([
                f"meas tran {phase}_dbg_{stage}_high max v({node}) from=8n to=12.8n",
                f"meas tran {phase}_dbg_{stage}_low min v({node}) from=8n to=12.8n",
            ])
    buffer_subckt = "" if not (local_interface_buffer or
                                (sampler_clock_buffer and not clock_fanout_pex) or
                                (capture_clock_buffer and not clock_fanout_pex)) else """
.subckt lane_if_inv A Y VDD VSS params: MP=1 MN=1
XP Y A VDD VDD pfet_03v3 w=8u l=0.28u m={MP}
XN Y A VSS VSS nfet_03v3 w=8u l=0.28u m={MN}
.ends lane_if_inv
"""
    if local_interface_buffer:
        buffer_subckt += """
.subckt lane_if_buffer A Y VDD VSS
XI0 A B VDD VSS lane_if_inv MP=4 MN=4
XI1 B Y VDD VSS lane_if_inv MP=16 MN=16
.ends lane_if_buffer
"""
    if sampler_clock_buffer and not clock_fanout_pex:
        sampler_pre_mult, sampler_out_mult = sampler_clock_buffer
        buffer_subckt += f"""
.subckt sampler_clock_buffer A Y VDD VSS
XI0 A B VDD VSS lane_if_inv MP={sampler_pre_mult} MN={sampler_pre_mult}
XI1 B Y VDD VSS lane_if_inv MP={sampler_out_mult} MN={sampler_out_mult}
.ends sampler_clock_buffer
"""
    if capture_clock_buffer and not clock_fanout_pex:
        capture_pre_mult, capture_out_mult = capture_clock_buffer
        buffer_subckt += f"""
.subckt capture_clock_buffer A Y VDD VSS
XI0 A B VDD VSS lane_if_inv MP={capture_pre_mult} MN={capture_pre_mult}
XI1 B Y VDD VSS lane_if_inv MP={capture_out_mult} MN={capture_out_mult}
.ends capture_clock_buffer
"""
    event_outputs = ("E_SENSE_SRC E_BOOST_SRC E_CLK_SRC E_CLKB_SRC "
                     "O_SENSE_SRC O_BOOST_SRC O_CLK_SRC O_CLKB_SRC"
                     if local_interface_buffer else
                     "E_SENSE E_BOOST E_CLK E_CLKB O_SENSE O_BOOST O_CLK O_CLKB")
    buffer_instances = "" if not local_interface_buffer else """
XEB_S E_SENSE_SRC E_SENSE VDD 0 lane_if_buffer
XEB_B E_BOOST_SRC E_BOOST VDD 0 lane_if_buffer
XEB_C E_CLK_SRC E_CLK VDD 0 lane_if_buffer
XEB_CB E_CLKB_SRC E_CLKB VDD 0 lane_if_buffer
XOB_S O_SENSE_SRC O_SENSE VDD 0 lane_if_buffer
XOB_B O_BOOST_SRC O_BOOST VDD 0 lane_if_buffer
XOB_C O_CLK_SRC O_CLK VDD 0 lane_if_buffer
XOB_CB O_CLKB_SRC O_CLKB VDD 0 lane_if_buffer
"""
    sampler_buffer_instances = "" if not sampler_clock_buffer or clock_fanout_pex else """
XESB E_CLK E_SAMPLER_CLK VDD 0 sampler_clock_buffer
XOSB O_CLK O_SAMPLER_CLK VDD 0 sampler_clock_buffer
"""
    capture_buffer_instances = "" if not capture_clock_buffer or clock_fanout_pex else """
XECB E_CLK E_CAPTURE_CLK VDD 0 capture_clock_buffer
XECBB E_CLKB E_CAPTURE_CLKB VDD 0 capture_clock_buffer
XOCB O_CLK O_CAPTURE_CLK VDD 0 capture_clock_buffer
XOCBB O_CLKB O_CAPTURE_CLKB VDD 0 capture_clock_buffer
"""
    physical_fanout_instance = "" if not clock_fanout_pex else """
XFANOUT E_CLK E_CLKB O_CLK O_CLKB VDD 0 E_SAMPLER_CLK E_CAPTURE_CLK
+ E_CAPTURE_CLKB O_SAMPLER_CLK O_CAPTURE_CLK O_CAPTURE_CLKB local_clock_fanout_pex
"""
    use_capture_fanout = bool(capture_clock_buffer or clock_fanout_pex)
    e_capture_clk = "E_CAPTURE_CLK" if use_capture_fanout else "E_CLK"
    e_capture_clkb = "E_CAPTURE_CLKB" if use_capture_fanout else "E_CLKB"
    o_capture_clk = "O_CAPTURE_CLK" if use_capture_fanout else "O_CLK"
    o_capture_clkb = "O_CAPTURE_CLKB" if use_capture_fanout else "O_CLKB"
    for label, node in schematic_debug_nodes:
        measures.extend([
            f"meas tran sch_{label}_high max v({node}) from=8n to=12.8n",
            f"meas tran sch_{label}_low min v({node}) from=8n to=12.8n",
        ])
        if label.endswith(("_q", "_qb")):
            measures.extend([
                f"meas tran sch_{label}_low_exit when v({node})={CONTRACT['thresholds']['logic_rail_margin_v']} rise=1 td=12n",
                f"meas tran sch_{label}_high_enter when v({node})={vdd - CONTRACT['thresholds']['logic_rail_margin_v']:.6f} rise=1 td=12n",
                f"meas tran sch_{label}_high_exit when v({node})={vdd - CONTRACT['thresholds']['logic_rail_margin_v']:.6f} fall=1 td=12n",
                f"meas tran sch_{label}_low_enter when v({node})={CONTRACT['thresholds']['logic_rail_margin_v']} fall=1 td=12n",
            ])
    e_sampler_sense = ("E_SAMPLER_CLK" if (sampler_clock_buffer or clock_fanout_pex) else
                       "E_CLK" if direct_sampler_clock else "E_SENSE")
    e_sampler_boost = {"event": "E_BOOST", "on": "VDD", "off": "0"}[
        sampler_boost_mode]
    o_sampler_sense = ("O_SAMPLER_CLK" if (sampler_clock_buffer or clock_fanout_pex) else
                       "O_CLK" if direct_sampler_clock else "O_SENSE")
    o_sampler_boost = {"event": "O_BOOST", "on": "VDD", "off": "0"}[
        sampler_boost_mode]
    return f"""* SPDX-License-Identifier: Apache-2.0
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {environment['mos_corner']}
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {CONTRACT['res_corner'][environment['id']]}
.temp {environment['temperature_c']}
.include {event_pex}
.include {lane_pex}
{f'.include {clock_fanout_pex}' if clock_fanout_pex else ''}
{buffer_subckt}
VDD VDD 0 PWL(0 0 500p {vdd:.6f})
VCLKP CLKP_H 0 PULSE(0 {vdd:.6f} 1n 20p 20p 380p 800p)
VCLKN CLKN_H 0 PULSE(0 {vdd:.6f} 1.4n 20p 20p 380p 800p)
VSEL0 SEL0 0 PWL(0 0 500p {vdd if control['sense'] else 0:.6f})
VSEL1 SEL1 0 PWL(0 0 500p {vdd if control['interval'] else 0:.6f})
VSEL2 SEL2 0 PWL(0 0 500p {vdd if control['epoch'] else 0:.6f})
VRXP RXP_SRC 0 PWL(0 0 500p {vmid + 0.10:.6f})
VRXN RXN_SRC 0 PWL(0 0 500p {vmid - 0.10:.6f})
RRXP RXP_SRC RXP 1
RRXN RXN_SRC RXN 1
VRXBIAS RX_BIAS_SRC 0 PWL(0 0 500p {rx_bias:.6f})
RRXBIAS RX_BIAS_SRC RX_BIAS 1
VTHP VTHP_SRC 0 PWL(0 0 500p {vmid:.6f})
VTHN VTHN_SRC 0 PWL(0 0 500p {vmid:.6f})
RVTHP VTHP_SRC VTHP 1
RVTHN VTHN_SRC VTHN 1
VBW RX_BW_EN_N_SRC 0 0
RBW RX_BW_EN_N_SRC RX_BW_EN_N 1
VTERM0 TERM_EN0_N_SRC 0 0
VTERM1 TERM_EN1_N_SRC 0 0
VTERM2 TERM_EN2_N_SRC 0 0
VTERM3 TERM_EN3_N_SRC 0 {vdd:.6f}
VTERM4 TERM_EN4_N_SRC 0 {vdd:.6f}
VTERM5 TERM_EN5_N_SRC 0 {vdd:.6f}
VTERM6 TERM_EN6_N_SRC 0 {vdd:.6f}
RTERM0 TERM_EN0_N_SRC TERM_EN0_N 1
RTERM1 TERM_EN1_N_SRC TERM_EN1_N 1
RTERM2 TERM_EN2_N_SRC TERM_EN2_N 1
RTERM3 TERM_EN3_N_SRC TERM_EN3_N 1
RTERM4 TERM_EN4_N_SRC TERM_EN4_N 1
RTERM5 TERM_EN5_N_SRC TERM_EN5_N 1
RTERM6 TERM_EN6_N_SRC TERM_EN6_N 1
XEVENT CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD 0 {event_outputs}
+ retimed_event_capture_bridge_pex
{buffer_instances}
{sampler_buffer_instances}
{capture_buffer_instances}
{physical_fanout_instance}
REREGEN E_REGEN_CLK 0 1m
REREGENB E_REGEN_CLKB 0 1m
ROREGEN O_REGEN_CLK 0 1m
ROREGENB O_REGEN_CLKB 0 1m
XLANE RXP RXN TERM_EN0_N TERM_EN1_N TERM_EN2_N TERM_EN3_N TERM_EN4_N
+ TERM_EN5_N TERM_EN6_N VTHP VTHN RX_BIAS RX_BW_EN_N
+ {e_sampler_sense} E_REGEN_CLK E_REGEN_CLKB {e_capture_clk} {e_capture_clkb} {e_sampler_boost}
+ {o_sampler_sense} O_REGEN_CLK O_REGEN_CLKB {o_capture_clk} {o_capture_clkb} {o_sampler_boost}
+ VDD 0 RX_RAWP RX_RAWN FE_E_P FE_E_N FE_O_P FE_O_N
+ EVEN_Q EVEN_QB ODD_Q ODD_QB lane_rx_regenerative_capture_pex
CEQ EVEN_Q 0 50f
CEQB EVEN_QB 0 50f
COQ ODD_Q 0 50f
COQB ODD_QB 0 50f
.save {' '.join(dict.fromkeys(save_vectors))}
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


def run_case(spec: tuple) -> dict:
    (event_pex, lane_pex, work, environment, control, debug_stages,
     local_interface_buffer, *optional) = spec
    schematic_debug_nodes = optional[0] if optional else ()
    direct_sampler_clock = optional[1] if len(optional) > 1 else False
    sampler_clock_buffer = optional[2] if len(optional) > 2 else None
    sampler_boost_mode = optional[3] if len(optional) > 3 else "event"
    capture_clock_buffer = optional[4] if len(optional) > 4 else None
    clock_fanout_pex = optional[5] if len(optional) > 5 else None
    stem = f"{environment['id']}_{control['id']}"
    deck = work / f"{stem}.spice"
    log = work / f"{stem}.log"
    deck.write_text(compile_deck(event_pex, lane_pex, environment, control,
                                 debug_stages, local_interface_buffer,
                                 schematic_debug_nodes, direct_sampler_clock,
                                 sampler_clock_buffer, sampler_boost_mode,
                                 capture_clock_buffer, clock_fanout_pex))
    try:
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=900,
                                 check=False)
        returncode = run.returncode
    except subprocess.TimeoutExpired:
        returncode = 124
    log_text = log.read_text()
    observed = {key: float(value)
                for key, value in MEASURE.findall(log_text)}
    for phase in PHASES:
        low_enter = observed.get(f"{phase}_sense_low_enter")
        low_exit = observed.get(f"{phase}_sense_low_exit")
        high_enter = observed.get(f"{phase}_sense_high_enter")
        high_exit = observed.get(f"{phase}_sense_high_exit")
        if low_enter is not None and low_exit is not None:
            observed[f"{phase}_sense_low_rail_time"] = (low_exit - low_enter) % 8e-10
        if high_enter is not None and high_exit is not None:
            observed[f"{phase}_sense_high_rail_time"] = (high_exit - high_enter) % 8e-10
    required = {"supply_current"}
    required |= {f"sch_{label}_{bound}" for label, _ in schematic_debug_nodes
                 for bound in ("high", "low")}
    required |= {f"sch_{label}_{edge}" for label, _ in schematic_debug_nodes
                 if label.endswith(("_q", "_qb"))
                 for edge in ("low_exit", "high_enter", "high_exit", "low_enter")}
    for phase in PHASES:
        required |= {f"{phase}_{signal}_{bound}"
                     for signal in ("sense", "boost", "clk", "clkb")
                     for bound in ("high", "low")}
        if local_interface_buffer:
            required |= {f"{phase}_{signal}_src_{bound}"
                         for signal in ("sense", "boost", "clk", "clkb")
                         for bound in ("high", "low")}
        required |= {f"{phase}_fe_diff", f"{phase}_q_diff"}
        required |= {f"{phase}_sense_{edge}" for edge in
                     ("low_enter", "low_exit", "high_enter", "high_exit")}
        required |= {
                     f"{phase}_sense_low_rail_time",
                     f"{phase}_sense_high_rail_time"}
        required |= {f"{phase}_dbg_{stage}_{bound}"
                     for stage in debug_stages for bound in ("high", "low")}
    complete = returncode == 0 and required <= observed.keys()
    for label, _ in schematic_debug_nodes:
        if label.endswith(("_q", "_qb")) and all(
                f"sch_{label}_{edge}" in observed for edge in
                ("low_exit", "high_enter", "high_exit", "low_enter")):
            observed[f"sch_{label}_low_rail_time"] = (
                observed[f"sch_{label}_low_exit"]
                - observed[f"sch_{label}_low_enter"]) % 8e-10
            observed[f"sch_{label}_high_rail_time"] = (
                observed[f"sch_{label}_high_exit"]
                - observed[f"sch_{label}_high_enter"]) % 8e-10
    vdd = float(environment["vdd_v"])
    margin = float(CONTRACT["thresholds"]["logic_rail_margin_v"])
    dynamic_signals = ("sense", "clk", "clkb") + (("boost",)
                      if sampler_boost_mode == "event" else ())
    rails = all(
        observed.get(f"{phase}_{signal}_high", 0) >= vdd - margin
        and observed.get(f"{phase}_{signal}_low", vdd) <= margin
        for phase in PHASES for signal in dynamic_signals
    )
    if sampler_boost_mode == "on":
        rails &= all(observed.get(f"{phase}_boost_low", 0) >= vdd - margin
                     for phase in PHASES)
    elif sampler_boost_mode == "off":
        rails &= all(observed.get(f"{phase}_boost_high", vdd) <= margin
                     for phase in PHASES)
    if local_interface_buffer:
        rails &= all(
            observed.get(f"{phase}_{signal}_src_high", 0) >= vdd - margin
            and observed.get(f"{phase}_{signal}_src_low", vdd) <= margin
            for phase in PHASES for signal in ("sense", "boost", "clk", "clkb")
        )
    intervals = all(
        CONTRACT["thresholds"][f"sense_{state}_rail_time_s"][0]
        <= observed.get(f"{phase}_sense_{state}_rail_time", -1)
        <= CONTRACT["thresholds"][f"sense_{state}_rail_time_s"][1]
        for phase in PHASES for state in ("low", "high")
    )
    frontend = all(abs(observed.get(f"{phase}_fe_diff", 0)) >=
                   CONTRACT["thresholds"]["frontend_differential_v"]
                   for phase in PHASES)
    capture = all(abs(observed.get(f"{phase}_q_diff", 0)) >=
                  CONTRACT["thresholds"]["capture_differential_v"]
                  for phase in PHASES)
    current = observed.get("supply_current")
    current_bounds = CONTRACT["thresholds"]["average_supply_current_a"]
    passed = (complete and rails and intervals and frontend and capture and current is not None
              and current_bounds[0] < current <= current_bounds[1])
    return {"case_id": stem, "environment_id": environment["id"],
            "code_id": control["id"], "control": control,
            "returncode": returncode,
            "diagnostic_log_tail": [] if complete else log_text.splitlines()[-40:],
            "complete": complete, "rails_pass": rails,
            "sense_intervals_pass": intervals,
            "frontend_pass": frontend, "capture_pass": capture,
            "observed": observed, "result": "pass" if passed else "fail"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-pex", required=True, type=Path)
    parser.add_argument("--event-physical", required=True, type=Path)
    parser.add_argument(
        "--event-schematic",
        type=Path,
        help="exact schematic lowered into the event PEX; requires --event-source-revision",
    )
    parser.add_argument("--event-source-revision")
    parser.add_argument("--lane-pex", required=True, type=Path)
    parser.add_argument("--lane-physical", required=True, type=Path)
    parser.add_argument("--environment-ids", nargs="+")
    parser.add_argument("--control-ids", nargs="+")
    parser.add_argument("--case-ids", nargs="+",
                        help="explicit ENVIRONMENT:CONTROL pairs")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument(
        "--skip-debug-stages", action="store_true",
        help="omit topology-specific internal probes; functional checks remain unchanged",
    )
    parser.add_argument(
        "--interface-debug-stages", action="store_true",
        help="probe physically labeled source and midpoint interface-buffer nodes",
    )
    parser.add_argument(
        "--local-interface-buffer", action="store_true",
        help="insert a realizable two-stage CMOS buffer at each lane control input",
    )
    parser.add_argument(
        "--direct-sampler-clock", action="store_true",
        help="drive sampler sense directly from its extracted full-duty capture clock",
    )
    parser.add_argument(
        "--sampler-clock-buffer", nargs=2, type=int, metavar=("PRE", "OUT"),
        help="branch the extracted capture clock through a local two-stage sampler buffer",
    )
    parser.add_argument(
        "--sampler-clock-stages", nargs="+", type=int,
        help="record the stage multipliers of an exact physical sampler fanout",
    )
    parser.add_argument("--sampler-final-p-mult", type=int,
                        help="record an asymmetric final PMOS multiplier")
    parser.add_argument("--sampler-final-n-mult", type=int,
                        help="record the final NMOS multiplier")
    parser.add_argument(
        "--sampler-boost-mode", choices=("event", "on", "off"), default="event",
        help="use the event BOOST waveform or a static rail trim at the sampler",
    )
    parser.add_argument(
        "--capture-clock-buffer", nargs=2, type=int, metavar=("PRE", "OUT"),
        help="restore both extracted capture-clock polarities with local two-stage buffers",
    )
    parser.add_argument("--clock-fanout-pex", type=Path,
                        help="exact extracted six-branch local clock fanout")
    parser.add_argument("--clock-fanout-physical", type=Path,
                        help="hash-bound physical record for --clock-fanout-pex")
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(1 <= args.jobs <= 8, "jobs must be 1--8")
    require((args.clock_fanout_pex is None) == (args.clock_fanout_physical is None),
            "clock fanout PEX and physical record must be supplied together")
    require(not (args.direct_sampler_clock and args.sampler_clock_buffer),
            "direct sampler clock and sampler clock buffer are mutually exclusive")
    if args.sampler_clock_buffer:
        require(all(1 <= value <= 64 for value in args.sampler_clock_buffer),
                "sampler clock buffer multipliers must be 1--64")
    if args.sampler_clock_stages:
        require(all(1 <= value <= 64 for value in args.sampler_clock_stages),
                "sampler clock stage multipliers must be 1--64")
    if args.sampler_final_p_mult is not None:
        require(1 <= args.sampler_final_p_mult <= 64,
                "sampler final PMOS multiplier must be 1--64")
    if args.sampler_final_n_mult is not None:
        require(1 <= args.sampler_final_n_mult <= 64,
                "sampler final NMOS multiplier must be 1--64")
    if args.capture_clock_buffer:
        require(all(1 <= value <= 64 for value in args.capture_clock_buffer),
                "capture clock buffer multipliers must be 1--64")
    require((args.event_schematic is None) == (args.event_source_revision is None),
            "event schematic and source revision must be supplied together")
    event_physical = require_physical_pex(args.event_pex, args.event_physical, True)
    if args.event_schematic is None:
        expected_revision = CONTRACT["event_source_revision"]
        expected_schematic_sha256 = hashlib.sha256(
            event_physical_source.compile_source().encode()).hexdigest()
    else:
        expected_revision = args.event_source_revision
        expected_schematic_sha256 = digest(args.event_schematic)
    require(event_physical.get("source_revision") == expected_revision,
            "event physical source revision mismatch")
    require(event_physical.get("identity", {}).get("schematic_sha256")
            == expected_schematic_sha256,
            "event physical schematic identity mismatch")
    lane_physical = require_physical_pex(args.lane_pex, args.lane_physical, False)
    fanout_physical = None
    if args.clock_fanout_pex:
        fanout_physical = require_physical_pex(
            args.clock_fanout_pex, args.clock_fanout_physical, True)
        require(fanout_physical.get("top") == "local_clock_fanout",
                "unexpected clock fanout physical top")
        selected = fanout_physical.get("selected_candidate", {})
        if "sampler_stage_mults" in selected:
            require(args.sampler_clock_stages == selected["sampler_stage_mults"],
                    "physical fanout sampler-stage identity mismatch")
            require(args.sampler_clock_buffer is None,
                    "physical staged fanout cannot also declare a two-stage buffer")
            require(args.sampler_final_p_mult == selected.get("sampler_final_p_mult"),
                    "physical fanout final-PMOS identity mismatch")
            require(args.sampler_final_n_mult == selected.get("sampler_final_n_mult"),
                    "physical fanout final-NMOS identity mismatch")
        else:
            require(args.sampler_clock_buffer == [selected.get("sampler_pre_mult"),
                                                   selected.get("sampler_output_mult")],
                    "physical fanout sampler-buffer identity mismatch")
        require(args.capture_clock_buffer == [selected.get("capture_pre_mult"),
                                               selected.get("capture_output_mult")],
                "physical fanout capture-buffer identity mismatch")
    environments = list(base.CONTRACT["environments"])
    controls = list(event_runner.CONTROLS)
    require(not args.case_ids or not (args.environment_ids or args.control_ids),
            "case-ids cannot be combined with environment/control filters")
    if args.environment_ids:
        wanted = set(args.environment_ids)
        require(wanted <= {item["id"] for item in environments},
                "unknown environment id")
        environments = [item for item in environments if item["id"] in wanted]
    if args.control_ids:
        wanted = set(args.control_ids)
        require(wanted <= {item["id"] for item in controls}, "unknown control id")
        controls = [item for item in controls if item["id"] in wanted]
    args.work.mkdir(parents=True, exist_ok=True)
    if args.case_ids:
        environment_by_id = {item["id"]: item for item in environments}
        control_by_id = {item["id"]: item for item in controls}
        pairs = []
        for case_id in args.case_ids:
            require(case_id.count(":") == 1, "case id must be ENVIRONMENT:CONTROL")
            environment_id, control_id = case_id.split(":")
            require(environment_id in environment_by_id, "unknown case environment")
            require(control_id in control_by_id, "unknown case control")
            pairs.append((environment_by_id[environment_id], control_by_id[control_id]))
        require(len(pairs) == len(set(args.case_ids)), "duplicate case id")
        environments = [environment_by_id[item]
                        for item in dict.fromkeys(env for env, _ in
                                                 (case_id.split(":") for case_id in args.case_ids))]
    else:
        pairs = [(environment, control)
                 for environment in environments for control in controls]
    require(not (args.skip_debug_stages and args.interface_debug_stages),
            "cannot skip and request interface debug stages together")
    debug_stages = (INTERFACE_DEBUG_STAGES if args.interface_debug_stages else
                    (() if args.skip_debug_stages else DEBUG_STAGES))
    specs = [(args.event_pex, args.lane_pex, args.work, environment, control,
              debug_stages, args.local_interface_buffer, (),
              args.direct_sampler_clock,
              tuple(args.sampler_clock_buffer) if args.sampler_clock_buffer else None,
              args.sampler_boost_mode,
              tuple(args.capture_clock_buffer) if args.capture_clock_buffer else None,
              args.clock_fanout_pex)
             for environment, control in pairs]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(run_case, specs))
    coverage = {environment["id"]: [case["code_id"] for case in cases
                                     if case["environment_id"] == environment["id"]
                                     and case["result"] == "pass"]
                for environment in environments}
    result = {
        "schema_version": 1,
        "claim": "extracted_event_bridge_into_routed_regenerative_lane_static_input",
        "scope": "unrouted composition of two exact physically bound PEX macros",
        "contract_sha256": digest(CONTRACT_PATH),
        "event_pex_sha256": digest(args.event_pex),
        "event_physical_sha256": digest(args.event_physical),
        "lane_pex_sha256": digest(args.lane_pex),
        "lane_physical_sha256": digest(args.lane_physical),
        "clock_fanout_pex_sha256": (digest(args.clock_fanout_pex)
                                     if args.clock_fanout_pex else None),
        "clock_fanout_physical_sha256": (digest(args.clock_fanout_physical)
                                          if args.clock_fanout_physical else None),
        "event_source_revision": event_physical["source_revision"],
        "lane_claim": lane_physical["claim"],
        "debug_stages": list(debug_stages),
        "local_interface_buffer": args.local_interface_buffer,
        "direct_sampler_clock": args.direct_sampler_clock,
        "sampler_clock_buffer": args.sampler_clock_buffer,
        "sampler_clock_stages": args.sampler_clock_stages,
        "sampler_final_p_mult": args.sampler_final_p_mult,
        "sampler_final_n_mult": args.sampler_final_n_mult,
        "sampler_boost_mode": args.sampler_boost_mode,
        "capture_clock_buffer": args.capture_clock_buffer,
        "clock_fanout_claim": (fanout_physical["claim"]
                                if fanout_physical else None),
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "environment_code_coverage": coverage,
        "cases": cases,
        "not_a_claim": CONTRACT["not_a_claim"],
        "result": "pass" if coverage and all(coverage.values()) else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"],
                      "passing_case_count": result["passing_case_count"],
                      "environment_code_coverage": coverage}, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
