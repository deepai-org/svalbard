#!/usr/bin/env python3
"""Compile and screen a constrained family of selectable HCLK WRITE windows."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "hclk_window.spice.in"
CONTRACT_PATH = ROOT / "hclk_window_contract.json"
TEMPLATE = TEMPLATE_PATH.read_text()
WORK = Path("/work/cases")
OUTPUT = Path("/work/hclk-window-result.json")
MEASURE = re.compile(
    r"^(\w+)\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
    re.MULTILINE,
)
PLACEHOLDER = re.compile(r"@([A-Z][A-Z0-9_]*)@")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_]*$")
REQUIRED_MEASURES = {
    "hclk_fall", "write_rise", "write_fall", "write_high", "write_low",
    "win_rise", "win_fall", "wpn_fall", "wpn_rise", "wpn_high", "wpn_low",
    "supply_current",
}
RUNTIME_PLACEHOLDERS = {
    "MOS_CORNER", "TEMP_C", "VDD_V", "VMID", "SEL_V", "ESEL_V",
}


class ContractError(ValueError):
    """Raised when intent cannot compile into an unambiguous campaign."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def logical_spice_lines(text: str) -> list[str]:
    """Return non-comment SPICE statements with continuation lines joined."""
    statements: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("+"):
            require(bool(statements), "orphan SPICE continuation line")
            statements[-1] += " " + line[1:].strip()
        else:
            statements.append(line)
    return statements


def subckt_instances(text: str, subckt: str) -> dict[str, dict[str, Any]]:
    """Parse X-instance connectivity within one named subcircuit."""
    active = False
    found = False
    instances: dict[str, dict[str, Any]] = {}
    for line in logical_spice_lines(text):
        tokens = line.split()
        directive = tokens[0].lower()
        if directive == ".subckt":
            active = len(tokens) >= 2 and tokens[1].lower() == subckt.lower()
            found |= active
            continue
        if directive == ".ends":
            if active:
                active = False
            continue
        if not active or not tokens[0].lower().startswith("x"):
            continue
        parameter_index = next(
            (index for index, token in enumerate(tokens[1:], start=1)
             if "=" in token),
            len(tokens),
        )
        require(parameter_index >= 2, f"malformed instance statement: {line}")
        cell_index = parameter_index - 1
        name = tokens[0].upper()
        require(name not in instances, f"duplicate instance {name} in {subckt}")
        instances[name] = {
            "nodes": tokens[1:cell_index],
            "cell": tokens[cell_index],
        }
    require(found, f"subcircuit {subckt!r} not found")
    return instances


def validate_structural_contract(text: str, contract: dict[str, Any]) -> dict[str, Any]:
    structural = contract.get("structural_contract")
    require(isinstance(structural, dict), "structural_contract must be an object")
    subckt = structural.get("subckt")
    expected = structural.get("instances")
    require(isinstance(subckt, str) and subckt, "structural subckt is missing")
    require(isinstance(expected, dict) and expected, "structural instances are missing")
    observed = subckt_instances(text, subckt)
    checked: list[str] = []
    for raw_name, binding in expected.items():
        name = raw_name.upper()
        require(isinstance(binding, dict), f"binding {name} must be an object")
        require(name in observed, f"required semantic instance {name} is missing")
        nodes = binding.get("nodes")
        cell = binding.get("cell")
        require(isinstance(nodes, list) and all(isinstance(node, str) for node in nodes),
                f"binding {name} nodes are invalid")
        require(isinstance(cell, str) and cell, f"binding {name} cell is invalid")
        require(observed[name]["nodes"] == nodes,
                f"semantic connectivity mismatch at {name}: "
                f"expected {nodes}, got {observed[name]['nodes']}")
        require(observed[name]["cell"].lower() == cell.lower(),
                f"semantic cell mismatch at {name}: expected {cell}, "
                f"got {observed[name]['cell']}")
        checked.append(name)
    return {"result": "pass", "subckt": subckt, "checked_instances": checked}


