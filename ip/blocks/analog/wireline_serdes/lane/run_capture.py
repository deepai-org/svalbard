#!/usr/bin/env python3
"""Compose the extracted lane through dual CML/CMOS conversion and capture."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path

import run_lane as spine


PAIR_INDICES = tuple(range(2, 10))
DEFAULT_OFFSETS_PS = (0, 100, 200, 300)
SCALAR = re.compile(
    r"^(fe_even_\d+|fe_odd_\d+|q_even_\d+|q_odd_\d+|rx_cm_avg|amp_cm_avg|"
    r"supply_current)\s*=\s*([-+0-9.eE]+)", re.MULTILINE,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tx-pex", required=True, type=Path)
    parser.add_argument("--term-pex", required=True, type=Path)
    parser.add_argument("--rx-pex", required=True, type=Path)
    parser.add_argument("--sampler-pex", required=True, type=Path)
    parser.add_argument("--frontend-pex", required=True, type=Path)
    parser.add_argument("--deserializer-pex", required=True, type=Path)
    parser.add_argument("--deserializer-physical", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--offset-ps", type=int, action="append")
    parser.add_argument("--sampler-phase", type=float, default=135.0)
    parser.add_argument("--tx-bias", type=float, default=1.1)
    parser.add_argument("--rx-bias", type=float, default=1.1)
    parser.add_argument("--sampler-bias", type=float, default=1.1)
    parser.add_argument("--term-code", type=int, default=3)
    parser.add_argument("--mos-corner", default="typical")
    parser.add_argument("--res-corner", default="res_typical")
    parser.add_argument("--vdd", type=float, default=3.3)
    parser.add_argument("--temperature", type=int, default=27)
    parser.add_argument("--allow-fail", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4 or not 1 <= args.term_code <= 6:
        parser.error("jobs or termination code outside declared range")
    offsets = tuple(args.offset_ps) if args.offset_ps else DEFAULT_OFFSETS_PS
    if any(offset < 0 or offset > 300 for offset in offsets):
        parser.error("conversion offset must be 0--300 ps")
    args.work.mkdir(parents=True, exist_ok=True)

    ui = 1 / 1.25e9
    period = 2 * ui
    clock_delay = 4e-9
    even_bits, odd_bits = spine.BITS[0::2], spine.BITS[1::2]
    even_updates = tuple(clock_delay + (index - 1) * period + 1.5 * ui
                         for index in range(1, len(even_bits)))
    odd_updates = tuple(clock_delay + index * period + 0.5 * ui
                        for index in range(1, len(odd_bits)))
    template_path = args.source / "lane" / "lane_tb.spice.in"
    template = template_path.read_text()
    template = template.replace(
        "@SAMPLER_INCLUDE@",
        "@SAMPLER_INCLUDE@\n.include @FRONTEND_PEX@\n.include @DESERIALIZER_PEX@",
    )
    downstream = """
VESENSE E_SENSE_SRC 0 PULSE(0 @VDD_V@ @E_SENSE_DELAY@ 20p 20p 575p @PERIOD@)
VEREGEN E_REGEN_SRC 0 PULSE(0 @VDD_V@ @E_REGEN_DELAY@ 20p 20p 565p @PERIOD@)
VEREGENB E_REGENB_SRC 0 PULSE(@VDD_V@ 0 @E_REGEN_DELAY@ 20p 20p 565p @PERIOD@)
VECLK E_CAPTURE_SRC 0 PULSE(0 @VDD_V@ @E_CAPTURE_DELAY@ 20p 20p 380p @PERIOD@)
VECLKB E_CAPTUREB_SRC 0 PULSE(@VDD_V@ 0 @E_CAPTURE_DELAY@ 20p 20p 380p @PERIOD@)
VOSENSE O_SENSE_SRC 0 PULSE(0 @VDD_V@ @O_SENSE_DELAY@ 20p 20p 575p @PERIOD@)
VOREGEN O_REGEN_SRC 0 PULSE(0 @VDD_V@ @O_REGEN_DELAY@ 20p 20p 565p @PERIOD@)
VOREGENB O_REGENB_SRC 0 PULSE(@VDD_V@ 0 @O_REGEN_DELAY@ 20p 20p 565p @PERIOD@)
VOCLK O_CAPTURE_SRC 0 PULSE(0 @VDD_V@ @O_CAPTURE_DELAY@ 20p 20p 380p @PERIOD@)
VOCLKB O_CAPTUREB_SRC 0 PULSE(@VDD_V@ 0 @O_CAPTURE_DELAY@ 20p 20p 380p @PERIOD@)
VBOOST BOOST_SRC 0 0
R_ESENSE E_SENSE_SRC E_SENSE_CLK 1
R_EREGEN E_REGEN_SRC E_REGEN_CLK 1
R_EREGENB E_REGENB_SRC E_REGEN_CLKB 1
R_ECAPTURE E_CAPTURE_SRC E_CAPTURE_CLK 1
R_ECAPTUREB E_CAPTUREB_SRC E_CAPTURE_CLKB 1
R_OSENSE O_SENSE_SRC O_SENSE_CLK 1
R_OREGEN O_REGEN_SRC O_REGEN_CLK 1
R_OREGENB O_REGENB_SRC O_REGEN_CLKB 1
R_OCAPTURE O_CAPTURE_SRC O_CAPTURE_CLK 1
R_OCAPTUREB O_CAPTUREB_SRC O_CAPTURE_CLKB 1
R_BOOST BOOST_SRC SENSE_BOOST 1

