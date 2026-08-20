#!/usr/bin/env python3
"""Calibrate and verify the changing-word integrated serializer/TX schematic."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

from run_changing_word import EVEN_BITS, ENVIRONMENTS, ODD_BITS, OFFSETS_PS, instantiate, pwl

BIAS_CANDIDATES_V = (0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rate", type=float, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--pex", type=Path)
    args = parser.parse_args()
    if args.rate not in OFFSETS_PS or not 1 <= args.jobs <= 4:
        parser.error("unsupported rate or job count")
    args.work.mkdir(parents=True, exist_ok=True)
    template_path = args.source / "serializer" / "integrated_tx_tb.spice.in"
    template = template_path.read_text()
    ui = 1.0 / args.rate
    period = 2.0 * ui
    clock_delay = 2.0e-9
    expected = tuple(bit for pair in zip(EVEN_BITS, ODD_BITS) for bit in pair)
    measure_names = tuple(f"tx_{index}" for index in range(len(expected))) + ("supply_current",)
    pattern = re.compile(
        rf"^({'|'.join(measure_names)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
    )

    def simulate(environment: tuple[object, ...], bias: float, offset_ps: int,
                 phase: str) -> dict[str, object]:
        mos, resistor, supply, temperature = environment
        offset = offset_ps * 1e-12
        even_updates = tuple(
            clock_delay + (index - 1) * period + ui + offset
            for index in range(1, len(EVEN_BITS))
        )
        odd_updates = tuple(
            clock_delay + index * period + offset
            for index in range(1, len(ODD_BITS))
        )
        sample_times = tuple(
            clock_delay + index * period + sample_phase * ui
            for index in range(len(EVEN_BITS)) for sample_phase in (0.5, 1.5)
        )
        measures = "\n".join(
            f"meas tran tx_{index} find tx_diff at={time:.12g}"
            for index, time in enumerate(sample_times)
        )
        prints = "\n".join(
            "print " + " ".join(measure_names[index:index + 8])
            for index in range(0, len(measure_names), 8)
        )
        stop_time = clock_delay + len(EVEN_BITS) * period
        case_id = (
            f"{phase}_{mos}_{resistor}_{float(supply):.2f}_{int(temperature):+d}_"
            f"b{bias:.1f}_o{offset_ps}p"
        ).replace("+", "p").replace("-", "m").replace(".", "p")
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(instantiate(template, {
            "MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
            "TEMP_C": str(temperature), "VDD_V": f"{float(supply):.2f}",
            "VBIAS_V": f"{bias:.2f}", "CLOCK_DELAY": f"{clock_delay:.12g}",
            "DUT_PATH": str(args.pex) if args.pex else "/src/serializer/serializer_tx.spice",
            "DUT_CELL": "serializer_tx_pex" if args.pex else "serializer_tx",
            "UI": f"{ui:.12g}", "PERIOD": f"{period:.12g}",
            "EVEN_P_PWL": pwl(EVEN_BITS, even_updates, float(supply)),
            "EVEN_N_PWL": pwl(tuple(1-bit for bit in EVEN_BITS), even_updates, float(supply)),
            "ODD_P_PWL": pwl(ODD_BITS, odd_updates, float(supply)),
            "ODD_N_PWL": pwl(tuple(1-bit for bit in ODD_BITS), odd_updates, float(supply)),
            "STOP_TIME": f"{stop_time:.12g}",
            "MEASURE_START": f"{clock_delay:.12g}",
            "MEASURE_LINES": measures, "PRINT_LINES": prints,
        }))
        with log.open("w") as output:
            run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                 stderr=subprocess.STDOUT, timeout=120, check=False)
        observed = {name: float(value) for name, value in pattern.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(measure_names)
        signed = [(1 if bit else -1) * observed.get(f"tx_{index}", 0.0)
                  for index, bit in enumerate(expected)]
        minimum = min(signed)
        passed = complete and minimum >= 0.50 and 0.001 <= observed["supply_current"] <= 0.020
        return {
            "id": case_id, "environment": list(environment), "bias_v": bias,
            "hold_margin_s": offset, "setup_margin_s": ui-offset,
            "minimum_signed_sample_v": minimum,
            "supply_current_a": observed.get("supply_current"),
            "result": "pass" if passed else "fail",
        }

    center_offset = int(round(ui * 0.5e12))
    screen_specs = [(env, bias, center_offset, "screen")
                    for env in ENVIRONMENTS for bias in BIAS_CANDIDATES_V]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        screen = list(executor.map(lambda spec: simulate(*spec), screen_specs))
    calibration = []
    for environment in ENVIRONMENTS:
        passing = [case for case in screen
                   if tuple(case["environment"]) == environment and case["result"] == "pass"]
        selected = min(passing, key=lambda case: (
            case["supply_current_a"],
            -(case["minimum_signed_sample_v"] - 0.50),
            abs(case["bias_v"]-1.1),
        )) if passing else None
        calibration.append({
            "environment": list(environment),
            "selected_bias_v": selected["bias_v"] if selected else None,
            "screen_margin_v": selected["minimum_signed_sample_v"]-0.50 if selected else None,
            "result": "pass" if selected else "fail",
        })
    selected_by_environment = {tuple(item["environment"]): item["selected_bias_v"]
                               for item in calibration if item["result"] == "pass"}
    verification_specs = [
        (environment, selected_by_environment[environment], offset, "verify")
        for environment in ENVIRONMENTS if environment in selected_by_environment
        for offset in OFFSETS_PS[args.rate]
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        verification = list(executor.map(lambda spec: simulate(*spec), verification_specs))
    passed = len(selected_by_environment) == 5 and len(verification) == 35 \
        and all(case["result"] == "pass" for case in verification)
    result = {
        "schema_version": 1,
        "claim": ("extracted_integrated_serializer_tx_changing_word_aperture"
                  if args.pex else "schematic_integrated_serializer_tx_changing_word_aperture"),
        "extraction": "full_rc" if args.pex else "schematic",
        "serial_rate_hz": args.rate, "case_count": len(screen)+len(verification),
        "screen_case_count": len(screen), "verification_case_count": len(verification),
        "passing_environment_count": len(selected_by_environment),
        "calibration": calibration, "screen_cases": screen,
        "verification_cases": verification,
        "worst_verified_sample_v": min(
            (case["minimum_signed_sample_v"] for case in verification), default=None),
        "schematic_source_sha256": sha256(args.source / "serializer" / "serializer_tx.spice"),
        "testbench_source_sha256": sha256(template_path),
        "simulation_source_sha256": sha256(Path(__file__)),
        "pex_sha256": sha256(args.pex) if args.pex else None,
        "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"Integrated serializer/TX {args.rate/1e9:.2f} GT/s: "
          f"{len(selected_by_environment)}/5 env; verified={len(verification)}/35; "
          f"worst={result['worst_verified_sample_v']}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