def load_contract() -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text())
    require(contract.get("schema_version") == 1, "unsupported contract schema")
    require(isinstance(contract.get("contract_id"), str), "contract_id is missing")
    unit_interval = contract.get("unit_interval_s")
    require(isinstance(unit_interval, (int, float))
            and math.isfinite(unit_interval) and unit_interval > 0,
            "unit_interval_s must be finite and positive")

    environments = contract.get("environments")
    require(isinstance(environments, list) and environments,
            "environments must be a non-empty list")
    environment_ids: list[str] = []
    for environment in environments:
        require(isinstance(environment, dict), "environment must be an object")
        identifier = environment.get("id")
        require(isinstance(identifier, str) and SAFE_ID.fullmatch(identifier) is not None,
                "environment id is invalid")
        environment_ids.append(identifier)
        require(environment.get("mos_corner") in {"typical", "ff", "ss"},
                f"environment {identifier} has an unsupported MOS corner")
        for field in ("vdd_v", "temperature_c"):
            value = environment.get(field)
            require(isinstance(value, (int, float)) and math.isfinite(value),
                    f"environment {identifier} field {field} is invalid")
    require(len(environment_ids) == len(set(environment_ids)),
            "environment ids must be unique")

    codes = contract.get("control_codes")
    require(isinstance(codes, list) and codes,
            "control_codes must be a non-empty list")
    code_ids: list[str] = []
    for code in codes:
        require(isinstance(code, dict), "control code must be an object")
        identifier = code.get("id")
        require(isinstance(identifier, str)
                and SAFE_ID.fullmatch(identifier) is not None,
                "control code id is invalid")
        require(code.get("sel") in (0, 1) and code.get("epoch") in (0, 1),
                f"control code {identifier} must bind binary sel and epoch")
        code_ids.append(identifier)
    require(len(code_ids) == len(set(code_ids)), "control code ids must be unique")

    candidates = contract.get("candidates")
    require(isinstance(candidates, list) and candidates,
            "candidates must be a non-empty list")
    candidate_ids: list[str] = []
    template_parameters = set(PLACEHOLDER.findall(TEMPLATE)) - RUNTIME_PLACEHOLDERS
    for candidate in candidates:
        require(isinstance(candidate, dict), "candidate must be an object")
        identifier = candidate.get("id")
        replacements = candidate.get("replacements")
        require(isinstance(identifier, str) and SAFE_ID.fullmatch(identifier) is not None,
                "candidate id is invalid")
        candidate_ids.append(identifier)
        require(isinstance(replacements, dict)
                and all(isinstance(key, str) and isinstance(value, str)
                        for key, value in replacements.items()),
                f"candidate {identifier} replacements are invalid")
        require(set(replacements) == template_parameters,
                f"candidate {identifier} replacements do not exactly bind "
                f"{sorted(template_parameters)}")
    require(len(candidate_ids) == len(set(candidate_ids)),
            "candidate ids must be unique")

    thresholds = contract.get("thresholds")
    require(isinstance(thresholds, dict), "thresholds must be an object")
    for field in ("write_width_s", "write_delay_from_hclk_fall_s",
                  "average_supply_current_a"):
        interval = thresholds.get(field)
        require(isinstance(interval, list) and len(interval) == 2
                and all(isinstance(value, (int, float)) and math.isfinite(value)
                        for value in interval)
                and interval[0] <= interval[1],
                f"threshold {field} is invalid")
    margin = thresholds.get("logic_rail_margin_v")
    require(isinstance(margin, (int, float)) and math.isfinite(margin) and margin >= 0,
            "logic_rail_margin_v is invalid")
    validate_structural_contract(TEMPLATE, contract)
    return contract


CONTRACT = load_contract()


def cyclic_delta(later: float, earlier: float) -> float:
    """Return the positive same-event separation at the declared unit interval."""
    period = float(CONTRACT["unit_interval_s"])
    delta = later - earlier
    while delta < 0:
        delta += period
    while delta >= period:
        delta -= period
    return delta


