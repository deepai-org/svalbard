#!/usr/bin/env python3
"""Verify all paths and a nonoverlap handoff through full-RC selector-tree PEX."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import statistics
import subprocess
from pathlib import Path

SCALAR = re.compile(r"^(current_late|current_max)\s*=\s*([-+0-9.eE]+)", re.MULTILINE)
ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27, 0),
    ("ff", "res_ff", 3.63, -40, 3),
    ("ff", "res_ss", 2.97, 125, 5),
    ("ss", "res_ff", 2.97, 125, 8),
    ("ss", "res_ss", 2.97, 125, 11),
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled tokens: {remaining}")
    return template


def path(leaf: int) -> list[tuple[int, str]]:
    return [
        (leaf // 2, "a" if leaf % 2 == 0 else "b"),
        (8 + leaf // 4, "a" if (leaf // 2) % 2 == 0 else "b"),
        (12 + leaf // 8, "a" if (leaf // 4) % 2 == 0 else "b"),
        (14, "a" if leaf < 8 else "b"),
    ]


def tree_instance() -> str:
    pins = []
    for leaf in range(12):
        pins.extend((f"I{leaf}P", f"I{leaf}N"))
    pins.append("VDD")
    for node in range(15):
        pins.extend((f"S{node}A", f"S{node}B", f"S{node}BUF"))
    pins.extend(("VDD", "0", "OUTP", "OUTN", "vco_selector_tree_pex"))
    lines = ["XTREE " + " ".join(pins[:12])]
    for index in range(12, len(pins), 12):
        lines.append("+ " + " ".join(pins[index:index + 12]))
    return "\n".join(lines)


def input_sources(vdd: float, selected_leaf: int, selected_hz: float = 2.5e9,
                  handoff_leaf: int | None = None, handoff_hz: float = 2.5e9) -> str:
    lines = []
    common_mode = 0.72 * vdd
    for leaf in range(12):
        if leaf == selected_leaf:
            frequency = selected_hz
        elif handoff_leaf is not None and leaf == handoff_leaf:
            frequency = handoff_hz
        else:
            frequency = 1.75e9 + leaf * 35e6
        phase = (leaf * 29) % 360
        lines.append(f"VI{leaf}P I{leaf}P 0 SIN({common_mode:.6f} 0.20 {frequency:.9g} 0 0 {phase})")
        lines.append(f"VI{leaf}N I{leaf}N 0 SIN({common_mode:.6f} 0.20 {frequency:.9g} 0 0 {phase + 180})")
    return "\n".join(lines)


def static_controls(leaf: int, active: float, buffer: float) -> str:
    selected = dict(path(leaf))
    lines = []
    for node in range(15):
        branch = selected.get(node)
        lines.append(f"VS{node}A S{node}A 0 {active:.2f}" if branch == "a" else f"VS{node}A S{node}A 0 0")
        lines.append(f"VS{node}B S{node}B 0 {active:.2f}" if branch == "b" else f"VS{node}B S{node}B 0 0")
        lines.append(f"VS{node}BUF S{node}BUF 0 {buffer:.2f}" if branch else f"VS{node}BUF S{node}BUF 0 0")
    return "\n".join(lines)


def handoff_controls(old_leaf: int, new_leaf: int, active: float, buffer: float) -> str:
    old, new = dict(path(old_leaf)), dict(path(new_leaf))
    lines = []
    for node in range(15):
        for suffix, branch in (("A", "a"), ("B", "b")):
            old_on, new_on = old.get(node) == branch, new.get(node) == branch
            if old_on and new_on:
                source = f"{active:.2f}"
            elif old_on:
                source = f"PWL(0 {active:.2f} 8n {active:.2f} 8.05n 0)"
            elif new_on:
                source = f"PWL(0 0 9n 0 9.05n {active:.2f})"
            else:
                source = "0"
            lines.append(f"VS{node}{suffix} S{node}{suffix} 0 {source}")
        old_on, new_on = node in old, node in new
        if old_on and new_on:
            source = f"PWL(0 {buffer:.2f} 8n {buffer:.2f} 8.05n 0 9n 0 9.05n {buffer:.2f})"
        elif old_on:
            source = f"PWL(0 {buffer:.2f} 8n {buffer:.2f} 8.05n 0)"
        elif new_on:
            source = f"PWL(0 0 9n 0 9.05n {buffer:.2f})"
        else:
            source = "0"
        lines.append(f"VS{node}BUF S{node}BUF 0 {source}")
    return "\n".join(lines)


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


def metrics(times: list[float], values: list[float], start: float, stop: float,
            expected_hz: float | None = None) -> dict[str, float]:
    window = [value for time, value in zip(times, values) if start <= time <= stop]
    crossings = []
    for index in range(1, len(times)):
        if start <= times[index] <= stop and values[index - 1] < 0 <= values[index]:
            fraction = -values[index - 1] / (values[index] - values[index - 1])
            crossings.append(times[index - 1] + fraction * (times[index] - times[index - 1]))
    periods = [upper - lower for lower, upper in zip(crossings, crossings[1:])]
    mean_period = statistics.mean(periods) if periods else math.inf
    jitter = [period - mean_period for period in periods]
    frequency = 1 / mean_period if math.isfinite(mean_period) else 0.0
    return {
        "crossing_count": len(crossings), "frequency_hz": frequency,
        "frequency_error_fraction": (abs(frequency - expected_hz) / expected_hz
                                     if expected_hz else 0.0),
        "cycle_jitter_pp_s": max(jitter) - min(jitter) if jitter else math.inf,
        "differential_high_v": max(window) if window else -math.inf,
        "differential_low_v": min(window) if window else math.inf,
        "differential_peak_v": max((abs(value) for value in window), default=math.inf),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "selector_tree_tb.spice.in").read_text()
    specs = [("typical", "res_typical", 3.30, 27, leaf, 1.35, 1.20)
             for leaf in range(12)]
    # Four cascaded selector stages need the strongest already-qualified
    # selector bias code in the slow/hot/low-supply environments.  This is the
    # realizable code-6 endpoint from the two-input selector bank, not an
    # interpolated or netlist-only device change.
    specs.extend((mos, resistor, supply, temperature, leaf,
                  1.50 if mos == "ss" else 1.35,
                  1.35 if mos == "ss" else 1.20)
                 for mos, resistor, supply, temperature, leaf in ENVIRONMENTS[1:])

    def simulate(spec: tuple[str, str, float, int, int, float, float]) -> dict[str, object]:
        mos, resistor, supply, temperature, leaf, active, buffer = spec
        case_id = f"{mos}_{resistor}_{supply:.2f}_{temperature:+d}_leaf{leaf}".replace("+", "p").replace("-", "m").replace(".", "p")
        deck, log, wave = (args.work / f"{case_id}.{suffix}" for suffix in ("spice", "log", "dat"))
        deck.write_text(instantiate(template, {
            "MOS_CORNER": mos, "RES_CORNER": resistor, "TEMP_C": str(temperature),
            "VDD_V": f"{supply:.2f}", "TREE_PEX_PATH": str(args.pex),
            "INPUT_SOURCES": input_sources(supply, leaf),
            "CONTROL_SOURCES": static_controls(leaf, active, buffer),
            "TREE_INSTANCE": tree_instance(), "WAVE_PATH": str(wave),
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=240, check=False)
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        timing = metrics(*waveform(wave), 10e-9, 20e-9, 2.5e9)
        passed = (run.returncode == 0 and len(observed) == 2
                  and timing["crossing_count"] >= 20
                  and timing["frequency_error_fraction"] <= 0.005
                  and timing["cycle_jitter_pp_s"] <= 20e-12
                  and timing["differential_high_v"] >= 0.20
                  and timing["differential_low_v"] <= -0.20
                  and 0.005 <= observed["current_late"] <= 0.040
                  and observed["current_max"] <= 0.050)
        return {"id": case_id, "environment": [mos, resistor, supply, temperature],
                "selected_leaf": leaf, "active_tail_bias_v": active,
                "buffer_tail_bias_v": buffer, "observed": observed,
                "timing": timing, "result": "pass" if passed else "fail"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))

    handoff_dir = args.work / "handoff"
    handoff_dir.mkdir(exist_ok=True)
    deck, log, wave = handoff_dir / "case.spice", handoff_dir / "case.log", handoff_dir / "case.dat"
    deck.write_text(instantiate(template, {
        "MOS_CORNER": "typical", "RES_CORNER": "res_typical", "TEMP_C": "27",
        "VDD_V": "3.30", "TREE_PEX_PATH": str(args.pex),
        "INPUT_SOURCES": input_sources(3.30, 0, 2.4e9, 11, 2.6e9),
        "CONTROL_SOURCES": handoff_controls(0, 11, 1.35, 1.20),
        "TREE_INSTANCE": tree_instance(), "WAVE_PATH": str(wave),
    }))
    with log.open("w") as output:
        run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                             stderr=subprocess.STDOUT, timeout=240, check=False)
    observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
    times, values = waveform(wave)
    before = metrics(times, values, 3e-9, 7e-9, 2.4e9)
    gap = metrics(times, values, 8.3e-9, 8.8e-9)
    after = metrics(times, values, 11e-9, 19e-9, 2.6e9)
    handoff_pass = (run.returncode == 0 and len(observed) == 2
                    and before["frequency_error_fraction"] <= 0.005
                    and after["frequency_error_fraction"] <= 0.005
                    and before["differential_high_v"] >= 0.20
                    and before["differential_low_v"] <= -0.20
                    and after["differential_high_v"] >= 0.20
                    and after["differential_low_v"] <= -0.20
                    and gap["differential_peak_v"] <= 0.05
                    and observed["current_max"] <= 0.050)
    handoff = {"old_leaf": 0, "new_leaf": 11, "dead_time_s": 0.95e-9,
               "controls_overlap": False, "before": before, "gap": gap, "after": after,
               "observed": observed, "result": "pass" if handoff_pass else "fail"}

    passed = all(case["result"] == "pass" for case in cases) and handoff_pass
    result = {"schema_version": 1, "claim": "full_rc_twelve_leaf_selector_tree",
              "pex_sha256": hashlib.sha256(args.pex.read_bytes()).hexdigest(),
              "case_count": len(cases), "passing_case_count": sum(c["result"] == "pass" for c in cases),
              "nominal_leaf_count": 12,
              "environment_count": 5,
              "handoff": handoff, "cases": cases, "result": "pass" if passed else "fail"}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"selector tree extracted: {result['passing_case_count']}/{result['case_count']}; "
          f"handoff={handoff['result']}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
