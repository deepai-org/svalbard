#!/usr/bin/env python3
"""Qualify the fixed, LVS-equivalent dual-phase macro with full-RC PEX."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

import compile_selected_physical_source as physical
import run_hclk_window_probe as base


ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "selected_pex_contract.json"
DEFAULT_WORK = Path("/work/selected-pex-cases")
MEASURE = re.compile(r"^([a-z0-9_]+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
PHASES = ("e", "o")
SIGNALS = ("sense", "boost", "write")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_contract() -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text())
    require(contract.get("schema_version") == 1, "unsupported PEX contract schema")
    require(contract.get("selected_write_candidate") == physical.SELECTED_WRITE,
            "PEX and physical WRITE selections differ")
    require(contract.get("selected_sense_candidate") == physical.SELECTED_SENSE,
            "PEX and physical SENSE selections differ")
    require(contract.get("unit_interval_s") == base.CONTRACT["unit_interval_s"],
            "PEX and schematic unit intervals differ")
    loads = contract.get("external_load_f", {})
    require(set(loads) == set(SIGNALS)
            and all(isinstance(value, (int, float)) and value > 0
                    for value in loads.values()), "invalid PEX external loads")
    thresholds = contract.get("thresholds", {})
    for name in ("sense_width_s", "write_width_s",
                 "write_delay_from_sense_rise_s", "dead_time_s",
                 "dual_phase_average_supply_current_a"):
        interval = thresholds.get(name)
        require(isinstance(interval, list) and len(interval) == 2
                and all(isinstance(value, (int, float)) and math.isfinite(value)
                        for value in interval)
                and interval[0] <= interval[1], f"invalid PEX threshold {name}")
    require(isinstance(thresholds.get("logic_rail_margin_v"), (int, float))
            and thresholds["logic_rail_margin_v"] > 0,
            "invalid PEX logic rail margin")
    return contract


CONTRACT = load_contract()


def compile_deck(netlist: Path, top: str, environment: dict[str, Any],
                 code: dict[str, Any]) -> str:
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
    return f"""* SPDX-License-Identifier: Apache-2.0
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {environment['mos_corner']}
.temp {environment['temperature_c']}
.include {netlist}

VDD VDD 0 PWL(0 0 500p {vdd:.6f})
VSEL0 SEL0 0 PWL(0 0 500p {vdd if code['sel'] else 0:.6f})
VSEL1 SEL1 0 PWL(0 0 500p {vdd if code['epoch'] else 0:.6f})
VCLKP CLKP_H 0 PULSE(0 {vdd:.6f} 1n 20p 20p 380p 800p)
VCLKN CLKN_H 0 PULSE(0 {vdd:.6f} 1.4n 20p 20p 380p 800p)
XDUT CLKP_H CLKN_H SEL0 SEL1 VDD 0 E_SENSE E_BOOST E_WRITE
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