def run_case(spec: tuple[dict[str, Any], dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    candidate, environment, code = spec
    vdd = float(environment["vdd_v"])
    replacements = {
        "MOS_CORNER": environment["mos_corner"],
        "TEMP_C": str(environment["temperature_c"]),
        "VDD_V": f"{vdd:.6f}",
        "VMID": f"{vdd / 2:.6f}",
        "SEL_V": f"{vdd if code['sel'] else 0:.6f}",
        "ESEL_V": f"{vdd if code['epoch'] else 0:.6f}",
        **candidate["replacements"],
    }
    text = TEMPLATE
    for key, value in replacements.items():
        text = text.replace(f"@{key}@", value)
    unresolved = sorted(set(PLACEHOLDER.findall(text)))
    require(not unresolved, f"unresolved netlist placeholders: {unresolved}")

    stem = f"{candidate['id']}_{environment['id']}_{code['id']}"
    deck = WORK / f"{stem}.spice"
    log = WORK / f"{stem}.log"
    deck.write_text(text)
    try:
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=240, check=False,
            )
        returncode = run.returncode
    except subprocess.TimeoutExpired:
        returncode = -1
    observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
    complete = returncode == 0 and REQUIRED_MEASURES <= observed.keys()
    width = cyclic_delta(observed.get("write_fall", 0), observed.get("write_rise", 0))
    window_width = cyclic_delta(observed.get("win_fall", 0), observed.get("win_rise", 0))
    wpn_width = cyclic_delta(observed.get("wpn_rise", 0), observed.get("wpn_fall", 0))
    delay = cyclic_delta(observed.get("write_rise", 0), observed.get("hclk_fall", 0))
    thresholds = CONTRACT["thresholds"]
    width_range = thresholds["write_width_s"]
    delay_range = thresholds["write_delay_from_hclk_fall_s"]
    current_range = thresholds["average_supply_current_a"]
    margin = thresholds["logic_rail_margin_v"]
    passed = (
        complete
        and width_range[0] <= width <= width_range[1]
        and delay_range[0] <= delay <= delay_range[1]
        and observed["write_high"] >= vdd - margin
        and observed["write_low"] <= margin
        and observed["wpn_high"] >= vdd - margin
        and observed["wpn_low"] <= margin
        and current_range[0] < observed["supply_current"] <= current_range[1]
    )
    return {
        "case_id": stem,
        "candidate_id": candidate["id"],
        "environment_id": environment["id"],
        "environment": [environment["mos_corner"], vdd, environment["temperature_c"]],
        "code_id": code["id"],
        "control": {"sel": code["sel"], "epoch": code["epoch"]},
        "complete": complete,
        "write_width_s": width,
        "detector_window_width_s": window_width,
        "wpn_low_width_s": wpn_width,
        "write_delay_from_hclk_fall_s": delay,
        "observed": observed,
        "result": "pass" if passed else "fail",
    }


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    specs = [
        (candidate, environment, code)
        for candidate in CONTRACT["candidates"]
        for environment in CONTRACT["environments"]
        for code in CONTRACT["control_codes"]
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        cases = list(executor.map(run_case, specs))

    candidate_coverage: dict[str, dict[str, list[int]]] = {}
    for candidate in CONTRACT["candidates"]:
        by_environment: dict[str, list[int]] = {}
        for environment in CONTRACT["environments"]:
            by_environment[environment["id"]] = [
                case["code_id"] for case in cases
                if case["candidate_id"] == candidate["id"]
                and case["environment_id"] == environment["id"]
                and case["result"] == "pass"
            ]
        candidate_coverage[candidate["id"]] = by_environment
    qualifying_candidates = [
        candidate_id for candidate_id, coverage in candidate_coverage.items()
        if all(coverage.values())
    ]
    aggregate_environment_coverage = {
        environment["id"]: [
            {"candidate_id": case["candidate_id"], "code_id": case["code_id"]}
            for case in cases
            if case["environment_id"] == environment["id"]
            and case["result"] == "pass"
        ]
        for environment in CONTRACT["environments"]
    }
    result = {
        "schema_version": 2,
        "claim": "selectable_full_swing_hclk_write_window_necessary_screen",
        "scope": (
            "schematic necessary condition only: one physically fixed candidate "
            "must cover every environment through its realized static codes"
        ),
        "candidate_selection_semantics": (
            "candidate_id is a fabrication-time circuit choice and cannot vary "
            "by environment; code_id binds two realized static post-fabrication controls"
        ),
        "not_a_claim": [
            "complete_pcie_pulse_generator",
            "physical_layout_or_pex",
            "pcie_capture_or_cdr_closure",
            "calibration_algorithm_or_silicon_yield",
        ],
        "source_sha256": digest(TEMPLATE_PATH),
        "contract_sha256": digest(CONTRACT_PATH),
        "runner_sha256": digest(Path(__file__)),
        "structural_contract": validate_structural_contract(TEMPLATE, CONTRACT),
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "candidate_coverage": candidate_coverage,
        "qualifying_candidates": qualifying_candidates,
        "aggregate_environment_coverage_diagnostic": aggregate_environment_coverage,
        "cases": cases,
    }
    result["result"] = "pass" if qualifying_candidates else "fail"
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": result["result"],
        "qualifying_candidates": qualifying_candidates,
        "candidate_coverage": candidate_coverage,
    }, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
