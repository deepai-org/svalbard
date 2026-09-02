#!/usr/bin/env python3
"""Dynamic PRBS7 localization through the exact routed event/lane parent."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import run_exact_pex as base


HERE = Path(__file__).resolve().parent
MEASURE = re.compile(r"^(\w+)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
UI_S = 400e-12
DATA_START_S = 500e-12
SAMPLE_START = {"e": 8.55e-9, "o": 8.75e-9}
PHASE_POLARITY = {"e": 1, "o": -1}


def prbs7(count: int, seed: int = 0x5D) -> list[int]:
    """Return a deterministic x^7+x^6+1 sequence as +/-1 symbols."""
    state = seed & 0x7F
    base.require(state != 0, "PRBS7 seed must be nonzero")
    symbols = []
    for _ in range(count):
        symbols.append(1 if state & 1 else -1)
        feedback = ((state >> 6) ^ (state >> 5)) & 1
        state = ((state << 1) & 0x7E) | feedback
    return symbols


def source_pwl(symbols: list[int], vdd: float, positive: bool) -> str:
    vmid, amplitude, edge = vdd / 2, 0.10, 10e-12
    values = [(vmid + amplitude * symbol * (1 if positive else -1))
              for symbol in symbols]
    points = [(0.0, 0.0), (DATA_START_S, values[0])]
    for index, value in enumerate(values[1:], 1):
        transition = DATA_START_S + index * UI_S
        points.extend([(transition - edge, values[index - 1]),
                       (transition + edge, value)])
    points.append((DATA_START_S + len(values) * UI_S, values[-1]))
    return " ".join(f"{time:.12g} {value:.9g}" for time, value in points)


def compile_deck(pex: Path, environment: dict, symbols: list[int],
                 sample_count: int) -> str:
    deck = base.compile_deck(pex, environment)
    deck = re.sub(r"VRXP RXP_SRC 0 PWL\([^\n]+\)",
                  f"VRXP RXP_SRC 0 PWL({source_pwl(symbols, environment['vdd_v'], True)})",
                  deck)
    deck = re.sub(r"VRXN RXN_SRC 0 PWL\([^\n]+\)",
                  f"VRXN RXN_SRC 0 PWL({source_pwl(symbols, environment['vdd_v'], False)})",
                  deck)
    stop = max(SAMPLE_START.values()) + (sample_count - 1) * 800e-12 + 50e-12
    deck = deck.replace("tran 1p 12.8n uic", f"tran 1p {stop:.12g} uic")
    dynamic_measures = []
    for phase in ("e", "o"):
        for index in range(sample_count):
            instant = SAMPLE_START[phase] + index * 800e-12
            dynamic_measures.append(
                f"meas tran dyn_{phase}_{index} find {phase}_q_diff_vec at={instant:.12g}")
    marker = "meas tran supply_current avg isupply from=8n to=12.8n"
    deck = deck.replace(marker, "\n".join(dynamic_measures) + "\n" + marker)
    return deck


def symbol_at(symbols: list[int], instant: float, latency_ui: int) -> int | None:
    index = math.floor((instant - DATA_START_S) / UI_S) - latency_ui
    return symbols[index] if 0 <= index < len(symbols) else None


def score(observed: dict[str, float], symbols: list[int], sample_count: int,
          margin_v: float = 0.5) -> dict:
    latency_results = []
    for latency in range(9):
        phase_results = {}
        for phase in ("e", "o"):
            comparisons = []
            for index in range(sample_count):
                instant = SAMPLE_START[phase] + index * 800e-12
                expected = symbol_at(symbols, instant, latency)
                value = observed.get(f"dyn_{phase}_{index}")
                if expected is not None and value is not None:
                    signed_margin = value * expected * PHASE_POLARITY[phase]
                    comparisons.append({"index": index, "expected_symbol": expected,
                                        "observed_v": value,
                                        "signed_margin_v": signed_margin})
            phase_results[phase] = {
                "count": len(comparisons),
                "minimum_signed_margin_v": (min(x["signed_margin_v"] for x in comparisons)
                                             if comparisons else None),
                "pass": bool(comparisons) and all(
                    x["signed_margin_v"] >= margin_v for x in comparisons),
                "comparisons": comparisons,
            }
        latency_results.append({"latency_ui": latency, "phases": phase_results,
                                "pass": all(item["pass"] for item in phase_results.values())})
    passing = [item["latency_ui"] for item in latency_results if item["pass"]]
    independent = {phase: [item["latency_ui"] for item in latency_results
                           if item["phases"][phase]["pass"]]
                   for phase in ("e", "o")}
    return {"margin_threshold_v": margin_v, "common_passing_latency_ui": passing,
            "independent_phase_passing_latency_ui": independent,
            "latency_results": latency_results,
            "result": "pass" if len(passing) == 1 else "fail"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pex", type=Path, default=HERE / "event_lane_routed_parent.pex.spice")
    parser.add_argument("--physical", type=Path, default=HERE / "physical_result.json")
    parser.add_argument("--environment-id", default="tt")
    parser.add_argument("--sample-count", type=int, default=10)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--allow-fail", action="store_true")
    args = parser.parse_args()
    base.require(4 <= args.sample_count <= 16, "sample count must be 4--16")
    physical = json.loads(args.physical.read_text())
    base.require(physical.get("result") == "pass" and physical.get("lvs_unique") is True,
                 "physical evidence is not passing unique LVS")
    base.require(physical.get("identity", {}).get("pex_sha256") == base.digest(args.pex),
                 "PEX does not match physical evidence")
    environments = {item["id"]: item for item in base.HCLK_CONTRACT["environments"]}
    base.require(args.environment_id in environments, "unknown environment")
    environment = environments[args.environment_id]
    symbols = prbs7(48)
    args.work.mkdir(parents=True, exist_ok=True)
    deck_path, log_path = args.work / "dynamic.spice", args.work / "dynamic.log"
    deck_path.write_text(compile_deck(args.pex.resolve(), environment, symbols,
                                      args.sample_count))
    try:
        with log_path.open("w") as output:
            proc = subprocess.run(["ngspice", "-b", str(deck_path)], stdout=output,
                                  stderr=subprocess.STDOUT, timeout=args.timeout)
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        returncode = 124
    text = log_path.read_text()
    observed = {key: float(value) for key, value in MEASURE.findall(text)}
    scored = score(observed, symbols, args.sample_count)
    complete = (returncode == 0 and all(f"dyn_{phase}_{index}" in observed
                for phase in ("e", "o") for index in range(args.sample_count)))
    passed = complete and scored["result"] == "pass"
    result = {"schema_version": 1,
              "claim": "exact_routed_parent_dynamic_prbs7_common_latency_screen",
              "scope": "ideal differential PRBS7 source into one hash-bound full-RC parent",
              "environment_id": args.environment_id,
              "pex_sha256": base.digest(args.pex),
              "physical_sha256": base.digest(args.physical),
              "deck_sha256": base.digest(deck_path), "log_sha256": base.digest(log_path),
              "stimulus": {"pattern": "prbs7", "seed": "0x5d",
                           "serial_rate_hz": 2.5e9, "symbol_count": len(symbols),
                           "sample_count_per_phase": args.sample_count},
              "fixed_phase_polarity": PHASE_POLARITY, "returncode": returncode,
              "complete": complete, "score": scored,
              "diagnostic_log_tail": [] if complete else text.splitlines()[-40:],
              "not_a_claim": ["channel/package closure", "BER", "closed CDR",
                              "PCIe compliance or silicon yield"],
              "result": "pass" if passed else "fail"}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"], "complete": complete,
                      "common_passing_latency_ui": scored["common_passing_latency_ui"],
                      "independent": scored["independent_phase_passing_latency_ui"]},
                     sort_keys=True))
    if not passed and not args.allow_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