XFE_E SAMP_E_P SAMP_E_N E_SENSE_CLK E_REGEN_CLK E_REGEN_CLKB E_CAPTURE_CLK E_CAPTURE_CLKB
+ VDD 0 FE_E_P FE_E_N SENSE_BOOST cml_to_cmos_pex
XFE_O SAMP_O_P SAMP_O_N O_SENSE_CLK O_REGEN_CLK O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB
+ VDD 0 FE_O_P FE_O_N SENSE_BOOST cml_to_cmos_pex
CFE_E_P FE_E_P 0 25f
CFE_E_N FE_E_N 0 25f
CFE_O_P FE_O_P 0 25f
CFE_O_N FE_O_N 0 25f
XCAP FE_E_P FE_E_N FE_O_P FE_O_N
+ E_CAPTURE_CLK E_CAPTURE_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB VDD 0
+ EVEN_Q EVEN_QB ODD_Q ODD_QB deserializer_split_capture_pex
CEQ EVEN_Q 0 50f
CEQB EVEN_QB 0 50f
COQ ODD_Q 0 50f
COQB ODD_QB 0 50f
"""
    template = template.replace("\n.control\n", downstream + "\n.control\n")
    template = template.replace(
        "let odd_diff = v(SAMP_O_P)-v(SAMP_O_N)",
        "let odd_diff = v(SAMP_O_P)-v(SAMP_O_N)\n"
        "let fe_even_diff = v(FE_E_P)-v(FE_E_N)\n"
        "let fe_odd_diff = v(FE_O_P)-v(FE_O_N)\n"
        "let q_even_diff = v(EVEN_Q)-v(EVEN_QB)\n"
        "let q_odd_diff = v(ODD_Q)-v(ODD_QB)",
    )
    expected_scalars = len(PAIR_INDICES) * 4 + 3
    pex_paths = {
        "tx_pex": args.tx_pex, "termination_pex": args.term_pex,
        "rx_pex": args.rx_pex, "sampler_pex": args.sampler_pex,
        "frontend_pex": args.frontend_pex, "deserializer_pex": args.deserializer_pex,
    }
    deserializer_physical = json.loads(args.deserializer_physical.read_text())
    deserializer_pex_hash = spine.sha256(args.deserializer_pex)
    if (deserializer_physical.get("result") != "pass"
            or deserializer_physical.get("pex_sha256") != deserializer_pex_hash):
        raise SystemExit("split-capture physical evidence does not bind exact simulation PEX")

    def simulate(offset_ps: int) -> dict[str, object]:
        even_base = clock_delay + ui + 50e-12 + offset_ps * 1e-12
        odd_base = even_base + ui
        capture_close = odd_base + 1.0e-9
        measures = []
        for pair in PAIR_INDICES:
            even_event = even_base + pair * period
            odd_event = odd_base + pair * period
            output_time = odd_event + 1.28e-9
            measures.extend((
                f"meas tran fe_even_{pair} find fe_even_diff at={even_event + 750e-12:.12g}",
                f"meas tran fe_odd_{pair} find fe_odd_diff at={odd_event + 750e-12:.12g}",
                f"meas tran q_even_{pair} find q_even_diff at={output_time:.12g}",
                f"meas tran q_odd_{pair} find q_odd_diff at={output_time:.12g}",
            ))
        term_sources = "\n".join(
            f"VTERM{index} TERM_EN{index}_N_SRC 0 "
            + ("0" if index < args.term_code else f"{args.vdd:.2f}")
            + f"\nRTERM{index} TERM_EN{index}_N_SRC TERM_EN{index}_N 1"
            for index in range(7)
        )
        values = {
            "TX_INCLUDE": f".include {args.tx_pex}",
            "TERM_INCLUDE": f".include {args.term_pex}",
            "RX_INCLUDE": f".include {args.rx_pex}",
            "SAMPLER_INCLUDE": f".include {args.sampler_pex}",
            "FRONTEND_PEX": str(args.frontend_pex),
            "DESERIALIZER_PEX": str(args.deserializer_pex),
            "TX_CELL": "serializer_tx_pex", "TERM_CELL": "serdes_termination_pex",
            "RX_CELL": "serdes_rx_pex", "SAMPLER_CELL": "cdr_sampler_pex",
            "MOS_CORNER": args.mos_corner, "RES_CORNER": args.res_corner,
            "TEMP_C": str(args.temperature), "VDD_V": f"{args.vdd:.2f}",
            "RX_VCM_V": f"{args.vdd * 0.5:.6f}",
            "TX_BIAS_V": f"{args.tx_bias:.2f}", "RX_BIAS_V": f"{args.rx_bias:.2f}",
            "SAMPLER_BIAS_V": f"{args.sampler_bias:.2f}",
            "EVEN_P_PWL": spine.pwl(even_bits, even_updates, args.vdd),
            "EVEN_N_PWL": spine.pwl(tuple(1-bit for bit in even_bits), even_updates, args.vdd),
            "ODD_P_PWL": spine.pwl(odd_bits, odd_updates, args.vdd),
            "ODD_N_PWL": spine.pwl(tuple(1-bit for bit in odd_bits), odd_updates, args.vdd),
            "CLOCK_DELAY": f"{clock_delay:.12g}", "UI": f"{ui:.12g}",
            "PERIOD": f"{period:.12g}", "TERM_CONTROL_SOURCES": term_sources,
            "TX_PAD_CAP": "300f", "RX_PAD_CAP": "500f", "AC_CAP": "100n",
            "AC_INITIAL_V": f"{args.vdd * 0.32:.6f}",
            "PACKAGE_R": "2", "PACKAGE_L": "1n", "BIAS_RETURN_R": "2k",
            "SAMPLE_CLOCK_CM": f"{args.vdd * 2 / 3:.6f}", "SAMPLE_CLOCK_PEAK": "0.45",
            "CLOCK_HZ": "625e6", "CLOCK_PHASE": f"{args.sampler_phase:.3f}",
            "CLOCK_N_PHASE": f"{args.sampler_phase + 180:.3f}",
            "E_SENSE_DELAY": f"{even_base:.12g}",
            "E_REGEN_DELAY": f"{even_base + 10e-12:.12g}",
            "E_CAPTURE_DELAY": f"{even_base + 550e-12:.12g}",
            "O_SENSE_DELAY": f"{odd_base:.12g}",
            "O_REGEN_DELAY": f"{odd_base + 10e-12:.12g}",
            "O_CAPTURE_DELAY": f"{odd_base + 550e-12:.12g}",
            "MEASURE_LINES": "\n".join(measures),
            "MEASURE_START": f"{odd_base + 2 * period:.12g}",
            "STOP_TIME": f"{odd_base + (max(PAIR_INDICES) + 2) * period:.12g}",
        }
        case_id = f"convert_{offset_ps:03d}p"
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(spine.instantiate(template, values))
        with log.open("w") as output:
            try:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT, timeout=600, check=False)
                return_code = run.returncode
            except subprocess.TimeoutExpired:
                return_code = 124
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        margins = {name: [] for name in ("fe_even", "fe_odd", "q_even", "q_odd")}
        for pair in PAIR_INDICES:
            signs = {"even": 1 if even_bits[pair] else -1,
                     "odd": 1 if odd_bits[pair] else -1}
            for stage in ("fe", "q"):
                for lane_name in ("even", "odd"):
                    key = f"{stage}_{lane_name}"
                    margins[key].append(observed.get(f"{key}_{pair}", 0.0) * signs[lane_name])
        minima = {name: min(values_) for name, values_ in margins.items()}
        complete = return_code == 0 and len(observed) == expected_scalars
        current = observed.get("supply_current", 0.0)
        passed = (complete and min(minima["fe_even"], minima["fe_odd"]) >= 0.30
                  and min(minima["q_even"], minima["q_odd"]) >= 0.50
                  and 0.010 <= current <= 0.060)
        return {
            "id": case_id, "conversion_offset_s": offset_ps * 1e-12,
            "capture_close_s": capture_close, "complete": complete,
            "minimum_frontend_even_v": minima["fe_even"],
            "minimum_frontend_odd_v": minima["fe_odd"],
            "minimum_capture_even_v": minima["q_even"],
            "minimum_capture_odd_v": minima["q_odd"],
            "supply_current_a": current, "result": "pass" if passed else "fail",
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, offsets))
    passing = [case for case in cases if case["result"] == "pass"]
    selected = max(passing, key=lambda case: min(case["minimum_capture_even_v"],
                                                  case["minimum_capture_odd_v"])) if passing else None
    result = {
        "schema_version": 1,
        "claim": "extracted_1p25_gbd_lane_dual_cmos_capture",
        "environment": [args.mos_corner, args.res_corner, args.vdd, args.temperature, 0.5],
        "controls": {"sampler_phase_deg": args.sampler_phase, "tx_bias_v": args.tx_bias,
                     "rx_bias_v": args.rx_bias, "sampler_bias_v": args.sampler_bias,
                     "termination_code": args.term_code},
        "case_count": len(cases), "complete_case_count": sum(case["complete"] for case in cases),
        "passing_case_count": len(passing), "selected_case": selected, "cases": cases,
        "pex_sha256": {name: spine.sha256(path) for name, path in pex_paths.items()},
        "physical_sha256": {
            "deserializer_split": spine.sha256(args.deserializer_physical),
        },
        "source_sha256": {"base_testbench": spine.sha256(template_path),
                          "runner": spine.sha256(Path(__file__))},
        "result": "pass" if selected else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"lane dual capture: {len(passing)}/{len(cases)} offsets pass; best={selected}")
    if not selected and not args.allow_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
