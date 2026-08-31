#!/usr/bin/env python3
"""Rank bounded RC counterfactuals for the selected pulse PEX failures."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import run_selected_pex as selected


PEX_SUFFIX = re.compile(r"\.(?:n|t)\d+$")
SENSE_PATH = {
    "DBG_E_HSM", "DBG_O_HSM", "DBG_E_HSD", "DBG_O_HSD",
    "DBG_E_HSDX", "DBG_O_HSDX", "DBG_E_HSN", "DBG_O_HSN",
    "DBG_E_SB0", "DBG_O_SB0", "DBG_E_SB1", "DBG_O_SB1",
}
BOOST_PATH = {"DBG_E_HSN", "DBG_O_HSN", "DBG_E_RB0", "DBG_O_RB0",
              "DBG_E_RB1", "DBG_O_RB1"}
SENSE_BOOST_PATH = SENSE_PATH | BOOST_PATH
OUTPUTS = {f"{phase}_{signal}" for phase in ("E", "O")
           for signal in ("SENSE", "BOOST", "WRITE")}
CLOCK_CONTROL = {"CLKP_H", "CLKN_H", "SEL0", "SEL1"}
WRITE_PATH = {
    f"DBG_{phase}_{net}"
    for phase in ("EW", "OW")
    for net in ("HSM", "HSLOW", "HEMUX", "HEPOCH", "HBASE", "S0A", "S1A",
                "STR0", "START", "E0", "E1A", "E1", "EMUX", "END", "WIN",
                "WB1", "WB2", "WB3")
} | {"DBG_E_WPN", "DBG_O_WPN"}


def write_nets(*names: str) -> set[str]:
    return {f"DBG_{phase}_{name}" for phase in ("EW", "OW") for name in names}


WRITE_EPOCH_PATH = write_nets("HSM", "HSLOW", "HEMUX", "HEPOCH", "HBASE",
                              "S0A", "S1A", "STR0")
WRITE_INTERVAL_PATH = write_nets("START", "E0", "E1A", "E1", "EMUX", "END")
WRITE_DETECT_TAPER = (write_nets("WIN", "WB1", "WB2", "WB3")
                      | {"DBG_E_WPN", "DBG_O_WPN"})
REPRESENTATIVE_CASES = (("tt", "interval1_epoch0"),
                        ("ss_hot", "interval0_epoch0"))


def logical(node: str) -> str:
    return PEX_SUFFIX.sub("", node)


def transform(text: str, *, remove_caps: set[str] | None = None,
              remove_all_caps: bool = False,
              short_resistance: set[str] | None = None,
              short_all_resistance: bool = False) -> str:
    """Return a diagnostic-only PEX variant without changing its devices."""
    answer = []
    for raw in text.splitlines():
        fields = raw.split()
        kind = fields[0][0].upper() if fields else ""
        if kind == "C" and len(fields) >= 4:
            incident = {logical(fields[1]), logical(fields[2])}
            if remove_all_caps or (remove_caps and incident & remove_caps):
                continue
        if kind == "R" and len(fields) >= 4:
            incident = {logical(fields[1]), logical(fields[2])}
            if short_all_resistance or (short_resistance
                                        and incident <= short_resistance):
                fields[3] = "1m"
                raw = " ".join(fields)
        answer.append(raw)
    return "\n".join(answer) + "\n"


def variant_sources(source: str) -> dict[str, str]:
    return {
        "baseline": source,
        "baseline_repeat": source,
        "r_near_zero_all": transform(source, short_all_resistance=True),
        "c_removed_all": transform(source, remove_all_caps=True),
        "c_removed_outputs": transform(source, remove_caps=OUTPUTS),
        "c_removed_sense_path": transform(source, remove_caps=SENSE_PATH),
        "c_removed_clock_control": transform(source,
                                               remove_caps=CLOCK_CONTROL),
        "c_removed_write_path": transform(source, remove_caps=WRITE_PATH),
        "c_removed_write_epoch": transform(source,
                                             remove_caps=WRITE_EPOCH_PATH),
        "c_removed_write_interval": transform(source,
                                                remove_caps=WRITE_INTERVAL_PATH),
        "c_removed_write_detect_taper": transform(
            source, remove_caps=WRITE_DETECT_TAPER),
        "r_near_zero_outputs": transform(source, short_resistance=OUTPUTS),
        "r_near_zero_sense_path": transform(source,
                                              short_resistance=SENSE_PATH),
        "r_near_zero_write_path": transform(source,
                                              short_resistance=WRITE_PATH),
        "rc_ideal_sense_boost_path": transform(
            source, remove_caps=SENSE_BOOST_PATH,
            short_resistance=SENSE_BOOST_PATH),
        "rc_ideal_write_path": transform(
            source, remove_caps=WRITE_PATH, short_resistance=WRITE_PATH),
    }


def find_by_id(items: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    matches = [item for item in items if item["id"] == identifier]
    if len(matches) != 1:
        raise ValueError(f"identifier {identifier!r} resolves {len(matches)} times")
    return matches[0]


def summary(case: dict[str, Any]) -> dict[str, Any]:
    observed = case["observed"]
    return {
        "result": case["result"],
        "complete": case["complete"],
        "violation_count": len(case["violations"]),
        "violations": case["violations"],
        "phase_metrics": case["phase_metrics"],
        "key_observations": {
            key: observed.get(key) for key in (
                "e_sense_high", "e_sense_low", "e_boost_high", "e_boost_low",
                "e_write_high", "e_write_low", "o_sense_high", "o_sense_low",
                "o_boost_high", "o_boost_low", "o_write_high", "o_write_low",
                "supply_current")
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variants", nargs="+")
    args = parser.parse_args()
    source = args.pex.read_text()
    variants = variant_sources(source)
    if args.variants:
        unknown = sorted(set(args.variants) - set(variants))
        if unknown:
            raise ValueError(f"unknown localization variants: {unknown}")
        if "baseline" not in args.variants:
            raise ValueError("selected localization variants must include baseline")
        variants = {key: variants[key] for key in args.variants}
    args.work.mkdir(parents=True, exist_ok=True)
    jobs = []
    variant_hashes = {}
    for variant_id, variant_source in variants.items():
        variant_work = args.work / variant_id
        variant_work.mkdir(parents=True, exist_ok=True)
        variant_path = variant_work / "selected_dual_control_pulse.pex.spice"
        variant_path.write_text(variant_source)
        variant_hashes[variant_id] = hashlib.sha256(
            variant_source.encode()).hexdigest()
        for environment_id, code_id in REPRESENTATIVE_CASES:
            environment = find_by_id(selected.base.CONTRACT["environments"],
                                     environment_id)
            code = find_by_id(selected.base.CONTRACT["control_codes"], code_id)
            case_work = variant_work / f"{environment_id}_{code_id}"
            case_work.mkdir(parents=True, exist_ok=True)
            jobs.append((variant_id, environment_id, code_id,
                         (variant_path, "selected_dual_control_pulse_pex",
                          case_work, environment, code)))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [(metadata, executor.submit(selected.run_case, spec))
                   for *metadata, spec in jobs]
        for metadata, future in futures:
            variant_id, environment_id, code_id = metadata
            results.append({"variant_id": variant_id,
                            "environment_id": environment_id,
                            "code_id": code_id,
                            **summary(future.result())})
    baseline = {(item["environment_id"], item["code_id"]): item
                for item in results if item["variant_id"] == "baseline"}
    ranking = []
    for variant_id in variants:
        if variant_id in ("baseline", "baseline_repeat"):
            continue
        cases = [item for item in results if item["variant_id"] == variant_id]
        violation_reduction = sum(
            baseline[(item["environment_id"], item["code_id"])]
            ["violation_count"] - item["violation_count"] for item in cases)
        write_high_gain = sum(
            sum((item["key_observations"].get(f"{phase}_write_high") or 0)
                - (baseline[(item["environment_id"], item["code_id"])]
                   ["key_observations"].get(f"{phase}_write_high") or 0)
                for phase in ("e", "o")) for item in cases)
        ranking.append({"variant_id": variant_id,
                        "violation_reduction": violation_reduction,
                        "summed_write_high_gain_v": write_high_gain,
                        "passing_representative_cases": sum(
                            item["result"] == "pass" for item in cases)})
    ranking.sort(key=lambda item: (-item["passing_representative_cases"],
                                  -item["violation_reduction"],
                                  -item["summed_write_high_gain_v"],
                                  item["variant_id"]))
    repeat_deltas = []
    repeat = {(item["environment_id"], item["code_id"]): item
              for item in results if item["variant_id"] == "baseline_repeat"}
    for identity, baseline_case in baseline.items():
        repeated = repeat.get(identity)
        if repeated is None:
            continue
        numeric_deltas = []
        for phase in ("e", "o"):
            for measure, value in baseline_case["phase_metrics"][phase].items():
                numeric_deltas.append(abs(
                    value - repeated["phase_metrics"][phase][measure]))
        for measure, value in baseline_case["key_observations"].items():
            other = repeated["key_observations"].get(measure)
            if value is not None and other is not None:
                numeric_deltas.append(abs(value - other))
        repeat_deltas.append({
            "environment_id": identity[0], "code_id": identity[1],
            "maximum_absolute_numeric_delta": max(numeric_deltas, default=0.0),
            "same_result": baseline_case["result"] == repeated["result"],
            "same_violation_count": (baseline_case["violation_count"]
                                     == repeated["violation_count"]),
        })
    output = {
        "schema_version": 1,
        "claim": "selected_pulse_pex_rc_counterfactual_localization",
        "scope": "diagnostic-only exact-PEX variants at representative TT and SS/hot failures",
        "source_pex_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "variant_sha256": variant_hashes,
        "representative_cases": [list(item) for item in REPRESENTATIVE_CASES],
        "ranking": ranking,
        "baseline_repeat_check": repeat_deltas,
        "cases": results,
        "not_a_claim": ["modified_netlist_physical_qualification",
                        "regenerated_geometry", "five_environment_closure"],
        "result": "diagnostic",
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"ranking": ranking}, sort_keys=True))


if __name__ == "__main__":
    main()
