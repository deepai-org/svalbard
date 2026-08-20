#!/usr/bin/env python3
"""Prove changing-word serialization over a guarded unselected aperture."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path

ENVIRONMENTS = (
    ("typical", "res_typical", 3.30, 27),
    ("ff", "res_ff", 3.63, -40),
    ("ff", "res_ss", 2.97, 125),
    ("ss", "res_ff", 2.97, 125),
    ("ss", "res_ss", 2.97, 125),
)
EVEN_BITS = (1, 0, 1, 0, 1, 0, 1, 0)
ODD_BITS = (0, 1, 0, 1, 0, 1, 0, 1)
OFFSETS_PS = {
    1.25e9: (60, 100, 200, 300, 400, 600, 740),
    2.5e9: (60, 90, 130, 200, 270, 310, 340),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def instantiate(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", template)))
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def pwl(bits: tuple[int, ...], updates: tuple[float, ...], supply: float) -> str:
    points = [(0.0, bits[0] * supply), (0.5e-9, bits[0] * supply)]
    previous = bits[0]
    for update, bit in zip(updates, bits[1:]):
        points.extend(((update - 10e-12, previous * supply),
                       (update + 10e-12, bit * supply)))
        previous = bit
    return "PWL(" + " ".join(f"{time:.12g} {value:.6f}" for time, value in points) + ")"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pex", type=Path)
    parser.add_argument("--schematic", action="store_true")
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--physical", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rate", type=float, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--bias", type=float)
    parser.add_argument("--load", type=float, default=7.5)
    parser.add_argument("--restorer-pex", type=Path)
    parser.add_argument("--restorer-bias", type=float, default=1.2)
    parser.add_argument("--restorer-cell", default="cml_clock_restorer_cascade_pex")
    parser.add_argument("--restorer-invert", action="store_true")
    parser.add_argument("--tx-bias", type=float, default=1.1)
    parser.add_argument("--offsets-ps")
    parser.add_argument("--control-map", type=Path)
    parser.add_argument("--allow-fail", action="store_true")
    args = parser.parse_args()
    if not args.schematic and args.pex is None:
        parser.error("--pex is required unless --schematic is used")
    if args.rate not in OFFSETS_PS:
        parser.error("--rate must be 1.25e9 or 2.5e9")
    if args.load not in (5.0, 7.5, 10.0, 12.5):
        parser.error("--load must be a characterized load length")
    if not 0.7 <= args.restorer_bias <= 1.7:
        parser.error("--restorer-bias must be between 0.7 and 1.7 V")
    if not 0.7 <= args.tx_bias <= 1.7:
        parser.error("--tx-bias must be between 0.7 and 1.7 V")
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    args.work.mkdir(parents=True, exist_ok=True)

    calibration = json.loads(args.calibration.read_text())
    physical = json.loads(args.physical.read_text())
    pex_hash = sha256(args.pex) if args.pex else None
    common_identity = (
        calibration.get("result") == "pass"
        and calibration.get("extraction") == "full_rc"
        and calibration.get("serial_rate_hz") == args.rate
        and calibration.get("passing_environment_count") == 5
        and physical.get("result") == "pass"
    )
    physical_identity = (
        calibration.get("pex_sha256") == pex_hash
        and physical.get("pex_sha256") == pex_hash
    )
    if not common_identity or (not args.schematic and not physical_identity):
        raise SystemExit("calibration/physical/PEX identity mismatch")
    bias_by_environment = {
        tuple(item["environment"]): float(item["selected_bias_v"])
        for item in calibration["calibration"]
    }
    if set(bias_by_environment) != set(ENVIRONMENTS):
        raise SystemExit("calibration environments do not match timing matrix")
    if args.bias is not None:
        if not 0.7 <= args.bias <= 1.7:
            parser.error("--bias must be between 0.7 and 1.7 V")
        bias_by_environment = {environment: args.bias for environment in ENVIRONMENTS}
    restorer_bias_by_environment = {
        environment: args.restorer_bias for environment in ENVIRONMENTS
    }
    tx_bias_by_environment = {
        environment: args.tx_bias for environment in ENVIRONMENTS
    }
    if args.control_map:
        controls = json.loads(args.control_map.read_text())
        entries = {tuple(item["environment"]): item for item in controls["controls"]}
        if set(entries) != set(ENVIRONMENTS):
            raise SystemExit("control-map environments do not match timing matrix")
        bias_by_environment = {
            environment: float(entries[environment]["serializer_bias_v"])
            for environment in ENVIRONMENTS
        }
        restorer_bias_by_environment = {
            environment: float(entries[environment]["restorer_bias_v"])
            for environment in ENVIRONMENTS
        }
        tx_bias_by_environment = {
            environment: float(entries[environment]["tx_bias_v"])
            for environment in ENVIRONMENTS
        }

    template_path = args.source / "serializer" / "changing_word_tb.spice.in"
    template = template_path.read_text()
    ui = 1.0 / args.rate
    period = 2.0 * ui
    clock_delay = 2.0e-9
    samples = tuple(bit for pair in zip(EVEN_BITS, ODD_BITS) for bit in pair)
    measure_names = tuple(
        name for index in range(len(samples)) for name in (f"ser_{index}", f"tx_{index}")
    ) + ("serializer_current", "tx_current")
    measurement_pattern = re.compile(
        rf"^({'|'.join(measure_names)})\s*=\s*([-+0-9.eE]+)", re.MULTILINE
    )
    offsets_ps = (
        tuple(int(value) for value in args.offsets_ps.split(","))
        if args.offsets_ps else OFFSETS_PS[args.rate]
    )
    if not offsets_ps or min(offsets_ps) <= 0 or max(offsets_ps) >= ui * 1e12:
        parser.error("offsets must lie strictly inside the unselected UI")
    specifications = [
        (environment, offset_ps)
        for environment in ENVIRONMENTS
        for offset_ps in offsets_ps
    ]

    def simulate(specification: tuple[tuple[object, ...], int]) -> dict[str, object]:
        environment, offset_ps = specification
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
            clock_delay + index * period + phase * ui
            for index in range(len(EVEN_BITS)) for phase in (0.5, 1.5)
        )
        measure_lines = "\n".join(
            f"meas tran ser_{index} find ser_diff at={time:.12g}\n"
            f"meas tran tx_{index} find tx_diff at={time:.12g}"
            for index, time in enumerate(sample_times)
        )
        print_lines = "\n".join(
            "print " + " ".join(measure_names[index:index + 6])
            for index in range(0, len(measure_names), 6)
        )
        stop_time = clock_delay + len(EVEN_BITS) * period
        case_id = (
            f"{mos}_{resistor}_{float(supply):.2f}_{int(temperature):+d}_o{offset_ps}p"
        ).replace("+", "p").replace("-", "m").replace(".", "p")
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        even_p = pwl(EVEN_BITS, even_updates, float(supply))
        odd_p = pwl(ODD_BITS, odd_updates, float(supply))
        deck.write_text(instantiate(template, {
            "MOS_CORNER": str(mos), "RES_CORNER": str(resistor),
            "TEMP_C": str(temperature), "VDD_V": f"{float(supply):.2f}",
            "SER_BIAS_V": f"{bias_by_environment[environment]:.2f}",
            "TX_BIAS_V": f"{tx_bias_by_environment[environment]:.2f}",
            "DUT_PATH": ("/src/serializer/serializer.spice"
                         if args.schematic else str(args.pex)),
            "DUT_CELL": ("cml_serializer_2to1" if args.schematic
                         else "cml_serializer_2to1_pex"),
            "DUT_PARAMS": f"params: LOAD_L={args.load:.1f}u" if args.schematic else "",
            "RESTORER_INCLUDE": (f".include {args.restorer_pex}"
                                 if args.restorer_pex else "* direct serializer-to-TX"),
            "RESTORER_SUPPLIES": (
                f"VREST VDD_RESTORE 0 PWL(0 0 500p {float(supply):.2f})\n"
                f"VBIAS_RESTORE VBIAS_RESTORE 0 PWL(0 0 500p {restorer_bias_by_environment[environment]:.2f})"
                if args.restorer_pex else "* no restorer supplies"),
            "RESTORER_INSTANCE": (
                f"XREST SER_RAW_P SER_RAW_N VBIAS_RESTORE VDD_RESTORE 0 "
                f"{'SER_N SER_P' if args.restorer_invert else 'SER_P SER_N'} "
                f"{args.restorer_cell}"
                if args.restorer_pex else "* no restorer instance"),
            "SER_OUT_P": "SER_RAW_P" if args.restorer_pex else "SER_P",
            "SER_OUT_N": "SER_RAW_N" if args.restorer_pex else "SER_N",
            "TX_IN_P": "SER_P", "TX_IN_N": "SER_N",
            "CLOCK_DELAY": f"{clock_delay:.12g}",
            "UI": f"{ui:.12g}", "PERIOD": f"{period:.12g}",
            "EVEN_P_PWL": even_p,
            "EVEN_N_PWL": pwl(tuple(1 - bit for bit in EVEN_BITS), even_updates, float(supply)),
            "ODD_P_PWL": odd_p,
            "ODD_N_PWL": pwl(tuple(1 - bit for bit in ODD_BITS), odd_updates, float(supply)),
            "STOP_TIME": f"{stop_time:.12g}",
            "MEASURE_START": f"{clock_delay:.12g}",
            "MEASURE_LINES": measure_lines, "PRINT_LINES": print_lines,
        }))
        with log.open("w") as output:
            run = subprocess.run(
                ["ngspice", "-b", str(deck)], stdout=output,
                stderr=subprocess.STDOUT, timeout=120, check=False,
            )
        observed = {name: float(value) for name, value in measurement_pattern.findall(log.read_text())}
        complete = run.returncode == 0 and len(observed) == len(measure_names)
        signed_serializer = [
            (1 if bit else -1) * observed.get(f"ser_{index}", 0.0)
            for index, bit in enumerate(samples)
        ]
        signed_tx = [
            (1 if bit else -1) * observed.get(f"tx_{index}", 0.0)
            for index, bit in enumerate(samples)
        ]
        minimum_serializer = min(signed_serializer)
        minimum_tx = min(signed_tx)
        passed = (
            complete and minimum_serializer >= 0.40 and minimum_tx >= 0.30
            and 0.0001 <= observed["serializer_current"] <= 0.020
            and 0.0001 <= observed["tx_current"] <= 0.020
        )
        return {
            "id": case_id, "environment": list(environment),
            "update_offset_after_deselect_s": offset,
            "hold_margin_s": offset, "setup_margin_s": ui - offset,
            "selected_bias_v": bias_by_environment[environment],
            "restorer_bias_v": restorer_bias_by_environment[environment]
            if args.restorer_pex else None,
            "tx_bias_v": tx_bias_by_environment[environment],
            "complete": complete,
            "minimum_signed_serializer_sample_v": minimum_serializer,
            "minimum_signed_tx_sample_v": minimum_tx,
            "serializer_current_a": observed.get("serializer_current"),
            "tx_current_a": observed.get("tx_current"),
            "samples": [
                {"index": index, "expected_bit": bit,
                 "serializer_v": observed.get(f"ser_{index}"),
                 "tx_v": observed.get(f"tx_{index}")}
                for index, bit in enumerate(samples)
            ],
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, specifications))
    passed = all(case["result"] == "pass" for case in cases)
    result = {
        "schema_version": 1,
        "claim": ("schematic_half_rate_serializer_changing_word_aperture"
                  if args.schematic
                  else "extracted_half_rate_serializer_changing_word_aperture"),
        "extraction": "schematic" if args.schematic else "full_rc",
        "serial_rate_hz": args.rate, "half_rate_clock_hz": args.rate / 2,
        "load_length_um": args.load,
        "restorer": args.restorer_pex is not None,
        "restorer_bias_v": None if args.control_map else (
            args.restorer_bias if args.restorer_pex else None),
        "restorer_cell": args.restorer_cell if args.restorer_pex else None,
        "restorer_output_swapped": args.restorer_invert if args.restorer_pex else None,
        "tx_bias_v": None if args.control_map else args.tx_bias,
        "control_map_sha256": sha256(args.control_map) if args.control_map else None,
        "parallel_word_count_per_case": len(EVEN_BITS),
        "serial_sample_count_per_case": len(samples),
        "case_count": len(cases),
        "passing_case_count": sum(case["result"] == "pass" for case in cases),
        "minimum_tested_hold_s": min(case["hold_margin_s"] for case in cases),
        "minimum_tested_setup_s": min(case["setup_margin_s"] for case in cases),
        "worst_signed_serializer_sample_v": min(case["minimum_signed_serializer_sample_v"] for case in cases),
        "worst_signed_tx_sample_v": min(case["minimum_signed_tx_sample_v"] for case in cases),
        "pex_sha256": pex_hash,
        "restorer_pex_sha256": sha256(args.restorer_pex) if args.restorer_pex else None,
        "serializer_source_sha256": sha256(args.source / "serializer" / "serializer.spice"),
        "calibration_sha256": sha256(args.calibration),
        "physical_sha256": sha256(args.physical),
        "testbench_source_sha256": sha256(template_path),
        "simulation_source_sha256": sha256(Path(__file__)),
        "cases": cases, "result": "pass" if passed else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        f"Changing-word {args.rate / 1e9:.2f} GT/s: "
        f"{result['passing_case_count']}/{result['case_count']}; "
        f"worst serializer/TX={result['worst_signed_serializer_sample_v']:.3f}/"
        f"{result['worst_signed_tx_sample_v']:.3f} V"
    )
    if not passed and not args.allow_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
