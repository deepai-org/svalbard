#!/usr/bin/env python3
"""Screen full-duty retimed events directly into extracted split capture."""

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
import compile_event_capture_physical_source as physical_source
import run_hclk_window_probe as base


ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "event_capture_contract.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text())
PHASES = ("e", "o")
UI = float(base.CONTRACT["unit_interval_s"])
CONTROLS = [
    {"id": f"sense{sense}_interval{interval}_epoch{epoch}",
     "sense": sense, "interval": interval, "epoch": epoch}
    for sense in (0, 1) for interval in (0, 1) for epoch in (0, 1)
]
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
INTERNAL_STAGES = tuple(CONTRACT["internal_stages"])


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_contract() -> None:
    require(CONTRACT.get("schema_version") == 1, "unsupported event contract")
    require(CONTRACT.get("source_revision") == event_source.SOURCE_REVISION,
            "event source revision mismatch")
    require(set(CONTRACT["control_semantics"]) == {"SEL0", "SEL1", "SEL2"},
            "event contract must bind three controls")
    require(len(INTERNAL_STAGES) == len(set(INTERNAL_STAGES))
            and all(re.fullmatch(r"[a-z][a-z0-9_]*", stage)
                    for stage in INTERNAL_STAGES),
            "event contract internal stages must be unique semantic names")


validate_contract()


