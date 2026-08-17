#!/usr/bin/env python3
"""Run a full-RC PRBS-7 transient and extract eye/jitter statistics."""

from __future__ import annotations

import argparse
import bisect
import json
import math
import re
import statistics
import subprocess
from pathlib import Path


def prbs7() -> list[int]:
    state = 0x7f
    bits = []
    for _ in range(127):
        bits.append(state & 1)
        feedback = ((state >> 6) ^ (state >> 5)) & 1
        state = ((state << 1) & 0x7e) | feedback
    return bits


def pwl(bits: list[int], complement: bool, ui_ps: float = 400.0,
        edge_ps: float = 20.0, start_ps: float = 100.0) -> str:
    levels = [3.3 * ((1 - bit) if complement else bit) for bit in bits]
    points = [(0.0, levels[0]), (start_ps, levels[0])]
    for index in range(1, len(levels)):
        boundary = start_ps + index * ui_ps
        if levels[index] != levels[index - 1]:
            points.extend([(boundary - edge_ps / 2, levels[index - 1]),
                           (boundary + edge_ps / 2, levels[index])])
    stop = start_ps + len(levels) * ui_ps
    points.append((stop, levels[-1]))
    return " ".join(f"{time:g}p {level:g}" for time, level in points)


def instantiate(template: str, values: dict[str, str]) -> str:
    result = template
    for name, value in values.items():
        result = result.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", result)))
    if remaining:
        raise ValueError(f"unfilled SPICE tokens: {remaining}")
    return result


def interpolate(times: list[float], values: list[float], target: float) -> float:
    index = bisect.bisect_left(times, target)
    if index <= 0:
        return values[0]
    if index >= len(times):
        return values[-1]
    fraction = (target - times[index - 1]) / (times[index] - times[index - 1])
    return values[index - 1] + fraction * (values[index] - values[index - 1])


def crossing_after(times: list[float], values: list[float], start: float, stop: float) -> float | None:
    index = max(1, bisect.bisect_left(times, start))
    while index < len(times) and times[index] <= stop:
        if values[index - 1] * values[index] <= 0 and values[index] != values[index - 1]:
            fraction = -values[index - 1] / (values[index] - values[index - 1])
            return times[index - 1] + fraction * (times[index] - times[index - 1])
        index += 1
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pex", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    sequence = prbs7() * 2
    stop_ps = 100.0 + len(sequence) * 400.0
    wave = args.work / "prbs.dat"
    template = (args.source / "extracted_prbs_tb.spice.in").read_text()
    deck = args.work / "prbs.spice"
    deck.write_text(instantiate(template, {"PEX_PATH": str(args.pex),
                                           "INP_PWL": pwl(sequence, False),
                                           "INN_PWL": pwl(sequence, True),
                                           "TSTOP": f"{stop_ps:g}p",
                                           "WAVE_DATA": str(wave)}))
    log = args.work / "prbs.log"
    with log.open("w") as output:
        run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                             stderr=subprocess.STDOUT, timeout=180, check=False)
    rows = []
    if wave.exists():
        for line in wave.read_text().splitlines():
            try:
                row = [float(field) for field in line.split()]
            except ValueError:
                continue
            if len(row) >= 2:
                rows.append(row)
    times = [row[0] for row in rows]
    values = [row[1] for row in rows]
    sample_margins = []
    delays = []
    missing_crossings = 0
    for index in range(127, len(sequence)):
        center = (100.0 + (index + 0.5) * 400.0) * 1e-12
        value = interpolate(times, values, center)
        sample_margins.append((value if sequence[index] else -value))
        if sequence[index] != sequence[index - 1]:
            boundary = (100.0 + index * 400.0) * 1e-12
            crossing = crossing_after(times, values, boundary - 20e-12, boundary + 150e-12)
            if crossing is None:
                missing_crossings += 1
            else:
                delays.append((crossing - boundary) * 1e12)
    mean_delay = statistics.mean(delays) if delays else math.nan
    jitter = [delay - mean_delay for delay in delays]
    result = {
        "schema_version": 1,
        "result": "pass" if run.returncode == 0 and len(rows) > 100 and not missing_crossings else "fail",
        "bits_analyzed": 127,
        "transitions_analyzed": len(delays),
        "missing_crossings": missing_crossings,
        "minimum_center_eye_margin_v": min(sample_margins) if sample_margins else math.nan,
        "mean_center_eye_margin_v": statistics.mean(sample_margins) if sample_margins else math.nan,
        "crossing_delay_mean_ps": mean_delay,
        "deterministic_jitter_pp_ps": max(jitter) - min(jitter) if jitter else math.nan,
        "deterministic_jitter_rms_ps": math.sqrt(statistics.mean(value * value for value in jitter)) if jitter else math.nan,
        "waveform_points": len(rows),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
