#!/usr/bin/env python3
"""Compile the selected WRITE family with the established SENSE path."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import run_hclk_window_probe as base


ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "sense_write_composition_contract.json"
APPEND_PATH = ROOT / "sense_write_composition.spice.in"
WORK = Path("/work/sense-write-cases")
OUTPUT = Path("/work/sense-write-composition-result.json")
REQUIRED = {"sense_rise", "sense_fall", "write_rise", "write_fall",
            "sense_high", "sense_low", "boost_high", "boost_low",
            "write_high", "write_low", "supply_current"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_contract() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    contract = json.loads(CONTRACT_PATH.read_text())
    base.require(contract.get("schema_version") == 1,
                 "unsupported composition contract schema")
    candidate_ids = contract.get("candidate_ids")
    base.require(isinstance(candidate_ids, list) and candidate_ids
                 and len(candidate_ids) == len(set(candidate_ids)),
                 "composition candidate_ids must be non-empty and unique")
    candidates = [candidate for identifier in candidate_ids
                  for candidate in base.CONTRACT["candidates"]
                  if candidate["id"] == identifier]
    base.require(len(candidates) == len(candidate_ids),
                 "each composition candidate must resolve exactly once")
    base.require(contract.get("unit_interval_s") == base.CONTRACT["unit_interval_s"],
                 "composition and source unit intervals differ")
    sense_candidates = contract.get("sense_candidates")
    base.require(isinstance(sense_candidates, list) and sense_candidates,
                 "sense_candidates must be non-empty")
    expected = {"SENSE_PM", "SENSE_BASE_MN", "SENSE_EXTRA_W", "SENSE_EXTRA_M"}
    ids = []
    for sense_candidate in sense_candidates:
        identifier = sense_candidate.get("id")
        replacements = sense_candidate.get("replacements")
        base.require(isinstance(identifier, str)
                     and base.SAFE_ID.fullmatch(identifier) is not None,
                     "invalid sense candidate id")
        base.require(isinstance(replacements, dict)
                     and set(replacements) == expected
                     and all(isinstance(value, str)
                             for value in replacements.values()),
                     f"invalid replacements for {identifier}")
        ids.append(identifier)
    base.require(len(ids) == len(set(ids)), "sense candidate ids must be unique")
    thresholds = contract.get("thresholds")
    base.require(isinstance(thresholds, dict), "composition thresholds missing")
    for field in ("sense_width_s", "write_width_s",
                  "write_delay_from_sense_rise_s", "dead_time_s",
                  "average_supply_current_a"):
        interval = thresholds.get(field)
        base.require(isinstance(interval, list) and len(interval) == 2
                     and all(isinstance(value, (int, float))
                             and math.isfinite(value) for value in interval)
                     and interval[0] <= interval[1],
                     f"invalid composition threshold {field}")
    base.validate_structural_contract(APPEND_PATH.read_text(), contract)
    return contract, candidates, sense_candidates


CONTRACT, WRITE_CANDIDATES, SENSE_CANDIDATES = load_contract()


def cyclic_delta(later: float, earlier: float) -> float:
    period = float(CONTRACT["unit_interval_s"])
    return (later - earlier) % period


def source_prefix() -> str:
    marker = "\nVDD VDD 0 PWL"
    base.require(marker in base.TEMPLATE, "HCLK probe bench marker not found")
    return base.TEMPLATE.split(marker, 1)[0]


def compile_deck(write_candidate: dict[str, Any], sense_candidate: dict[str, Any],
                 environment: dict[str, Any], code: dict[str, Any]) -> str:
    vdd = float(environment["vdd_v"])
    replacements = {
        "MOS_CORNER": environment["mos_corner"],
        "TEMP_C": str(environment["temperature_c"]),
        "VDD_V": f"{vdd:.6f}",
        "VMID": f"{vdd / 2:.6f}",
        "SEL_V": f"{vdd if code['sel'] else 0:.6f}",
        "ESEL_V": f"{vdd if code['epoch'] else 0:.6f}",
        **write_candidate["replacements"],
        **sense_candidate["replacements"],
    }
    text = source_prefix() + APPEND_PATH.read_text()
    for key, value in replacements.items():
        text = text.replace(f"@{key}@", value)
    unresolved = sorted(set(base.PLACEHOLDER.findall(text)))
    base.require(not unresolved, f"unresolved composition placeholders: {unresolved}")
    return text


def run_case(spec: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    write_candidate, sense_candidate, environment, code = spec
    joint_id = f"{write_candidate['id']}__{sense_candidate['id']}"
    stem = f"{joint_id}_{environment['id']}_{code['id']}"
    deck = WORK / f"{stem}.spice"
    log = WORK / f"{stem}.log"
    deck.write_text(compile_deck(write_candidate, sense_candidate,
                                 environment, code))
    try:
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=240,
                                 check=False)
        returncode = run.returncode
    except subprocess.TimeoutExpired:
        returncode = -1
    observed = {key: float(value)
                for key, value in base.MEASURE.findall(log.read_text())}
    complete = returncode == 0 and REQUIRED <= observed.keys()
    sense_width = cyclic_delta(observed.get("sense_fall", 0),
                               observed.get("sense_rise", 0))
    write_width = cyclic_delta(observed.get("write_fall", 0),
                               observed.get("write_rise", 0))
    write_delay = cyclic_delta(observed.get("write_rise", 0),
                               observed.get("sense_rise", 0))
    dead_time = cyclic_delta(observed.get("write_rise", 0),
                             observed.get("sense_fall", 0))
    t = CONTRACT["thresholds"]
    margin = t["logic_rail_margin_v"]
    vdd = float(environment["vdd_v"])
    passed = (complete
              and t["sense_width_s"][0] <= sense_width <= t["sense_width_s"][1]
              and t["write_width_s"][0] <= write_width <= t["write_width_s"][1]
              and t["write_delay_from_sense_rise_s"][0] <= write_delay <= t["write_delay_from_sense_rise_s"][1]
              and t["dead_time_s"][0] <= dead_time <= t["dead_time_s"][1]
              and observed["sense_high"] >= vdd - margin
              and observed["sense_low"] <= margin
              and observed["boost_high"] >= vdd - margin
              and observed["boost_low"] <= margin
              and observed["write_high"] >= vdd - margin
              and observed["write_low"] <= margin
              and t["average_supply_current_a"][0] < observed["supply_current"] <= t["average_supply_current_a"][1])
    return {"case_id": stem, "joint_candidate_id": joint_id,
            "write_candidate_id": write_candidate["id"],
            "sense_candidate_id": sense_candidate["id"],
            "environment_id": environment["id"],
            "environment": [environment["mos_corner"], vdd,
                            environment["temperature_c"]],
            "code_id": code["id"],
            "control": {"sel": code["sel"], "epoch": code["epoch"]},
            "complete": complete,
            "sense_width_s": sense_width, "write_width_s": write_width,
            "write_delay_from_sense_rise_s": write_delay,
            "dead_time_s": dead_time, "observed": observed,
            "result": "pass" if passed else "fail"}


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    specs = [(write_candidate, sense_candidate, environment, code)
             for write_candidate in WRITE_CANDIDATES
             for sense_candidate in SENSE_CANDIDATES
             for environment in base.CONTRACT["environments"]
             for code in base.CONTRACT["control_codes"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        cases = list(executor.map(run_case, specs))
    joint_ids = [f"{write_candidate['id']}__{sense_candidate['id']}"
                 for write_candidate in WRITE_CANDIDATES
                 for sense_candidate in SENSE_CANDIDATES]
    coverage = {
        joint_id: {
            environment["id"]: [case["code_id"] for case in cases
                                if case["joint_candidate_id"] == joint_id
                                and case["environment_id"] == environment["id"]
                                and case["result"] == "pass"]
            for environment in base.CONTRACT["environments"]}
        for joint_id in joint_ids}
    qualifying = [identifier for identifier, by_environment in coverage.items()
                  if all(by_environment.values())]
    result = {
        "schema_version": 1,
        "claim": "selected_sense_write_schematic_composition",
        "scope": "schematic composition with declared capacitive boundaries",
        "write_candidate_ids": [candidate["id"] for candidate in WRITE_CANDIDATES],
        "candidate_selection_semantics": "one fixed circuit; only the two-bit static code may vary by environment",
        "source_sha256": {"hclk_template": digest(base.TEMPLATE_PATH),
                          "hclk_contract": digest(base.CONTRACT_PATH),
                          "composition": digest(APPEND_PATH),
                          "composition_contract": digest(CONTRACT_PATH),
                          "runner": digest(Path(__file__))},
        "structural_contract": base.validate_structural_contract(APPEND_PATH.read_text(), CONTRACT),
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "joint_candidate_coverage": coverage,
        "qualifying_joint_candidates": qualifying,
        "cases": cases,
        "not_a_claim": ["physical_layout_or_pex", "capture_or_cdr_closure",
                        "calibration_algorithm_or_silicon_yield"],
    }
    result["result"] = "pass" if qualifying else "fail"
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"],
                      "qualifying_joint_candidates": qualifying,
                      "joint_candidate_coverage": coverage}, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