def compile_deck(source: Path, bridge: Path | None, capture: Path,
                 environment: dict[str, Any], control: dict[str, Any],
                 combined_pex: bool = False,
                 internal_probes: bool = False) -> str:
    vdd = float(environment["vdd_v"])
    loads = CONTRACT["loads"]
    measures = []
    for phase in PHASES:
        upper = phase.upper()
        rail_signals = ("sense", "boost", "clk", "clkb") if combined_pex else \
                       ("sense", "boost", "start", "end", "clk", "clkb")
        for signal in rail_signals:
            node = f"{upper}_{signal.upper()}"
            measures.extend([
                f"meas tran {phase}_{signal}_high max v({node}) from=8n to=12.8n",
                f"meas tran {phase}_{signal}_low min v({node}) from=8n to=12.8n",
            ])
        edge_signals = [("sense", "rise"), ("sense", "fall"),
                        ("clkb", "fall"), ("clkb", "rise"),
                        ("clk", "rise"), ("clk", "fall")]
        if not combined_pex:
            edge_signals[2:2] = [("start", "fall"), ("start", "rise"),
                                 ("end", "fall"), ("end", "rise")]
        for signal, edge in edge_signals:
            node = f"{upper}_{signal.upper()}"
            measures.append(
                f"meas tran {phase}_{signal}_{edge} when v({node})={vdd / 2:.6f} "
                f"{edge}=1 td=8n")
        measures.append(
            f"meas tran {phase}_clk_rise2 when v({upper}_CLK)={vdd / 2:.6f} "
            "rise=2 td=8n")
        if internal_probes:
            require(combined_pex, "internal event probes require combined PEX")
            for stage in INTERNAL_STAGES:
                node = f"xsource.DBG_{upper}_{stage.upper()}"
                measures.extend([
                    f"meas tran {phase}_dbg_{stage}_high max v({node}) from=8n to=12.8n",
                    f"meas tran {phase}_dbg_{stage}_low min v({node}) from=8n to=12.8n",
                    f"meas tran {phase}_dbg_{stage}_rise when v({node})={vdd / 2:.6f} rise=1 td=8n",
                    f"meas tran {phase}_dbg_{stage}_fall when v({node})={vdd / 2:.6f} fall=1 td=8n",
                ])
    if combined_pex:
        source_includes = f".include {source}\n.include {capture}"
        source_instances = f"""XSOURCE CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD 0
+ E_SENSE E_BOOST E_CLK E_CLKB O_SENSE O_BOOST O_CLK O_CLKB
+ {physical_source.TOP}_pex"""
    else:
        require(bridge is not None, "schematic replay requires a bridge")
        source_includes = f".include {source}\n.include {bridge}\n.include {capture}"
        source_instances = f"""XSOURCE CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD 0
+ E_SENSE E_BOOST E_START E_END O_SENSE O_BOOST O_START O_END {event_source.TOP}
XBRIDGE E_START E_END O_START O_END E_CLK E_CLKB O_CLK O_CLKB VDD 0
+ event_capture_bridge"""
    return f"""* SPDX-License-Identifier: Apache-2.0
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {environment['mos_corner']}
.temp {environment['temperature_c']}
{source_includes}
VDD VDD 0 PWL(0 0 500p {vdd:.6f})
VSEL0 SEL0 0 PWL(0 0 500p {vdd if control['sense'] else 0:.6f})
VSEL1 SEL1 0 PWL(0 0 500p {vdd if control['interval'] else 0:.6f})
VSEL2 SEL2 0 PWL(0 0 500p {vdd if control['epoch'] else 0:.6f})
VCLKP CLKP_H 0 PULSE(0 {vdd:.6f} 1n 20p 20p 380p 800p)
VCLKN CLKN_H 0 PULSE(0 {vdd:.6f} 1.4n 20p 20p 380p 800p)
VSRC_ED ED_SRC 0 PWL(0 0 500p {vdd:.6f})
VSRC_EDB EDB_SRC 0 0
VSRC_OD OD_SRC 0 0
VSRC_ODB ODB_SRC 0 PWL(0 0 500p {vdd:.6f})
RED ED_SRC EVEN_D 1
REDB EDB_SRC EVEN_DB 1
ROD OD_SRC ODD_D 1
RODB ODB_SRC ODD_DB 1
{source_instances}
CE_SENSE E_SENSE 0 {loads['sense_f']}
CE_BOOST E_BOOST 0 {loads['boost_f']}
CO_SENSE O_SENSE 0 {loads['sense_f']}
CO_BOOST O_BOOST 0 {loads['boost_f']}
XCAP EVEN_D EVEN_DB ODD_D ODD_DB E_CLK E_CLKB O_CLK O_CLKB VDD 0
+ EVEN_Q EVEN_QB ODD_Q ODD_QB deserializer_split_capture_pex
CEQ EVEN_Q 0 {loads['capture_output_f']}
CEQB EVEN_QB 0 {loads['capture_output_f']}
COQ ODD_Q 0 {loads['capture_output_f']}
COQB ODD_QB 0 {loads['capture_output_f']}
.control
tran 1p 12.8n uic
let isupply = -i(VDD)
let e_q_diff = v(EVEN_Q)-v(EVEN_QB)
let o_q_diff = v(ODD_Q)-v(ODD_QB)
{chr(10).join(measures)}
meas tran e_q_diff find e_q_diff at=12.55n
meas tran o_q_diff find o_q_diff at=12.75n
meas tran supply_current avg isupply from=8n to=12.8n
.endc
.end
"""


def cyclic_delta(later: float, earlier: float) -> float:
    return (later - earlier) % UI


