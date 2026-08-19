#!/usr/bin/env python3
"""Qualify deterministic startup of composed full-RC VCO and assist layouts."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
import argparse

TARGET_HZ = 2.5e9
KICK_START_S = 1.0e-9
KICK_RELEASE_S = 1.27e-9
MEASURE_NAMES = (
    "startup_time", "period", "period_late", "diff_high", "diff_low",
    "output_cm", "supply_current", "prekick_diff",
)
MEASURE = re.compile(
    rf"^({'|'.join(MEASURE_NAMES)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
)


@dataclass(frozen=True)
class Sweep:
    variant: str
    subckt: str
    mos: str
    resistor: str
    supply: float
    temperature: int
    controls: tuple[float, ...]


SWEEPS = (
    Sweep("center", "cml_vco_delay_pex", "typical", "res_typical", 3.30, 27,
          (0.88, 0.98, 1.08)),
    Sweep("slow", "cml_vco_delay_slow_pex", "ff", "res_ff", 3.63, -40,
          (0.88, 0.98, 1.08)),
    Sweep("fast", "cml_vco_delay_fast_pex", "ff", "res_ss", 2.97, 125,
          (0.88, 0.98, 1.18)),
    Sweep("ss_ff_margin_slow", "cml_vco_delay_ss_ff_margin_slow_pex",
          "ss", "res_ff", 2.97, 125, (1.20, 1.25, 1.30)),
    Sweep("ss_ff_margin_fast", "cml_vco_delay_ss_ff_margin_fast_pex",
          "ss", "res_ff", 2.97, 125, (1.20, 1.25, 1.30)),
    Sweep("margin_slow", "cml_vco_delay_margin_slow_pex",
          "ss", "res_ss", 2.97, 125, (1.20, 1.25, 1.40)),
    Sweep("margin_fast", "cml_vco_delay_margin_fast_pex",
          "ss", "res_ss", 2.97, 125, (1.20, 1.25, 1.40)),
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = re.findall(r"@[A-Z0-9_]+@", template)
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def tile_path(pex_dir: Path, variant: str) -> Path:
    suffix = "" if variant == "center" else f"_{variant}"
    return pex_dir / f"cml_vco_delay{suffix}.pex.spice"


def pulse(supply: float) -> str:
    return f"PULSE(0 {supply:.2f} 1n 20p 20p 250p 100n)"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex-dir", type=Path, required=True)
    parser.add_argument("--assist-pex", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "startup_extracted_tb.spice.in").read_text()
    assist_hash = hashlib.sha256(args.assist_pex.read_bytes()).hexdigest()

    specs = []
    for sweep in SWEEPS:
        for control in sweep.controls:
            for polarity in ("p", "n"):
                specs.append((sweep, control, polarity))
    # One no-kick control per environment is diagnostic, never qualification.
    seen_environments: set[tuple[str, str, float, int]] = set()
    for sweep in SWEEPS:
        environment = (sweep.mos, sweep.resistor, sweep.supply, sweep.temperature)
        if environment not in seen_environments:
            specs.append((sweep, sweep.controls[len(sweep.controls) // 2], "none"))
            seen_environments.add(environment)

    def simulate(spec: tuple[Sweep, float, str]) -> dict[str, object]:
        sweep, control, polarity = spec
        pex = tile_path(args.pex_dir, sweep.variant)
        case_id = (f"{sweep.variant}_{sweep.mos}_{sweep.resistor}_"
                   f"{sweep.supply:.2f}_{sweep.temperature:+d}_{control:.2f}_{polarity}")
        case_id = case_id.replace("+", "p").replace("-", "m")
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        kick_p = pulse(sweep.supply) if polarity == "p" else "0"
        kick_n = pulse(sweep.supply) if polarity == "n" else "0"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": sweep.mos,
            "RES_CORNER": sweep.resistor,
            "TEMP_C": str(sweep.temperature),
            "VDD_V": f"{sweep.supply:.2f}",
            "VCTRL_V": f"{control:.2f}",
            "TILE_PEX_PATH": str(pex),
            "TILE_PEX_SUBCKT": sweep.subckt,
            "ASSIST_PEX_PATH": str(args.assist_pex),
            "KICKP_SOURCE": kick_p,
            "KICKN_SOURCE": kick_n,
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=120, check=False,
            )
        observed = {name: float(value) for name, value in MEASURE.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(MEASURE_NAMES)
        frequency = 1.0 / observed["period"] if complete and observed["period"] > 0 else 0.0
        late_frequency = 1.0 / observed["period_late"] if complete and observed["period_late"] > 0 else 0.0
        drift = abs(frequency - late_frequency) / frequency if frequency else 1.0
        startup_delay = observed.get("startup_time", 0.0) - KICK_RELEASE_S
        electrical = (
            complete and drift <= 0.01
            and observed["diff_high"] >= 0.20
            and observed["diff_low"] <= -0.20
            and 0.003 <= observed["supply_current"] <= 0.040
            and 0 <= startup_delay <= 10e-9
        )
        return {
            "id": case_id,
            "variant": sweep.variant,
            "environment": [sweep.mos, sweep.resistor, sweep.supply, sweep.temperature],
            "control_v": control,
            "kick_polarity": polarity,
            "tile_pex_sha256": hashlib.sha256(pex.read_bytes()).hexdigest(),
            "frequency_hz": frequency,
            "late_frequency_hz": late_frequency,
            "period_drift_fraction": drift,
            "startup_delay_s": startup_delay,
            "observed": observed,
            "result": "pass" if electrical else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        cases = list(executor.map(simulate, specs))

    qualified = [case for case in cases if case["kick_polarity"] != "none"]
    paired = []
    pair_keys = sorted({(case["variant"], tuple(case["environment"]), case["control_v"])
                        for case in qualified})
    for variant, environment, control in pair_keys:
        pair = [case for case in qualified if case["variant"] == variant
                and tuple(case["environment"]) == environment
                and case["control_v"] == control]
        frequencies = [float(case["frequency_hz"]) for case in pair]
        mismatch = ((max(frequencies) - min(frequencies)) / (sum(frequencies) / len(frequencies))
                    if len(frequencies) == 2 and min(frequencies) > 0 else 1.0)
        passed = len(pair) == 2 and all(case["result"] == "pass" for case in pair) and mismatch <= 0.01
        paired.append({
            "variant": variant, "environment": list(environment), "control_v": control,
            "kick_polarity_frequency_mismatch_fraction": mismatch,
            "result": "pass" if passed else "fail",
        })

    environments = []
    environment_keys = sorted({tuple(case["environment"]) for case in qualified})
    for environment in environment_keys:
        valid = [case for case in qualified if tuple(case["environment"]) == environment
                 and case["result"] == "pass"]
        minimum = min((float(case["frequency_hz"]) for case in valid), default=0.0)
        maximum = max((float(case["frequency_hz"]) for case in valid), default=0.0)
        covered = minimum <= TARGET_HZ <= maximum
        environments.append({
            "environment": list(environment),
            "passing_case_count": len(valid),
            "minimum_hz": minimum,
            "maximum_hz": maximum,
            "target_bracketed": covered,
            "result": "pass" if covered else "fail",
        })

    passed = (all(case["result"] == "pass" for case in qualified)
              and all(pair["result"] == "pass" for pair in paired)
              and all(environment["result"] == "pass" for environment in environments))
    result = {
        "schema_version": 1,
        "claim": "deterministic_assisted_startup_without_initial_condition",
        "initial_condition": "none",
        "transient_uic": False,
        "supply_ramp_s": 0.5e-9,
        "kick_start_s": KICK_START_S,
        "kick_release_s": KICK_RELEASE_S,
        "assist_pex_sha256": assist_hash,
        "qualified_case_count": len(qualified),
        "passing_qualified_case_count": sum(case["result"] == "pass" for case in qualified),
        "environment_count": len(environments),
        "passing_environment_count": sum(env["result"] == "pass" for env in environments),
        "result": "pass" if passed else "fail",
        "environments": environments,
        "polarity_pairs": paired,
        "cases": cases,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"assisted extracted startup: {result['passing_qualified_case_count']}/"
          f"{result['qualified_case_count']} cases; "
          f"{result['passing_environment_count']}/{result['environment_count']} target environments")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