def run_case(spec: tuple[Path, str, Path, dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    netlist, top, work, environment, code = spec
    stem = f"{environment['id']}_{code['id']}"
    deck = work / f"{stem}.spice"
    log = work / f"{stem}.log"
    deck.write_text(compile_deck(netlist, top, environment, code))
    try:
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=600,
                                 check=False)
        returncode = run.returncode
    except subprocess.TimeoutExpired:
        returncode = -1
    observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
    required = {f"{phase}_{signal}_{level}"
                for phase in PHASES for signal in SIGNALS
                for level in ("high", "low")}
    required |= {f"{phase}_{signal}_{edge}"
                 for phase in PHASES for signal in ("sense", "write")
                 for edge in ("rise", "fall")}
    required.add("supply_current")
    complete = returncode == 0 and required <= observed.keys()
    thresholds = CONTRACT["thresholds"]
    margin = float(thresholds["logic_rail_margin_v"])
    vdd = float(environment["vdd_v"])
    phase_metrics = {}
    phase_pass = {}
    violations = []
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
        for name, value in metrics.items():
            low, high = thresholds[name]
            if not low <= value <= high:
                violations.append({"phase": phase, "measure": name,
                                   "actual": value, "bounds": [low, high]})
        for signal in SIGNALS:
            high_value = observed.get(f"{phase}_{signal}_high")
            low_value = observed.get(f"{phase}_{signal}_low")
            if high_value is None or high_value < vdd - margin:
                violations.append({"phase": phase,
                                   "measure": f"{signal}_high_v",
                                   "actual": high_value,
                                   "bounds": [vdd - margin, vdd]})
            if low_value is None or low_value > margin:
                violations.append({"phase": phase,
                                   "measure": f"{signal}_low_v",
                                   "actual": low_value,
                                   "bounds": [0.0, margin]})
        phase_pass[phase] = complete and not any(
            item["phase"] == phase for item in violations)
    current_ok = (complete
                  and thresholds["dual_phase_average_supply_current_a"][0]
                  < observed.get("supply_current", 0)
                  <= thresholds["dual_phase_average_supply_current_a"][1])
    if not current_ok:
        violations.append({
            "phase": "both", "measure": "dual_phase_average_supply_current_a",
            "actual": observed.get("supply_current"),
            "bounds": thresholds["dual_phase_average_supply_current_a"],
        })
    if not complete:
        violations.append({"phase": "both", "measure": "measurement_complete",
                           "actual": False, "bounds": [True, True]})
    passed = all(phase_pass.values()) and current_ok
    return {
        "case_id": stem,
        "environment_id": environment["id"],
        "environment": [environment["mos_corner"], vdd,
                        environment["temperature_c"]],
        "code_id": code["id"],
        "control": {"sel": code["sel"], "epoch": code["epoch"]},
        "complete": complete,
        "phase_metrics": phase_metrics,
        "phase_pass": phase_pass,
        "supply_current_a": observed.get("supply_current"),
        "observed": observed,
        "violations": violations,
        "result": "pass" if passed else "fail",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--top", default="selected_dual_control_pulse_pex")
    parser.add_argument("--netlist-kind", choices=("full_rc_pex", "schematic"),
                        default="full_rc_pex")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    args = parser.parse_args()
    require(args.pex.is_file(), f"PEX netlist not found: {args.pex}")
    args.work.mkdir(parents=True, exist_ok=True)
    specs = [(args.pex, args.top, args.work, environment, code)
             for environment in base.CONTRACT["environments"]
             for code in base.CONTRACT["control_codes"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        cases = list(executor.map(run_case, specs))
    coverage = {
        environment["id"]: [case["code_id"] for case in cases
                            if case["environment_id"] == environment["id"]
                            and case["result"] == "pass"]
        for environment in base.CONTRACT["environments"]
    }
    violation_counts: dict[str, int] = {}
    for case in cases:
        for violation in case["violations"]:
            key = violation["measure"]
            violation_counts[key] = violation_counts.get(key, 0) + 1
    result = {
        "schema_version": 1,
        "claim": "selected_dual_control_pulse_full_rc_pvt",
        "scope": ("full-RC extracted dual-phase macro with declared external loads"
                  if args.netlist_kind == "full_rc_pex" else
                  "selected schematic dual-phase replay with declared external loads"),
        "netlist_kind": args.netlist_kind,
        "selected_write_candidate": physical.SELECTED_WRITE,
        "selected_sense_candidate": physical.SELECTED_SENSE,
        "identity": {"pex_sha256": digest(args.pex),
                     "contract_sha256": digest(CONTRACT_PATH),
                     "runner_sha256": digest(Path(__file__))},
        "candidate_selection_semantics": CONTRACT["qualification"],
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "environment_code_coverage": coverage,
        "ranked_violation_counts": sorted(
            violation_counts.items(), key=lambda item: (-item[1], item[0])),
        "cases": cases,
        "not_a_claim": ["capture_or_cdr_closure", "package_or_channel_closure",
                        "provider_signoff_or_silicon_yield"],
    }
    result["result"] = "pass" if all(coverage.values()) else "fail"
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"],
                      "passing_case_count": result["passing_case_count"],
                      "environment_code_coverage": coverage}, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
