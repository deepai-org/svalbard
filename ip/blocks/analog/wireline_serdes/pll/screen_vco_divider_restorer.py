#!/usr/bin/env python3
"""Screen a CML restorer between exact VCO and divider PEX decks."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

SERDES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERDES_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analog_evidence import environment_index, sha256_file  # noqa: E402
from run_vco_divider_composed import CODE_PORTS, bit_sources, instantiate  # noqa: E402

MEASUREMENTS = (
    "vco_startup", "vco_period", "vco_high", "vco_low", "rest_high",
    "rest_low", "div_startup", "div_period_early", "div_period_late",
    "div_high_time", "div_high", "div_low", "div_output_cm", "vco_current",
    "restorer_current", "div_current",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--vco-pex", type=Path, required=True)
    parser.add_argument("--divider-pex", type=Path, required=True)
    parser.add_argument("--vco-baseline", type=Path, required=True)
    parser.add_argument("--divider-physical", type=Path, required=True)
    parser.add_argument("--restorer-pex", type=Path)
    parser.add_argument("--restorer-physical", type=Path)
    parser.add_argument("--restorer-model", type=Path)
    parser.add_argument("--restorer-subckt")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.restorer_model and args.restorer_pex:
        raise SystemExit("choose --restorer-model or --restorer-pex, not both")
    if not 1 <= args.workers <= 16:
        raise SystemExit("--workers must be between 1 and 16")
    restorer_subckt = args.restorer_subckt or (
        "cml_clock_restorer_pex" if args.restorer_pex else "cml_clock_restorer"
    )
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "vco_divider_restorer_tb.spice.in"
    template = template_path.read_text()
    baseline = json.loads(args.vco_baseline.read_text())
    divider_physical = json.loads(args.divider_physical.read_text())
    if baseline.get("pex_sha256") != sha256_file(args.vco_pex):
        raise SystemExit("VCO PEX identity mismatch")
    if divider_physical.get("pex_sha256") != sha256_file(args.divider_pex):
        raise SystemExit("divider PEX identity mismatch")
    by_id = {case["id"]: case for case in baseline["cases"]}
    selected = [by_id[item["selected_case_id"]] for item in baseline["calibration"]
                if args.full or item["environment"][0] == "ss"]
    restorer_physical = None
    if args.restorer_pex:
        if not args.restorer_physical:
            raise SystemExit("--restorer-physical is required with --restorer-pex")
        restorer_physical = json.loads(args.restorer_physical.read_text())
        if restorer_physical.get("result") != "pass" or restorer_physical.get("pex_sha256") != sha256_file(args.restorer_pex):
            raise SystemExit("restorer PEX identity mismatch")
    specs = []
    for case in selected:
        if args.full:
            specs.extend((case, rest_bias, div_bias) for rest_bias in (1.0, 1.2)
                         for div_bias in (0.900, 0.950, 1.000))
            continue
        resistor_corner = case["environment"][1]
        if resistor_corner == "res_ff":
            specs.extend((case, 1.2, div_bias) for div_bias in
                         (0.900, 0.925, 0.950, 0.975, 1.000, 1.025, 1.050, 1.075, 1.100))
        else:
            specs.extend((case, 1.0, div_bias) for div_bias in
                         (0.875, 0.900, 0.925, 0.950))
    pattern = re.compile(rf"^({'|'.join(MEASUREMENTS)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE)

    def simulate(spec: tuple[dict[str, object], float, float]) -> dict[str, object]:
        base, rest_bias, div_bias = spec
        mos, resistor, supply, temperature = base["environment"]
        member = str(base["selected_member"])
        main, regen = (int(base["selected_codes"][key]) for key in ("main", "regen"))
        case_id = f"{base['id']}_rb{rest_bias:.3f}_db{div_bias:.3f}".replace(".", "p")
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        fast_codes = (main, regen) if member == "fast" else (0, 0)
        gain_codes = (main, regen) if member == "gain" else (0, 0)
        sources = bit_sources("F", *fast_codes, float(supply)) + bit_sources("G", *gain_codes, float(supply))
        pulse = f"PULSE(0 {float(supply):.2f} 1n 20p 20p 250p 100n)"
        select = "PWL(0 0 3n 0 3.1n 1.50)"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
            "TEMP_C": str(temperature), "VDD_V": f"{float(supply):.2f}",
            "REST_BIAS_V": f"{rest_bias:.3f}", "DIV_BIAS_V": f"{div_bias:.3f}",
            "REST_LOAD_L": "7.5", "VCO_PEX_PATH": str(args.vco_pex),
            "DIVIDER_PEX_PATH": str(args.divider_pex), "DUT_CODE_PORTS": " ".join(CODE_PORTS),
            "RESTORER_MODEL_PATH": str(args.restorer_pex or args.restorer_model or
                                       (args.source / "clock_restorer.spice")),
            "RESTORER_SUBCKT": restorer_subckt,
            "RESTORER_PARAMS": "" if args.restorer_pex else "params: LOAD_L=7.5u",
            "BIT_SOURCES": "\n".join(sources),
            "FAST_KICKP_SOURCE": pulse if member == "fast" else "0", "FAST_KICKN_SOURCE": "0",
            "GAIN_KICKP_SOURCE": pulse if member == "gain" else "0", "GAIN_KICKN_SOURCE": "0",
            "SEL_A_SOURCE": select if member == "fast" else "0",
            "SEL_B_SOURCE": select if member == "gain" else "0",
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=600, check=False)
        observed = {name: float(value) for name, value in pattern.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(MEASUREMENTS)
        vp, dp = observed.get("vco_period", 0.0), observed.get("div_period_late", 0.0)
        vf, df = (1 / vp if vp > 0 else 0.0), (1 / dp if dp > 0 else 0.0)
        ratio_error = abs(2 * df / vf - 1) if vf > 0 else 1.0
        drift = abs(dp - observed.get("div_period_early", 0.0)) / dp if dp > 0 else 1.0
        duty = abs(observed.get("div_high_time", 0.0)) / dp if dp > 0 else 0.0
        loading = abs(vf / float(base["frequency_hz"]) - 1)
        passed = (
            complete and 1.20e9 <= vf <= 1.30e9 and loading <= 0.05
            and observed["vco_high"] >= 0.15 and observed["vco_low"] <= -0.15
            and observed["rest_high"] >= 0.30 and observed["rest_low"] <= -0.30
            and ratio_error <= 0.01 and drift <= 0.01 and 0.45 <= duty <= 0.55
            and observed["div_high"] >= 0.15 and observed["div_low"] <= -0.15
            and observed["restorer_current"] <= 0.010 and observed["div_current"] <= 0.025
        )
        return {
            "id": case_id, "environment": base["environment"], "restorer_bias_v": rest_bias,
            "divider_bias_v": div_bias, "restorer_load_length_um": 7.5,
            "complete": complete, "observed": observed, "vco_frequency_hz": vf,
            "divider_frequency_hz": df, "divide_ratio_error_fraction": ratio_error,
            "divider_period_drift_fraction": drift, "divider_duty_cycle": duty,
            "vco_loading_frequency_shift_fraction": loading,
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        cases = list(executor.map(simulate, specs))
    calibration = []
    for base in selected:
        members = [case for case in cases if case["environment"] == base["environment"]]
        passing = [case for case in members if case["result"] == "pass"]
        windows = []
        for rest_bias in sorted({case["restorer_bias_v"] for case in members}):
            run = []
            for case in sorted((case for case in members
                                if case["restorer_bias_v"] == rest_bias),
                               key=lambda case: case["divider_bias_v"]):
                if case["result"] == "pass":
                    run.append(case)
                elif run:
                    windows.append(run)
                    run = []
            if run:
                windows.append(run)
        qualifying = [window for window in windows if len(window) >= 3]
        eligible = [case for window in qualifying for case in window]
        choice = min(eligible, key=lambda c: (abs(c["restorer_bias_v"] - 1.2),
                                               abs(c["divider_bias_v"] - 0.9))) if eligible else None
        calibration.append({
            "environment": base["environment"], "candidate_count": len(members),
            "passing_candidate_count": len(passing), "selected_case_id": choice["id"] if choice else None,
            "selected_restorer_bias_v": choice["restorer_bias_v"] if choice else None,
            "selected_divider_bias_v": choice["divider_bias_v"] if choice else None,
            "maximum_contiguous_passing_divider_code_count": max(
                (len(window) for window in windows), default=0
            ),
            "result": "pass" if choice else "fail",
        })
    environment_index(calibration)
    required_environments = 5 if args.full else 2
    passed = len(calibration) == required_environments and all(item["result"] == "pass" for item in calibration)
    result = {
        "schema_version": 1, "claim": (
            "exact_pex_vco_clock_restorer_divider_composition" if args.restorer_pex
            else "schematic_clock_restorer_candidate_with_exact_vco_divider_pex"
        ),
        "physical_qualification": bool(args.restorer_pex), "case_count": len(cases),
        "passing_case_count": sum(c["result"] == "pass" for c in cases),
        "passing_environment_count": sum(c["result"] == "pass" for c in calibration),
        "calibration": calibration, "cases": cases,
        "vco_pex_sha256": sha256_file(args.vco_pex),
        "divider_pex_sha256": sha256_file(args.divider_pex),
        "restorer_pex_sha256": sha256_file(args.restorer_pex) if args.restorer_pex else None,
        "restorer_physical_sha256": sha256_file(args.restorer_physical) if args.restorer_physical else None,
        "restorer_source_sha256": sha256_file(
            args.restorer_model or (args.source / "clock_restorer.spice")
        ),
        "testbench_source_sha256": sha256_file(template_path),
        "simulation_source_sha256": sha256_file(Path(__file__)),
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"VCO/restorer/divider screen: {result['passing_case_count']}/{len(cases)}; "
          f"{result['passing_environment_count']}/{required_environments} env")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
