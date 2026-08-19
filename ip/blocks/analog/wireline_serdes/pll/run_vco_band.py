#!/usr/bin/env python3
"""Qualify startup, selector loading, and shutdown of one physical VCO band."""
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

SCALAR = re.compile(
    r"^(band_current_late|band_current_pre)\s*=\s*([-+0-9.eE]+)", re.MULTILINE
)
KICK_RELEASE_S = 1.30e-9
OPERATING_CONTROL_V = 1.08


@dataclass(frozen=True)
class Case:
    name: str
    polarity: str
    selector_loaded: bool
    shutdown: bool = False


CASES = (
    Case("startup_p_unloaded", "p", False),
    Case("startup_n_unloaded", "n", False),
    Case("startup_p_selector_loaded", "p", True),
    Case("startup_n_selector_loaded", "n", True),
    Case("shutdown_selector_loaded", "p", True, True),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def waveform(path: Path) -> tuple[list[float], list[float]]:
    rows: list[list[float]] = []
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
    crossings: list[float] = []
    window = [value for time, value in zip(times, values) if start <= time <= stop]
    for index in range(1, len(times)):
        if not start <= times[index] <= stop:
            continue
        lower, upper = values[index - 1], values[index]
        if lower < 0 <= upper and upper != lower:
            fraction = -lower / (upper - lower)
            crossings.append(times[index - 1] + fraction * (times[index] - times[index - 1]))
    periods = [upper - lower for lower, upper in zip(crossings, crossings[1:])]
    mean_period = statistics.mean(periods) if periods else math.inf
    jitter = [period - mean_period for period in periods]
    return {
        "crossing_count": len(crossings),
        "first_crossing_s": crossings[0] if crossings else math.inf,
        "frequency_hz": 1.0 / mean_period if math.isfinite(mean_period) else 0.0,
        "cycle_jitter_pp_s": max(jitter) - min(jitter) if jitter else math.inf,
        "differential_high_v": max(window) if window else -math.inf,
        "differential_low_v": min(window) if window else math.inf,
        "differential_peak_v": max((abs(value) for value in window), default=math.inf),
    }


def kick(polarity: str) -> tuple[str, str]:
    pulse = "PULSE(0 3.3 1n 20p 20p 250p 100n)"
    return (pulse, "0") if polarity == "p" else ("0", pulse)


def json_finite(value: object) -> object:
    """Replace non-finite measurement sentinels with JSON null."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_finite(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--band-pex", type=Path, required=True)
    parser.add_argument("--selector-pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "vco_band_tb.spice.in").read_text()
    records: list[dict[str, object]] = []

    for case in CASES:
        case_dir = args.work / case.name
        case_dir.mkdir(exist_ok=True)
        deck, log = case_dir / "case.spice", case_dir / "case.log"
        band_wave, selected_wave = case_dir / "band.dat", case_dir / "selected.dat"
        kick_p, kick_n = kick(case.polarity)
        vctrl = (f"PWL(0 0 500p {OPERATING_CONTROL_V:.2f} 12n "
                 f"{OPERATING_CONTROL_V:.2f} 12.2n 0)" if case.shutdown
                 else f"PWL(0 0 500p {OPERATING_CONTROL_V:.2f})")
        if case.selector_loaded:
            load = (
                "XSELECT CLK_P CLK_N QUIETP QUIETN SELA SELB SELBUF "
                "SELECT_VDD 0 OUT_P OUT_N vco_selector_unit_pex\n"
                "COUTP OUT_P 0 50f\nCOUTN OUT_N 0 50f"
            )
            sela, selbuf = "PWL(0 0 3n 0 3.1n 1.35)", "PWL(0 0 3n 0 3.1n 1.20)"
        else:
            load = (
                "CLOADP CLK_P 0 25f\nCLOADN CLK_N 0 25f\n"
                "EOUTP OUT_P 0 CLK_P 0 1\nEOUTN OUT_N 0 CLK_N 0 1"
            )
            sela, selbuf = "0", "0"
        deck.write_text(instantiate(template, {
            "BAND_PEX_PATH": str(args.band_pex),
            "SELECTOR_PEX_PATH": str(args.selector_pex),
            "VCTRL_SOURCE": vctrl,
            "KICKP_SOURCE": kick_p,
            "KICKN_SOURCE": kick_n,
            "SELA_SOURCE": sela,
            "SELBUF_SOURCE": selbuf,
            "LOAD_NETWORK": load,
            "BAND_WAVE_PATH": str(band_wave),
            "SELECTED_WAVE_PATH": str(selected_wave),
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=180, check=False,
            )
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        band_data, selected_data = waveform(band_wave), waveform(selected_wave)
        startup = metrics(*band_data, KICK_RELEASE_S, 11e-9)
        pre = metrics(*band_data, 6e-9, 11e-9)
        late = metrics(*band_data, 18e-9, 25e-9)
        selected_late = metrics(*selected_data, 18e-9, 25e-9)
        complete = run.returncode == 0 and len(observed) == 2
        startup_delay = startup["first_crossing_s"] - KICK_RELEASE_S
        steady_pass = (
            complete and pre["crossing_count"] >= 8
            and pre["differential_high_v"] >= 0.20
            and pre["differential_low_v"] <= -0.20
            and pre["cycle_jitter_pp_s"] <= 10e-12
            and 2.45e9 <= pre["frequency_hz"] <= 2.55e9
            and 0 <= startup_delay <= 10e-9
            and 0.003 <= observed.get("band_current_pre", math.inf) <= 0.040
        )
        if case.shutdown:
            passed = (
                steady_pass and late["differential_peak_v"] <= 0.05
                and observed.get("band_current_late", math.inf) <= 0.0005
            )
        else:
            output_tracks = True
            if case.selector_loaded:
                frequency_error = abs(
                    selected_late["frequency_hz"] - late["frequency_hz"]
                ) / late["frequency_hz"] if late["frequency_hz"] else math.inf
                output_tracks = (
                    selected_late["crossing_count"] >= 12
                    and selected_late["differential_high_v"] >= 0.20
                    and selected_late["differential_low_v"] <= -0.20
                    and frequency_error <= 0.005
                    and selected_late["cycle_jitter_pp_s"] <= 10e-12
                )
            passed = (
                steady_pass and output_tracks and late["crossing_count"] >= 12
                and late["differential_high_v"] >= 0.20
                and late["differential_low_v"] <= -0.20
                and late["cycle_jitter_pp_s"] <= 10e-12
            )
        records.append({
            "id": case.name,
            "kick_polarity": case.polarity,
            "selector_loaded": case.selector_loaded,
            "shutdown_commanded": case.shutdown,
            "startup_delay_s": startup_delay,
            "band_pre_shutdown": pre,
            "band_late": late,
            "selector_output_late": selected_late,
            "observed": observed,
            "result": "pass" if passed else "fail",
        })

    startup_records = [record for record in records if not record["shutdown_commanded"]]
    polarity_groups = {
        loaded: [record for record in startup_records if record["selector_loaded"] == loaded]
        for loaded in (False, True)
    }
    polarity_mismatches = []
    for loaded, group in polarity_groups.items():
        frequencies = [float(record["band_late"]["frequency_hz"]) for record in group]
        mismatch = ((max(frequencies) - min(frequencies)) / statistics.mean(frequencies)
                    if len(frequencies) == 2 and min(frequencies) > 0 else math.inf)
        polarity_mismatches.append({
            "selector_loaded": loaded,
            "frequency_mismatch_fraction": mismatch,
            "result": "pass" if mismatch <= 0.01 else "fail",
        })
    unloaded_frequency = statistics.mean(
        float(record["band_late"]["frequency_hz"])
        for record in polarity_groups[False]
    )
    loaded_frequency = statistics.mean(
        float(record["band_late"]["frequency_hz"])
        for record in polarity_groups[True]
    )
    loading_shift = abs(loaded_frequency - unloaded_frequency) / unloaded_frequency
    passed = (all(record["result"] == "pass" for record in records)
              and all(item["result"] == "pass" for item in polarity_mismatches)
              and loading_shift <= 0.05)
    result = {
        "schema_version": 1,
        "claim": "full_rc_physical_vco_band_startup_loading_and_shutdown",
        "initial_condition": "none",
        "transient_uic": False,
        "supply_ramp_s": 0.5e-9,
        "operating_control_v": OPERATING_CONTROL_V,
        "frequency_contract_hz": [2.45e9, 2.55e9],
        "band_pex_sha256": digest(args.band_pex),
        "selector_pex_sha256": digest(args.selector_pex),
        "simulation_source_sha256": digest(args.source / "run_vco_band.py"),
        "testbench_template_sha256": digest(args.source / "vco_band_tb.spice.in"),
        "case_count": len(records),
        "passing_case_count": sum(record["result"] == "pass" for record in records),
        "selector_loading_frequency_shift_fraction": loading_shift,
        "polarity_checks": polarity_mismatches,
        "cases": records,
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(json_finite(result), indent=2, sort_keys=True) + "\n")
    print(f"physical VCO band: {result['passing_case_count']}/{result['case_count']} cases; "
          f"selector loading shift={loading_shift:.4%}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