def run_case(spec: tuple[Path, Path | None, Path, Path, dict[str, Any],
                         dict[str, Any], bool, bool]) -> dict[str, Any]:
    (source, bridge, capture, work, environment, control, combined_pex,
     internal_probes) = spec
    stem = f"{environment['id']}_{control['id']}"
    deck, log = work / f"{stem}.spice", work / f"{stem}.log"
    deck.write_text(compile_deck(source, bridge, capture, environment, control,
                                 combined_pex, internal_probes))
    try:
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=300,
                                 check=False)
        returncode = run.returncode
    except subprocess.TimeoutExpired:
        returncode = 124
    observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
    required = {"supply_current", "e_q_diff", "o_q_diff"}
    for phase in PHASES:
        rail_signals = ("sense", "boost", "clk", "clkb") if combined_pex else \
                       ("sense", "boost", "start", "end", "clk", "clkb")
        required |= {f"{phase}_{signal}_{level}"
                     for signal in rail_signals
                     for level in ("high", "low")}
        edge_signals = [("sense", "rise"), ("sense", "fall"),
                        ("clkb", "fall"), ("clkb", "rise"),
                        ("clk", "rise"), ("clk", "fall")]
        if not combined_pex:
            edge_signals[2:2] = [("start", "fall"), ("start", "rise"),
                                 ("end", "fall"), ("end", "rise")]
        required |= {f"{phase}_{signal}_{edge}"
                     for signal, edge in edge_signals}
        required.add(f"{phase}_clk_rise2")
        if internal_probes:
            required |= {f"{phase}_dbg_{stage}_{measure}"
                         for stage in INTERNAL_STAGES
                         for measure in ("high", "low", "rise", "fall")}
    complete = returncode == 0 and required <= observed.keys()
    thresholds = CONTRACT["thresholds"]
    vdd = float(environment["vdd_v"])
    margin = float(thresholds["logic_rail_margin_v"])
    phase_metrics = {}
    phase_pass = {}
    for phase in PHASES:
        metrics = {
            "sense_width_s": cyclic_delta(observed.get(f"{phase}_sense_fall", 0),
                                            observed.get(f"{phase}_sense_rise", 0)),
            "entry_skew_s": cyclic_delta(observed.get(f"{phase}_clk_rise", 0),
                                           observed.get(f"{phase}_clkb_fall", 0)),
            "exit_skew_s": cyclic_delta(observed.get(f"{phase}_clk_fall", 0),
                                          observed.get(f"{phase}_clkb_rise", 0)),
            "capture_overlap_s": cyclic_delta(observed.get(f"{phase}_clkb_rise", 0),
                                                observed.get(f"{phase}_clk_rise", 0)),
            "clock_period_s": observed.get(f"{phase}_clk_rise2", 0)
                              - observed.get(f"{phase}_clk_rise", 0),
            "capture_entry_from_sense_rise_s": cyclic_delta(
                observed.get(f"{phase}_clkb_fall", 0),
                observed.get(f"{phase}_sense_rise", 0)),
            "dead_time_s": cyclic_delta(observed.get(f"{phase}_clkb_fall", 0),
                                         observed.get(f"{phase}_sense_fall", 0)),
        }
        phase_metrics[phase] = metrics
        bounded = all(
            thresholds[name][0] <= metrics[name] <= thresholds[name][1]
            for name in ("entry_skew_s", "exit_skew_s", "capture_overlap_s",
                         "clock_period_s"))
        bounded &= 4.5e-10 <= metrics["sense_width_s"] <= 6.5e-10
        bounded &= 4.5e-10 <= metrics["capture_entry_from_sense_rise_s"] <= 7.5e-10
        bounded &= 0 <= metrics["dead_time_s"] <= 2.2e-10
        rails = all(
            observed.get(f"{phase}_{signal}_high", 0) >= vdd - margin
            and observed.get(f"{phase}_{signal}_low", vdd) <= margin
            for signal in rail_signals)
        phase_pass[phase] = complete and bounded and rails
    current = observed.get("supply_current")
    current_bounds = thresholds["average_supply_current_a"]
    capture_pass = (observed.get("e_q_diff", 0) >= thresholds["capture_differential_v"]
                    and observed.get("o_q_diff", 0) <= -thresholds["capture_differential_v"])
    passed = (all(phase_pass.values()) and capture_pass and current is not None
              and current_bounds[0] < current <= current_bounds[1])
    return {"case_id": stem, "environment_id": environment["id"],
            "code_id": control["id"], "control": control,
            "complete": complete, "phase_metrics": phase_metrics,
            "phase_pass": phase_pass, "capture_pass": capture_pass,
            "observed": observed, "result": "pass" if passed else "fail"}


