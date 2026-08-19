#!/usr/bin/env python3
"""Compose two extracted VCOs with the extracted one-hot selector."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path

SCALAR = re.compile(r"^(current_late|current_max)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)


@dataclass(frozen=True)
class Case:
    name: str
    vctrl_a: str
    vctrl_b: str
    kick_ap: str
    kick_an: str
    kick_bp: str
    kick_bn: str
    sel_a: str
    sel_b: str
    sel_buf: str
    selected: str
    handoff: bool = False
    unselected_active: bool = False


def pulse(delay: str, polarity: str) -> tuple[str, str]:
    source = f"PULSE(0 3.3 {delay} 20p 20p 250p 100n)"
    return (source, "0") if polarity == "p" else ("0", source)


KA_P, KA_N = pulse("1n", "p")
KB_P, KB_N = pulse("1n", "n")
KH_P, KH_N = pulse("11.2n", "n")
STATIC_A = "PWL(0 0 3n 0 3.1n 1.35)"
STATIC_B = "PWL(0 0 3n 0 3.1n 1.35)"
STATIC_BUF = "PWL(0 0 3n 0 3.1n 1.20)"
CASES = (
    Case("select_a_b_powered_down", "PWL(0 0 500p 0.98)", "0",
         KA_P, KA_N, "0", "0", STATIC_A, "0", STATIC_BUF, "a"),
    Case("select_b_a_powered_down", "0", "PWL(0 0 500p 0.98)",
         "0", "0", KB_P, KB_N, "0", STATIC_B, STATIC_BUF, "b"),
    Case("select_a_live_b_aggressor", "PWL(0 0 500p 0.88)", "PWL(0 0 500p 1.08)",
         KA_P, KA_N, KB_P, KB_N, STATIC_A, "0", STATIC_BUF, "a",
         unselected_active=True),
    Case("select_b_live_a_aggressor", "PWL(0 0 500p 0.88)", "PWL(0 0 500p 1.08)",
         KA_P, KA_N, KB_P, KB_N, "0", STATIC_B, STATIC_BUF, "b",
         unselected_active=True),
    Case("break_before_make_a_to_b",
         "PWL(0 0 500p 0.98 10n 0.98 10.2n 0)",
         "PWL(0 0 10.5n 0 11n 1.08)", KA_P, KA_N, KH_P, KH_N,
         "PWL(0 0 3n 0 3.1n 1.35 10n 1.35 10.1n 0)",
         "PWL(0 0 13n 0 13.1n 1.35)",
         "PWL(0 0 3n 0 3.1n 1.20 10n 1.20 10.1n 0 13n 0 13.1n 1.20)",
         "b", handoff=True),
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return template


def waveform(path: Path) -> tuple[list[float], list[float]]:
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                row = [float(field) for field in line.split()]
            except ValueError:
                continue
            if len(row) >= 2:
                rows.append(row)
    return [row[0] for row in rows], [row[1] for row in rows]


def metrics(times: list[float], values: list[float], start: float, stop: float) -> dict[str, float]:
    crossings = []
    window = [value for time, value in zip(times, values) if start <= time <= stop]
    for index in range(1, len(times)):
        if not start <= times[index] <= stop:
            continue
        if values[index - 1] < 0 <= values[index] and values[index] != values[index - 1]:
            fraction = -values[index - 1] / (values[index] - values[index - 1])
            crossings.append(times[index - 1] + fraction * (times[index] - times[index - 1]))
    periods = [upper - lower for lower, upper in zip(crossings, crossings[1:])]
    mean_period = statistics.mean(periods) if periods else math.inf
    jitter = [period - mean_period for period in periods]
    return {
        "crossing_count": len(crossings),
        "frequency_hz": 1 / mean_period if math.isfinite(mean_period) else 0.0,
        "cycle_jitter_pp_s": max(jitter) - min(jitter) if jitter else math.inf,
        "differential_high_v": max(window) if window else -math.inf,
        "differential_low_v": min(window) if window else math.inf,
        "differential_peak_v": max((abs(value) for value in window), default=math.inf),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--tile-pex", type=Path, required=True)
    parser.add_argument("--assist-pex", type=Path, required=True)
    parser.add_argument("--selector-pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "selector_vco_tb.spice.in").read_text()
    cases = []
    for spec in CASES:
        case_dir = args.work / spec.name
        case_dir.mkdir(exist_ok=True)
        deck, log = case_dir / "case.spice", case_dir / "case.log"
        waves = {name: case_dir / f"{name}.dat" for name in ("a", "b", "out")}
        deck.write_text(instantiate(template, {
            "TILE_PEX_PATH": str(args.tile_pex), "ASSIST_PEX_PATH": str(args.assist_pex),
            "SELECTOR_PEX_PATH": str(args.selector_pex),
            "VCTRLA_SOURCE": spec.vctrl_a, "VCTRLB_SOURCE": spec.vctrl_b,
            "KICKAP_SOURCE": spec.kick_ap, "KICKAN_SOURCE": spec.kick_an,
            "KICKBP_SOURCE": spec.kick_bp, "KICKBN_SOURCE": spec.kick_bn,
            "SELA_SOURCE": spec.sel_a, "SELB_SOURCE": spec.sel_b,
            "SELBUF_SOURCE": spec.sel_buf,
            "A_WAVE_PATH": str(waves["a"]), "B_WAVE_PATH": str(waves["b"]),
            "OUT_WAVE_PATH": str(waves["out"]),
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=180, check=False)
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        wave_data = {name: waveform(path) for name, path in waves.items()}
        if spec.handoff:
            a_before = metrics(*wave_data["a"], 5e-9, 9e-9)
            out_before = metrics(*wave_data["out"], 5e-9, 9e-9)
            b_after = metrics(*wave_data["b"], 15e-9, 25e-9)
            out_after = metrics(*wave_data["out"], 15e-9, 25e-9)
            gap = metrics(*wave_data["out"], 10.5e-9, 12.5e-9)
            before_error = abs(out_before["frequency_hz"] - a_before["frequency_hz"]) / a_before["frequency_hz"]
            after_error = abs(out_after["frequency_hz"] - b_after["frequency_hz"]) / b_after["frequency_hz"]
            passed = (run.returncode == 0 and len(observed) == 2
                      and before_error <= 0.005 and after_error <= 0.005
                      and out_before["differential_high_v"] >= 0.20
                      and out_before["differential_low_v"] <= -0.20
                      and out_after["differential_high_v"] >= 0.20
                      and out_after["differential_low_v"] <= -0.20
                      and gap["differential_peak_v"] <= 0.05
                      and observed["current_max"] <= 0.080)
            record = {"a_before": a_before, "output_before": out_before,
                      "b_after": b_after, "output_after": out_after,
                      "gap": gap, "before_frequency_error_fraction": before_error,
                      "after_frequency_error_fraction": after_error}
        else:
            ring = metrics(*wave_data[spec.selected], 15e-9, 25e-9)
            out = metrics(*wave_data["out"], 15e-9, 25e-9)
            other_name = "b" if spec.selected == "a" else "a"
            other = metrics(*wave_data[other_name], 15e-9, 25e-9)
            frequency_error = abs(out["frequency_hz"] - ring["frequency_hz"]) / ring["frequency_hz"]
            powered_down = not spec.unselected_active
            feedthrough_ratio = other["differential_peak_v"] / ring["differential_peak_v"]
            feedthrough_db = 20 * math.log10(feedthrough_ratio) if feedthrough_ratio > 0 else -math.inf
            isolation_ok = ((other["differential_peak_v"] <= 0.05 and feedthrough_ratio <= 0.05)
                            if powered_down else
                            abs(other["frequency_hz"] - ring["frequency_hz"]) /
                            ring["frequency_hz"] >= 0.03)
            passed = (run.returncode == 0 and len(observed) == 2
                      and ring["crossing_count"] >= 20 and out["crossing_count"] >= 20
                      and frequency_error <= 0.005 and out["cycle_jitter_pp_s"] <= 10e-12
                      and out["differential_high_v"] >= 0.20
                      and out["differential_low_v"] <= -0.20
                      and isolation_ok and observed["current_max"] <= 0.080)
            record = {"selected_ring": ring, "unselected_ring": other,
                      "output": out, "output_frequency_error_fraction": frequency_error,
                      "unselected_powered_down": powered_down,
                      "inactive_feedthrough_ratio": feedthrough_ratio if powered_down else None,
                      "inactive_feedthrough_db": feedthrough_db if powered_down else None}
        cases.append({"id": spec.name, "selected": spec.selected, "observed": observed,
                      **record, "result": "pass" if passed else "fail"})

    passed = all(case["result"] == "pass" for case in cases)
    result = {
        "schema_version": 1, "claim": "two_extracted_vcos_with_extracted_selector",
        "initial_condition": "none", "transient_uic": False,
        "tile_pex_sha256": hashlib.sha256(args.tile_pex.read_bytes()).hexdigest(),
        "assist_pex_sha256": hashlib.sha256(args.assist_pex.read_bytes()).hexdigest(),
        "selector_pex_sha256": hashlib.sha256(args.selector_pex.read_bytes()).hexdigest(),
        "case_count": len(cases), "passing_case_count": sum(c["result"] == "pass" for c in cases),
        "cases": cases, "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"VCO selector composition: {result['passing_case_count']}/{result['case_count']}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
