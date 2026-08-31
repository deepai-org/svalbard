#!/usr/bin/env python3
"""Characterize the externally matched 2.4 GHz LNA core over public PVT."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path


MEASURE = re.compile(
    r"^(output_dc|supply_current|gain_2p4g|input_mag_2p4g)\s*=\s*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", re.MULTILINE)
ENVIRONMENTS = (
    ("tt", "typical", 3.30, 27),
    ("ff_cold", "ff", 3.63, -40),
    ("ff_hot", "ff", 2.97, 125),
    ("ss_hot", "ss", 2.97, 125),
    ("ss_cold", "ss", 3.63, -40),
)
BIAS_VOLTAGES = (0.90, 1.00, 1.10, 1.20, 1.30, 1.40, 1.50, 1.60)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fill(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"@{key}@", value)
    missing = sorted(set(re.findall(r"@[A-Z0-9_]+@", rendered)))
    if missing:
        raise ValueError(f"unfilled testbench tokens: {missing}")
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pex", type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    args.work.mkdir(parents=True, exist_ok=True)
    template = (args.source / "lna_ac_tb.spice.in").read_text()
    dut = args.pex or args.source / "lna_cs_core.spice"
    subckt = "wifi_lna_cs_core_pex" if args.pex else "wifi_lna_cs_core"

    def run_case(spec: tuple[str, str, float, int, float]) -> dict[str, object]:
        name, corner, vdd, temperature, bias = spec
        stem = f"{name}_b{bias:.2f}"
        deck = args.work / f"{stem}.spice"
        log = args.work / f"{stem}.log"
        deck.write_text(fill(template, {
            "MOS_CORNER": corner,
            "DUT_INCLUDE": f".include {dut}",
            "DUT_SUBCKT": subckt,
            "TEMP_C": str(temperature),
            "VDD_V": f"{vdd:.2f}",
            "VBIAS_V": f"{bias:.2f}",
        }))
        try:
            with log.open("w") as output:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=90, check=False)
            returncode = run.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
        observed = {key: float(value) for key, value in MEASURE.findall(log.read_text())}
        complete = returncode == 0 and {
            "output_dc", "supply_current", "gain_2p4g", "input_mag_2p4g"
        } <= observed.keys()
        passed = complete and (
            0.40 <= observed["output_dc"] <= vdd - 0.40
            and 0.0001 <= observed["supply_current"] <= 0.020
            and observed["input_mag_2p4g"] >= 0.25
            and observed["gain_2p4g"] >= 1.0
        )
        return {
            "case_id": stem, "environment": [corner, vdd, temperature],
            "bias_v": bias, "complete": complete, "observed": observed,
            "result": "pass" if passed else "fail",
        }

    specs = [(*environment, bias) for environment in ENVIRONMENTS
             for bias in BIAS_VOLTAGES]
    if args.jobs == 1:
        cases = [run_case(spec) for spec in specs]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            cases = list(pool.map(run_case, specs))
    # This is deliberately a fixed external bench bias, not a simulator-picked
    # calibration code.  A macro that only works by selecting a different ideal
    # source at each corner has not established a realizable bias architecture.
    common_biases = []
    for bias in BIAS_VOLTAGES:
        corner_cases = {
            name: next(case for case in cases
                       if case["environment"] == [corner, vdd, temperature]
                       and case["bias_v"] == bias)
            for name, corner, vdd, temperature in ENVIRONMENTS
        }
        if all(case["result"] == "pass" for case in corner_cases.values()):
            common_biases.append({"bias_v": bias, "cases": corner_cases})
    operating_bias = min(common_biases, key=lambda item: item["bias_v"], default=None)
    result = {
        "schema_version": 1,
        "claim": ("wifi_2p4g_external_passive_lna_core_full_rc_voltage_gain"
                  if args.pex else "wifi_2p4g_external_passive_lna_core_schematic_voltage_gain"),
        "boundary": "external_matching_and_high_impedance_mixer_load",
        "result": "pass" if operating_bias else "fail",
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "common_external_operating_bias": operating_bias,
        "bias_control_status": (
            "external ideal source in this screen; no on-die bias, reference, "
            "or calibration circuit is implemented or claimed"
        ),
        "cases": cases,
        "unavailable_obligations": [
            "noise_figure", "linearity", "blocker_tolerance", "phase_noise",
            "package_and_antenna_em", "regulatory_evm_and_spectral_mask",
            "on_die_bias_reference_and_calibration",
        ],
        "source_sha256": digest(args.source / "lna_cs_core.spice"),
        "testbench_sha256": digest(args.source / "lna_ac_tb.spice.in"),
        "runner_sha256": digest(Path(__file__)),
    }
    if args.pex:
        result["pex_sha256"] = digest(args.pex)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": result["result"], "common_external_bias_v": (
        operating_bias["bias_v"] if operating_bias else None
    )}, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