def main() -> None:
    parser = argparse.ArgumentParser()
    implementation = parser.add_mutually_exclusive_group(required=True)
    implementation.add_argument("--source", type=Path)
    implementation.add_argument("--combined-pex", type=Path)
    parser.add_argument("--bridge", type=Path)
    parser.add_argument("--combined-physical", type=Path)
    parser.add_argument(
        "--combined-schematic",
        type=Path,
        help="exact schematic lowered into --combined-pex; defaults to the selected source",
    )
    parser.add_argument("--capture-pex", type=Path, required=True)
    parser.add_argument("--capture-physical", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--environment-ids", nargs="+")
    parser.add_argument("--control-ids", nargs="+")
    parser.add_argument("--internal-probes", action="store_true")
    args = parser.parse_args()
    combined_pex = args.combined_pex is not None
    if combined_pex:
        require(args.bridge is None, "combined PEX must not include a schematic bridge")
        require(args.combined_physical is not None,
                "combined PEX requires its physical record")
        combined_physical = json.loads(args.combined_physical.read_text())
        require(combined_physical.get("result") == "pass",
                "combined physical record failed")
        require(combined_physical.get("identity", {}).get("pex_sha256")
                == digest(args.combined_pex),
                "combined PEX is not byte-bound to its physical record")
        expected_schematic = (
            digest(args.combined_schematic)
            if args.combined_schematic is not None
            else hashlib.sha256(physical_source.compile_source().encode()).hexdigest()
        )
        require(combined_physical.get("identity", {}).get("schematic_sha256")
                == expected_schematic,
                "combined physical record is not the selected circuit")
        source = args.combined_pex
    else:
        require(not args.internal_probes,
                "internal probes are supported only for combined PEX")
        require(args.bridge is not None, "schematic source requires --bridge")
        require(args.combined_physical is None,
                "schematic source cannot use a combined physical record")
        require(args.combined_schematic is None,
                "schematic source cannot use --combined-schematic")
        source = args.source
    physical = json.loads(args.capture_physical.read_text())
    require(physical.get("result") == "pass", "capture physical record failed")
    require(physical.get("pex_sha256") == digest(args.capture_pex),
            "capture PEX is not byte-bound to its physical record")
    args.work.mkdir(parents=True, exist_ok=True)
    environments = list(base.CONTRACT["environments"])
    controls = CONTROLS
    if args.environment_ids:
        unknown = sorted(set(args.environment_ids)
                         - {item["id"] for item in environments})
        require(not unknown, f"unknown event environments: {unknown}")
        environments = [item for item in environments
                        if item["id"] in args.environment_ids]
    if args.control_ids:
        unknown = sorted(set(args.control_ids)
                         - {item["id"] for item in controls})
        require(not unknown, f"unknown event controls: {unknown}")
        controls = [item for item in controls if item["id"] in args.control_ids]
    specs = [(source, args.bridge, args.capture_pex, args.work,
              environment, control, combined_pex, args.internal_probes)
             for environment in environments for control in controls]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        cases = list(executor.map(run_case, specs))
    coverage = {
        environment["id"]: [case["code_id"] for case in cases
                            if case["environment_id"] == environment["id"]
                            and case["result"] == "pass"]
        for environment in environments
    }
    result = {
        "schema_version": 1,
        "claim": ("full_rc_event_bridge_into_extracted_capture" if combined_pex
                  else "schematic_full_duty_events_into_extracted_capture"),
        "scope": ("byte-bound full-RC event/bridge macro into byte-bound capture PEX"
                  if combined_pex else
                  "exact event-source schematic and bridge into byte-bound capture PEX"),
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "environment_code_coverage": coverage,
        "source_sha256": digest(source),
        "capture_pex_sha256": digest(args.capture_pex),
        "capture_physical_sha256": digest(args.capture_physical),
        "contract_sha256": digest(CONTRACT_PATH),
        "cases": cases,
        "result": "pass" if all(coverage.values()) else "fail",
        "not_a_claim": CONTRACT["not_a_claim"],
        "internal_probes": args.internal_probes,
    }
    if args.bridge is not None:
        result["bridge_sha256"] = digest(args.bridge)
    if args.combined_physical is not None:
        result["combined_physical_sha256"] = digest(args.combined_physical)
    if len(environments) != len(base.CONTRACT["environments"]):
        result["not_a_claim"] = ["five-environment coverage",
                                  *result["not_a_claim"]]
    if len(controls) != len(CONTROLS):
        result["not_a_claim"] = ["full-control-cube coverage",
                                  *result["not_a_claim"]]
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"],
                      "passing_case_count": result["passing_case_count"],
                      "environment_code_coverage": coverage}, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
