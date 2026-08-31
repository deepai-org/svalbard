#!/usr/bin/env python3
"""Qualify the localized three-control recovery circuit before layout."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import compile_recovery_physical_source as recovery
import run_hclk_window_probe as base
import run_selected_pex as verifier


ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "recovery_contract.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text())
PHASES = ("e", "o")
SIGNALS = ("sense", "boost", "write")
INTERNAL_STAGES = tuple(CONTRACT["internal_probe_nodes"])
INTERNAL_PATHS = {name: tuple(stages)
                  for name, stages in CONTRACT["semantic_paths"].items()}
CONTROLS = [
    {"id": f"sense{sense}_interval{interval}_epoch{epoch}",
     "sense": sense, "interval": interval, "epoch": epoch}
    for sense in (0, 1) for interval in (0, 1) for epoch in (0, 1)
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_contract() -> None:
    require(CONTRACT.get("schema_version") == 1, "unsupported recovery schema")
    require(CONTRACT.get("top") == recovery.TOP, "recovery top mismatch")
    require(CONTRACT.get("unit_interval_s") == base.CONTRACT["unit_interval_s"],
            "recovery unit interval mismatch")
    require(CONTRACT.get("thresholds") == verifier.CONTRACT["thresholds"],
            "recovery and selected PEX thresholds differ")
    require(set(INTERNAL_PATHS) == {"sense", "boost"},
            "recovery semantic paths must name SENSE and BOOST")
    require(all(path[-1] == name for name, path in INTERNAL_PATHS.items()),
            "recovery semantic paths must terminate at their named output")
    require(set(stage for path in INTERNAL_PATHS.values() for stage in path[:-1])
            <= set(INTERNAL_STAGES),
            "recovery semantic paths reference an undeclared internal probe")


validate_contract()


def compile_deck(source: Path, top: str, environment: dict[str, Any],
                 control: dict[str, Any], internal_probes: bool = False) -> str:
    vdd = float(environment["vdd_v"])
    loads = CONTRACT["external_load_f"]
    measures = []
    for phase in PHASES:
        upper = phase.upper()
        for signal in SIGNALS:
            node = f"{upper}_{signal.upper()}"
            measures.extend([
                f"meas tran {phase}_{signal}_high max v({node}) from=8n to=12.8n",
                f"meas tran {phase}_{signal}_low min v({node}) from=8n to=12.8n",
            ])
        for edge in ("rise", "fall"):
            measures.append(
                f"meas tran {phase}_sense_{edge} when v({upper}_SENSE)={vdd / 2:.6f} "
                f"{edge}=1 td=8n")
            measures.append(
                f"meas tran {phase}_write_{edge} when v({upper}_WRITE)={vdd / 2:.6f} "
                f"{edge}=1 td=8n")
    measures.append("meas tran supply_current avg isupply from=8n to=12.8n")
    if internal_probes:
        for phase in PHASES:
            for stage in INTERNAL_STAGES:
                node = f"xdut.DBG_{phase.upper()}_{stage.upper()}"
                measures.extend([
                    f"meas tran {phase}_dbg_{stage}_high max v({node}) from=8n to=12.8n",
                    f"meas tran {phase}_dbg_{stage}_low min v({node}) from=8n to=12.8n",
                ])
    return f"""* SPDX-License-Identifier: Apache-2.0
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {environment['mos_corner']}
.temp {environment['temperature_c']}
.include {source}
VDD VDD 0 PWL(0 0 500p {vdd:.6f})
VSEL0 SEL0 0 PWL(0 0 500p {vdd if control['sense'] else 0:.6f})
VSEL1 SEL1 0 PWL(0 0 500p {vdd if control['interval'] else 0:.6f})
VSEL2 SEL2 0 PWL(0 0 500p {vdd if control['epoch'] else 0:.6f})
VCLKP CLKP_H 0 PULSE(0 {vdd:.6f} 1n 20p 20p 380p 800p)
VCLKN CLKN_H 0 PULSE(0 {vdd:.6f} 1.4n 20p 20p 380p 800p)
XDUT CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD 0 E_SENSE E_BOOST E_WRITE
+ O_SENSE O_BOOST O_WRITE {top}
CE_SENSE E_SENSE 0 {loads['sense']}
CE_BOOST E_BOOST 0 {loads['boost']}
CE_WRITE E_WRITE 0 {loads['write']}
CO_SENSE O_SENSE 0 {loads['sense']}
CO_BOOST O_BOOST 0 {loads['boost']}
CO_WRITE O_WRITE 0 {loads['write']}
.control
tran 1p 12.8n uic
let isupply = -i(VDD)
{chr(10).join(measures)}
.endc
.end
"""


def cyclic_delta(later: float, earlier: float) -> float:
    return (later - earlier) % float(CONTRACT["unit_interval_s"])


def stage_diagnostics(observed: dict[str, float], phase: str, vdd: float,
                      margin: float) -> dict[str, Any]:
    stages: dict[str, Any] = {}
    for stage in (*INTERNAL_STAGES, *SIGNALS):
        prefix = (f"{phase}_dbg_{stage}" if stage in INTERNAL_STAGES
                  else f"{phase}_{stage}")
        high = observed.get(f"{prefix}_high")
        low = observed.get(f"{prefix}_low")
        high_margin = None if high is None else high - (vdd - margin)
        low_margin = None if low is None else margin - low
        transition_high_margin = None if high is None else high - vdd / 2
        transition_low_margin = None if low is None else vdd / 2 - low
        stages[stage] = {
            "high_v": high,
            "low_v": low,
            "high_margin_v": high_margin,
            "low_margin_v": low_margin,
            "rail_pass": (high_margin is not None and low_margin is not None
                          and high_margin >= 0 and low_margin >= 0),
            "transition_high_margin_v": transition_high_margin,
            "transition_low_margin_v": transition_low_margin,
            "transition_pass": (transition_high_margin is not None
                                and transition_low_margin is not None
                                and transition_high_margin >= 0
                                and transition_low_margin >= 0),
        }
    paths = {}
    for path, order in INTERNAL_PATHS.items():
        first_failed = next((stage for stage in order
                             if not stages[stage]["transition_pass"]), None)
        paths[path] = {"stage_order": list(order),
                       "criterion": "both midrail transitions observed",
                       "first_failed_stage": first_failed}
    return {"stages": stages, "paths": paths}


def run_case(spec: tuple[Path, str, Path, dict[str, Any], dict[str, Any], bool]) -> dict[str, Any]:
    source, top, work, environment, control, internal_probes = spec
    stem = f"{environment['id']}_{control['id']}"
    deck = work / f"{stem}.spice"
    log = work / f"{stem}.log"
    deck.write_text(compile_deck(source, top, environment, control,
                                 internal_probes=internal_probes))
    try:
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=300,
                                 check=False)
        returncode = run.returncode
    except subprocess.TimeoutExpired:
        returncode = -1
    observed = {key: float(value)
                for key, value in verifier.MEASURE.findall(log.read_text())}
    required = {f"{phase}_{signal}_{level}"
                for phase in PHASES for signal in SIGNALS
                for level in ("high", "low")}
    required |= {f"{phase}_{signal}_{edge}"
                 for phase in PHASES for signal in ("sense", "write")
                 for edge in ("rise", "fall")}
    required.add("supply_current")
    if internal_probes:
        required |= {f"{phase}_dbg_{stage}_{level}"
                     for phase in PHASES for stage in INTERNAL_STAGES
                     for level in ("high", "low")}
    complete = returncode == 0 and required <= observed.keys()
    thresholds = CONTRACT["thresholds"]
    margin = float(thresholds["logic_rail_margin_v"])
    vdd = float(environment["vdd_v"])
    phase_metrics = {}
    phase_pass = {}
    for phase in PHASES:
        metrics = {
            "sense_width_s": cyclic_delta(observed.get(f"{phase}_sense_fall", 0),
                                            observed.get(f"{phase}_sense_rise", 0)),
            "write_width_s": cyclic_delta(observed.get(f"{phase}_write_fall", 0),
                                            observed.get(f"{phase}_write_rise", 0)),
            "write_delay_from_sense_rise_s": cyclic_delta(
                observed.get(f"{phase}_write_rise", 0),
                observed.get(f"{phase}_sense_rise", 0)),
            "dead_time_s": cyclic_delta(observed.get(f"{phase}_write_rise", 0),
                                          observed.get(f"{phase}_sense_fall", 0)),
        }
        phase_metrics[phase] = metrics
        phase_pass[phase] = complete and all(
            thresholds[name][0] <= value <= thresholds[name][1]
            for name, value in metrics.items()) and all(
                observed[f"{phase}_{signal}_high"] >= vdd - margin
                and observed[f"{phase}_{signal}_low"] <= margin
                for signal in SIGNALS)
    current = observed.get("supply_current")
    current_bounds = thresholds["dual_phase_average_supply_current_a"]
    passed = (all(phase_pass.values()) and current is not None
              and current_bounds[0] < current <= current_bounds[1])
    result = {"case_id": stem, "environment_id": environment["id"],
            "code_id": control["id"], "control": control,
            "complete": complete, "phase_metrics": phase_metrics,
            "phase_pass": phase_pass, "observed": observed,
            "result": "pass" if passed else "fail"}
    if internal_probes:
        result["internal_stage_diagnostics"] = {
            phase: stage_diagnostics(observed, phase, vdd, margin)
            for phase in PHASES
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top", default=recovery.TOP)
    parser.add_argument("--netlist-kind", choices=("schematic", "full_rc_pex"),
                        default="schematic")
    parser.add_argument("--environment-ids", nargs="+")
    parser.add_argument("--internal-probes", action="store_true",
                        help="measure semantic nodes retained in flattened PEX")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    environments = base.CONTRACT["environments"]
    if args.environment_ids:
        unknown = sorted(set(args.environment_ids)
                         - {item["id"] for item in environments})
        require(not unknown, f"unknown recovery environments: {unknown}")
        environments = [item for item in environments
                        if item["id"] in args.environment_ids]
    specs = [(args.source, args.top, args.work, environment, control,
              args.internal_probes)
             for environment in environments
             for control in CONTROLS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        cases = list(executor.map(run_case, specs))
    coverage = {
        environment["id"]: [case["code_id"] for case in cases
                            if case["environment_id"] == environment["id"]
                            and case["result"] == "pass"]
        for environment in environments
    }
    result = {"schema_version": 1,
              "claim": "three_control_full_width_boost_schematic",
              "scope": ("exact dual-phase schematic with declared loads"
                        if args.netlist_kind == "schematic" else
                        "full-RC extracted dual-phase macro with declared loads"),
              "netlist_kind": args.netlist_kind,
              "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
              "contract_sha256": hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest(),
              "candidate_selection_semantics": CONTRACT["candidate_scope"],
              "internal_probes": args.internal_probes,
              "case_count": len(cases),
              "passing_case_count": sum(c["result"] == "pass" for c in cases),
              "environment_code_coverage": coverage, "cases": cases,
              "not_a_claim": ["layout", "pex", "capture_or_cdr_closure"]}
    result["result"] = "pass" if all(coverage.values()) else "fail"
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"],
                      "passing_case_count": result["passing_case_count"],
                      "environment_code_coverage": coverage}, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
