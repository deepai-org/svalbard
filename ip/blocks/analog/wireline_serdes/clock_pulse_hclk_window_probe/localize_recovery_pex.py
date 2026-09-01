#!/usr/bin/env python3
"""Rank semantic RC counterfactuals for the three-control recovery PEX.

The transformed netlists are diagnostic artifacts only.  A proposed remedy
must still regenerate geometry and pass DRC, unique LVS, extraction, and the
unaltered contract.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
from typing import Any

import localize_selected_pex as pex_cf
import run_hclk_window_probe as base
import run_recovery_schematic as recovery


PHASES = ("E", "O")


def stage_nets(stage: str) -> set[str]:
    """Resolve a semantic stage through the active closure contract."""
    if stage in recovery.INTERNAL_PROBES:
        binding = recovery.INTERNAL_PROBES[stage]
        return {binding.format(phase=phase) for phase in PHASES}
    if stage in recovery.SIGNALS:
        return {f"{phase}_{stage.upper()}" for phase in PHASES}
    raise ValueError(f"semantic stage has no extracted binding: {stage}")


def semantic_path_nets(*path_names: str) -> set[str]:
    stages = {
        stage
        for name in path_names
        if name in recovery.INTERNAL_PATHS
        for stage in recovery.INTERNAL_PATHS[name]["stages"]
    }
    return set().union(*(stage_nets(stage) for stage in stages)) if stages else set()


WRITE_EPOCH = semantic_path_nets(*(
    name for name in recovery.INTERNAL_PATHS if name.startswith("write_epoch")))
WRITE_START = semantic_path_nets("write_start")
WRITE_END = semantic_path_nets(*(
    name for name in recovery.INTERNAL_PATHS if name.startswith("write_end")))
WRITE_TAPER = semantic_path_nets("write_taper")
WRITE_ALL = WRITE_EPOCH | WRITE_START | WRITE_END | WRITE_TAPER
SENSE = semantic_path_nets("sense")
BOOST = semantic_path_nets("boost")
SENSE_BOOST = SENSE | BOOST

REPRESENTATIVE = tuple(
    (item["environment_id"], item["code_id"])
    for item in recovery.CONTRACT.get("diagnostic_cases", (
        {"environment_id": "tt", "code_id": "sense0_interval1_epoch0"},
        {"environment_id": "ss_hot", "code_id": "sense1_interval0_epoch0"},
    )))


def by_id(items: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    matches = [item for item in items if item["id"] == identifier]
    if len(matches) != 1:
        raise ValueError(f"identifier {identifier!r} resolves {len(matches)} times")
    return matches[0]


def variants(source: str) -> dict[str, str]:
    answer = {"baseline": source, "baseline_repeat": source}
    for name, nodes in (
        ("sense", SENSE),
        ("boost", BOOST),
        ("sense_boost", SENSE_BOOST),
        ("epoch", WRITE_EPOCH),
        ("start", WRITE_START),
        ("end", WRITE_END),
        ("taper", WRITE_TAPER),
        ("all_write", WRITE_ALL),
    ):
        answer[f"c_removed_{name}"] = pex_cf.transform(
            source, remove_caps=nodes)
        answer[f"r_near_zero_{name}"] = pex_cf.transform(
            source, short_resistance=nodes)
    return answer


def summarize(case: dict[str, Any]) -> dict[str, Any]:
    paths = case["internal_stage_diagnostics"]
    return {
        "result": case["result"],
        "complete": case["complete"],
        "phase_metrics": case["phase_metrics"],
        "output_rails": {
            key: case["observed"].get(key)
            for phase in ("e", "o")
            for key in (f"{phase}_write_high", f"{phase}_write_low")
        },
        "active_path_failures": {
            phase: {
                name: {
                    "first_transition": spec["first_failed_transition_stage"],
                    "first_rail": spec["first_failed_rail_stage"],
                }
                for name, spec in paths[phase]["paths"].items()
                if spec["active"]
            }
            for phase in ("e", "o")
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.pex.read_text()
    sources = variants(source)
    args.work.mkdir(parents=True, exist_ok=True)
    jobs = []
    hashes = {}
    for variant_id, text in sources.items():
        directory = args.work / variant_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "recovery_dual_control_pulse.pex.spice"
        path.write_text(text)
        hashes[variant_id] = hashlib.sha256(text.encode()).hexdigest()
        for environment_id, code_id in REPRESENTATIVE:
            environment = by_id(base.CONTRACT["environments"], environment_id)
            control = by_id(recovery.CONTROLS, code_id)
            case_work = directory / f"{environment_id}_{code_id}"
            case_work.mkdir(parents=True, exist_ok=True)
            jobs.append((variant_id, environment_id, code_id,
                         (path, "recovery_dual_control_pulse_pex", case_work,
                          environment, control, True)))
    cases = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        pending = [(metadata, executor.submit(recovery.run_case, spec))
                   for *metadata, spec in jobs]
        for metadata, future in pending:
            variant_id, environment_id, code_id = metadata
            cases.append({"variant_id": variant_id,
                          "environment_id": environment_id,
                          "code_id": code_id,
                          **summarize(future.result())})
    baseline = {(item["environment_id"], item["code_id"]): item
                for item in cases if item["variant_id"] == "baseline"}
    ranking = []
    for variant_id in sources:
        if variant_id in ("baseline", "baseline_repeat"):
            continue
        selected = [item for item in cases if item["variant_id"] == variant_id]
        high_gain = sum(
            item["output_rails"][f"{phase}_write_high"]
            - baseline[(item["environment_id"], item["code_id"])]
              ["output_rails"][f"{phase}_write_high"]
            for item in selected for phase in ("e", "o"))
        transition_failures = sum(
            failure["first_transition"] is not None
            for item in selected
            for phase in item["active_path_failures"].values()
            for failure in phase.values())
        rail_failures = sum(
            failure["first_rail"] is not None
            for item in selected
            for phase in item["active_path_failures"].values()
            for failure in phase.values())
        ranking.append({
            "variant_id": variant_id,
            "passing_representative_cases": sum(
                item["result"] == "pass" for item in selected),
            "active_path_transition_failure_count": transition_failures,
            "active_path_rail_failure_count": rail_failures,
            "summed_write_high_gain_v": high_gain,
        })
    ranking.sort(key=lambda item: (
        -item["passing_representative_cases"],
        item["active_path_transition_failure_count"],
        item["active_path_rail_failure_count"],
        -item["summed_write_high_gain_v"], item["variant_id"]))
    repeats = {(item["environment_id"], item["code_id"]): item
               for item in cases if item["variant_id"] == "baseline_repeat"}
    repeat_identical = all(
        repeats[key]["result"] == value["result"]
        and repeats[key]["phase_metrics"] == value["phase_metrics"]
        and repeats[key]["output_rails"] == value["output_rails"]
        for key, value in baseline.items())
    output = {
        "schema_version": 1,
        "claim": "three_control_recovery_semantic_rc_localization",
        "scope": "diagnostic-only exact-PEX counterfactuals",
        "source_pex_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "variant_sha256": hashes,
        "representative_cases": [list(item) for item in REPRESENTATIVE],
        "baseline_repeat_identical": repeat_identical,
        "ranking": ranking,
        "cases": cases,
        "not_a_claim": ["physical qualification", "regenerated geometry",
                        "five-environment closure"],
        "result": "diagnostic",
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"baseline_repeat_identical": repeat_identical,
                      "ranking": ranking}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
