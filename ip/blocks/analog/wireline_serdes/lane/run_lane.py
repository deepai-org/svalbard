#!/usr/bin/env python3
"""Calibrate the externally clocked TX-to-sampler lane composition."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path


BITS = (1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 0, 1,
        0, 0, 1, 1, 0, 1, 1, 0)
SAMPLE_INDICES = tuple(range(4, 20))
PHASES_DEG = tuple(index * 22.5 for index in range(16))
SCALAR = re.compile(
    r"^(tx_\d+|pin_\d+|rx_\d+|sample_\d+|rx_cm_avg|amp_cm_avg|supply_current)"
    r"\s*=\s*([-+0-9.eE]+)", re.MULTILINE,
)


def instantiate(template: str, values: dict[str, str]) -> str:
    for name, value in values.items():
        template = template.replace(f"@{name}@", value)
    remaining = sorted(set(re.findall(r"@[A-Z0-9_]+@", template)))
    if remaining:
        raise ValueError(f"unfilled template tokens: {remaining}")
    return template


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pwl(bits: tuple[int, ...], updates: tuple[float, ...], supply: float) -> str:
    points = [(0.0, bits[0] * supply), (0.5e-9, bits[0] * supply)]
    previous = bits[0]
    for update, bit in zip(updates, bits[1:]):
        if bit != previous:
            points.extend(((update - 10e-12, previous * supply),
                           (update + 10e-12, bit * supply)))
        previous = bit
    points.append((updates[-1] + 2e-9, previous * supply))
    return "PWL(" + " ".join(f"{time:.12g} {voltage:.6f}" for time, voltage in points) + ")"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--tx-pex", type=Path)
    parser.add_argument("--term-pex", type=Path)
    parser.add_argument("--rx-pex", type=Path)
    parser.add_argument("--sampler-pex", type=Path)
    parser.add_argument("--tx-bias", type=float, default=1.1)
    parser.add_argument("--rx-bias", type=float, default=1.1)
    parser.add_argument("--sampler-bias", type=float, default=1.1)
    parser.add_argument("--term-code", type=int, default=3)
    parser.add_argument("--mos-corner", default="typical")
    parser.add_argument("--res-corner", default="res_typical")
    parser.add_argument("--vdd", type=float, default=3.3)
    parser.add_argument("--temperature", type=int, default=27)
    parser.add_argument("--rx-vcm-fraction", type=float, default=0.5)
    parser.add_argument("--phase", type=float, action="append")
    parser.add_argument("--allow-fail", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    if not 1 <= args.term_code <= 6:
        parser.error("--term-code must retain one code of rail margin")
    for value in (args.tx_bias, args.rx_bias, args.sampler_bias):
        if not 0.8 <= value <= 1.6:
            parser.error("biases must be between 0.8 and 1.6 V")
    if args.mos_corner not in ("typical", "ff", "ss"):
        parser.error("unsupported MOS corner")
    if args.res_corner not in ("res_typical", "res_ff", "res_ss"):
        parser.error("unsupported resistor corner")
    if not 2.97 <= args.vdd <= 3.63 or not 0.45 <= args.rx_vcm_fraction <= 0.55:
        parser.error("environment is outside the declared lane screen")
    pex_paths = (args.tx_pex, args.term_pex, args.rx_pex, args.sampler_pex)
    if any(path is not None for path in pex_paths) and not all(path is not None for path in pex_paths):
        parser.error("provide all four PEX paths or none")
    extraction = "full_rc_leaves" if all(pex_paths) else "schematic_leaves"
    args.work.mkdir(parents=True, exist_ok=True)

    rate = 1.25e9
    ui = 1.0 / rate
    period = 2.0 * ui
    clock_delay = 4.0e-9
    even_bits, odd_bits = BITS[0::2], BITS[1::2]
    update_offset = ui / 2
    even_updates = tuple(clock_delay + (index - 1) * period + ui + update_offset
                         for index in range(1, len(even_bits)))
    odd_updates = tuple(clock_delay + index * period + update_offset
                        for index in range(1, len(odd_bits)))
    template_path = args.source / "lane" / "lane_tb.spice.in"
    template = template_path.read_text()
    phases = tuple(args.phase) if args.phase else PHASES_DEG
    expected_scalars = len(SAMPLE_INDICES) * 4 + 3

    sources = {
        "TX_INCLUDE": f".include {args.tx_pex}" if args.tx_pex else ".include /src/serializer/serializer_tx.spice",
        "TERM_INCLUDE": f".include {args.term_pex}" if args.term_pex else ".include /src/termination/termination.spice",
        "RX_INCLUDE": f".include {args.rx_pex}" if args.rx_pex else ".include /src/serdes_rx/serdes_rx.spice",
        "SAMPLER_INCLUDE": f".include {args.sampler_pex}" if args.sampler_pex else ".include /src/cdr/cdr_sampler.spice",
        "TX_CELL": "serializer_tx_pex" if args.tx_pex else "serializer_tx",
        "TERM_CELL": "serdes_termination_pex" if args.term_pex else "serdes_termination",
        "RX_CELL": "serdes_rx_pex" if args.rx_pex else "serdes_rx",
        "SAMPLER_CELL": "cdr_sampler_pex" if args.sampler_pex else "cdr_sampler",
    }
    term_sources = "\n".join(
        f"VTERM{index} TERM_EN{index}_N_SRC 0 "
        + ("0" if index < args.term_code else f"{args.vdd:.2f}")
        + f"\nRTERM{index} TERM_EN{index}_N_SRC TERM_EN{index}_N 1"
        for index in range(7)
    )

    def simulate(phase: float) -> dict[str, object]:
        measures = []
        for index in SAMPLE_INDICES:
            eye_time = clock_delay + (index + 0.5) * ui
            held_time = clock_delay + (index + 1) * ui + 50e-12
            output = "even_diff" if index % 2 == 0 else "odd_diff"
            measures.extend((
                f"meas tran tx_{index} find tx_diff at={eye_time:.12g}",
                f"meas tran pin_{index} find pin_diff at={eye_time:.12g}",
                f"meas tran rx_{index} find rx_diff at={eye_time:.12g}",
                f"meas tran sample_{index} find {output} at={held_time:.12g}",
            ))
        case_id = f"phase_{phase:05.1f}".replace(".", "p")
        deck = args.work / f"{case_id}.spice"
        log = args.work / f"{case_id}.log"
        values = {
            **sources,
            "MOS_CORNER": args.mos_corner, "RES_CORNER": args.res_corner,
            "TEMP_C": str(args.temperature), "VDD_V": f"{args.vdd:.2f}",
            "RX_VCM_V": f"{args.vdd * args.rx_vcm_fraction:.6f}",
            "TX_BIAS_V": f"{args.tx_bias:.2f}", "RX_BIAS_V": f"{args.rx_bias:.2f}",
            "SAMPLER_BIAS_V": f"{args.sampler_bias:.2f}",
            "EVEN_P_PWL": pwl(even_bits, even_updates, args.vdd),
            "EVEN_N_PWL": pwl(tuple(1-bit for bit in even_bits), even_updates, args.vdd),
            "ODD_P_PWL": pwl(odd_bits, odd_updates, args.vdd),
            "ODD_N_PWL": pwl(tuple(1-bit for bit in odd_bits), odd_updates, args.vdd),
            "CLOCK_DELAY": f"{clock_delay:.12g}", "UI": f"{ui:.12g}",
            "PERIOD": f"{period:.12g}", "TERM_CONTROL_SOURCES": term_sources,
            "TX_PAD_CAP": "300f", "RX_PAD_CAP": "500f", "AC_CAP": "100n",
            "AC_INITIAL_V": f"{args.vdd * (0.82 - args.rx_vcm_fraction):.6f}",
            "PACKAGE_R": "2", "PACKAGE_L": "1n", "BIAS_RETURN_R": "2k",
            "SAMPLE_CLOCK_CM": f"{args.vdd * 2 / 3:.6f}",
            "SAMPLE_CLOCK_PEAK": "0.45",
            "CLOCK_HZ": f"{rate / 2:.12g}", "CLOCK_PHASE": f"{phase:.3f}",
            "CLOCK_N_PHASE": f"{phase + 180:.3f}",
            "MEASURE_LINES": "\n".join(measures),
            "MEASURE_START": f"{clock_delay + 4 * ui:.12g}",
            "STOP_TIME": f"{clock_delay + (len(BITS) + 2) * ui:.12g}",
        }
        deck_text = instantiate(template, values)
        deck.write_text(deck_text)
        with log.open("w") as output:
            try:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=240, check=False)
                return_code = run.returncode
            except subprocess.TimeoutExpired:
                return_code = 124
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        signed = {}
        for prefix in ("tx", "pin", "rx", "sample"):
            signed[prefix] = [
                observed.get(f"{prefix}_{index}", 0.0) * (1 if BITS[index] else -1)
                for index in SAMPLE_INDICES
            ]
        complete = return_code == 0 and len(observed) == expected_scalars
        margins = {name: min(values_) for name, values_ in signed.items()}
        current = observed.get("supply_current", 0.0)
        passed = (complete and margins["tx"] >= 0.05 and margins["pin"] >= 0.10
                  and margins["rx"] >= 0.08 and margins["sample"] >= 0.10
                  and args.vdd * args.rx_vcm_fraction - 0.25
                  <= observed.get("rx_cm_avg", 0.0)
                  <= args.vdd * args.rx_vcm_fraction + 0.25
                  and 0.50 <= observed.get("amp_cm_avg", 0.0) <= args.vdd - 0.10
                  and 0.005 <= current <= 0.060)
        return {
            "id": case_id, "phase_deg": phase, "complete": complete,
            "minimum_signed_tx_v": margins["tx"],
            "minimum_signed_pin_v": margins["pin"],
            "minimum_signed_rx_v": margins["rx"],
            "minimum_signed_sample_v": margins["sample"],
            "rx_common_mode_v": observed.get("rx_cm_avg"),
            "amplifier_common_mode_v": observed.get("amp_cm_avg"),
            "supply_current_a": current,
            "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, phases))
    passing = [case for case in cases if case["result"] == "pass"]
    selected = max(passing, key=lambda case: case["minimum_signed_sample_v"]) if passing else None
    result = {
        "schema_version": 1,
        "claim": "externally_clocked_1p25_gbd_tx_to_sampler_composition",
        "extraction": extraction,
        "serial_rate_hz": rate,
        "channel_contract": {
            "tx_pad_capacitance_f": 300e-15, "rx_pad_capacitance_f": 500e-15,
            "ac_coupling_capacitance_f": 100e-9, "package_series_resistance_ohm_per_leg": 2.0,
            "package_series_inductance_h_per_leg": 1e-9, "bias_return_ohm_per_leg": 2000.0,
            "note": "provisional lumped low-loss boundary; no compliance or selected-pad claim",
        },
        "controls": {"tx_bias_v": args.tx_bias, "rx_bias_v": args.rx_bias,
                     "sampler_bias_v": args.sampler_bias, "termination_code": args.term_code},
        "environment": [args.mos_corner, args.res_corner, args.vdd,
                        args.temperature, args.rx_vcm_fraction],
        "case_count": len(cases), "complete_case_count": sum(case["complete"] for case in cases),
        "passing_case_count": len(passing), "selected_case": selected, "cases": cases,
        "source_hashes": {
            "testbench": sha256(template_path), "runner": sha256(Path(__file__)),
            **{name: sha256(path) for name, path in zip(
                ("tx_pex", "termination_pex", "rx_pex", "sampler_pex"), pex_paths) if path},
        },
        "result": "pass" if selected else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"1.25 GBd lane {extraction}: {len(passing)}/{len(cases)} phases pass; "
          f"best={selected}")
    if not selected and not args.allow_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
