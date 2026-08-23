#!/usr/bin/env python3
"""Compose the extracted lane through dual CML/CMOS conversion and capture."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import re
import subprocess
from pathlib import Path

import run_lane as spine


DEFAULT_OFFSETS_PS = (0, 100, 200, 300)
SCALAR = re.compile(
    r"^(tx_even_\d+|tx_odd_\d+|pin_even_\d+|pin_odd_\d+|"
    r"rx_even_\d+|rx_odd_\d+|rest_even_\d+|rest_odd_\d+|"
    r"fe_even_\d+|fe_odd_\d+|q_even_\d+|q_odd_\d+|"
    r"rx_cm_avg|amp_cm_avg|rest_cm_avg|"
    r"supply_current)\s*=\s*([-+0-9.eE]+)", re.MULTILINE,
)


def prbs7(count: int) -> tuple[int, ...]:
    """Return a deterministic maximal-length x^7+x^6+1 sequence."""
    state = 0x5D
    bits = []
    for _ in range(count):
        bits.append((state >> 6) & 1)
        feedback = ((state >> 6) ^ (state >> 5)) & 1
        state = ((state << 1) & 0x7F) | feedback
    return tuple(bits)


def clock_pwl(supply: float, delay: float, period: float, duty: float,
              jitter_s: float, stop: float, inverted: bool) -> str:
    """Create complementary clocks with bounded deterministic edge jitter."""
    initial = supply if inverted else 0.0
    points = [(0.0, initial), (max(0.0, delay - 30e-12), initial)]
    edge_index = 0
    cycle = 0
    while delay + cycle * period < stop + period:
        for nominal, high_after in (
                (delay + cycle * period, True),
                (delay + cycle * period + duty * period, False)):
            displacement = jitter_s * math.sin(2 * math.pi * edge_index / 7 + 0.37)
            edge = nominal + displacement
            before = supply if (high_after == inverted) else 0.0
            after = supply - before
            points.extend(((edge - 10e-12, before), (edge + 10e-12, after)))
            edge_index += 1
        cycle += 1
    return "PWL(" + " ".join(
        f"{time:.12g} {voltage:.6f}" for time, voltage in points
    ) + ")"


def supply_pwl(supply: float, stop: float, ripple_v: float,
               ripple_hz: float) -> str:
    """Ramp the rail, then apply a bounded sinusoidal ripple as a PWL source."""
    if ripple_v == 0.0:
        return f"PWL(0 0 500p {supply:.6f})"
    step = min(20e-12, 1 / (ripple_hz * 64))
    points = [(0.0, 0.0), (500e-12, supply)]
    time = 500e-12 + step
    while time <= stop + step:
        voltage = supply + ripple_v * math.sin(2 * math.pi * ripple_hz
                                                * (time - 500e-12))
        points.append((time, voltage))
        time += step
    return "PWL(" + " ".join(
        f"{point_time:.12g} {voltage:.6f}" for point_time, voltage in points
    ) + ")"


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
    parser.add_argument("--restorer-pex", type=Path)
    parser.add_argument("--restorer-physical", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--offset-ps", type=int, action="append")
    parser.add_argument("--sampler-phase", type=float, default=135.0)
    parser.add_argument("--tx-bias", type=float, default=1.1)
    parser.add_argument("--rx-bias", type=float, default=1.1)
    parser.add_argument("--sampler-bias", type=float, default=1.1)
    parser.add_argument("--restorer-bias", type=float, default=1.1)
    parser.add_argument("--term-code", type=int, default=3)
    parser.add_argument("--mos-corner", default="typical")
    parser.add_argument("--res-corner", default="res_typical")
    parser.add_argument("--vdd", type=float, default=3.3)
    parser.add_argument("--temperature", type=int, default=27)
    parser.add_argument("--pattern", choices=("changing24", "prbs7"),
                        default="changing24")
    parser.add_argument("--bit-count", type=int, default=24)
    parser.add_argument("--tx-clock-jitter-ps", type=float, default=0.0)
    parser.add_argument("--tx-clock-duty", type=float, default=0.5)
    parser.add_argument("--channel-series-ohm-per-leg", type=float, default=0.0)
    parser.add_argument("--channel-shunt-cap-f", type=float, default=0.0)
    parser.add_argument("--vdd-ripple-mv", type=float, default=0.0)
    parser.add_argument("--vdd-ripple-hz", type=float, default=100e6)
    parser.add_argument("--rx-bandwidth-mode", choices=("low", "high"),
                        default="high")
    parser.add_argument("--restorer-mode",
                        choices=("none", "single", "cascade", "data"),
                        default="none")
    parser.add_argument("--allow-fail", action="store_true")
    parser.add_argument("--case-id", default="nominal")
    parser.add_argument("--simulation-timeout-s", type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4 or not 1 <= args.term_code <= 6:
        parser.error("jobs or termination code outside declared range")
    offsets = tuple(args.offset_ps) if args.offset_ps else DEFAULT_OFFSETS_PS
    if any(offset < 0 or offset > 300 for offset in offsets):
        parser.error("conversion offset must be 0--300 ps")
    if not 24 <= args.bit_count <= 128 or args.bit_count % 2:
        parser.error("bit count must be an even value from 24 through 128")
    if args.pattern == "changing24" and args.bit_count != len(spine.BITS):
        parser.error("changing24 has exactly 24 bits")
    if not 0.40 <= args.tx_clock_duty <= 0.60:
        parser.error("TX clock duty must be between 40% and 60%")
    if not 0.0 <= args.tx_clock_jitter_ps <= 80.0:
        parser.error("TX clock jitter must be between 0 and 80 ps peak")
    if not 0.0 <= args.channel_series_ohm_per_leg <= 25.0:
        parser.error("channel series loss proxy must be 0--25 ohm per leg")
    if not 0.0 <= args.channel_shunt_cap_f <= 4e-12:
        parser.error("channel differential capacitance must be 0--4 pF")
    if not 0.0 <= args.vdd_ripple_mv <= 100.0:
        parser.error("VDD ripple must be 0--100 mV peak")
    if not 1e6 <= args.vdd_ripple_hz <= 1.25e9:
        parser.error("VDD ripple frequency must be 1 MHz--1.25 GHz")
    if not 300 <= args.simulation_timeout_s <= 900:
        parser.error("simulation timeout must be 300--900 seconds")
    if args.restorer_mode != "none" and not (
            args.restorer_pex and args.restorer_physical):
        parser.error("restorer mode requires its PEX and physical record")
    args.work.mkdir(parents=True, exist_ok=True)

    ui = 1 / 1.25e9
    period = 2 * ui
    clock_delay = 4e-9
    bits = spine.BITS if args.pattern == "changing24" else prbs7(args.bit_count)
    even_bits, odd_bits = bits[0::2], bits[1::2]
    pair_indices = tuple(range(2, len(even_bits) - 2))
    even_updates = tuple(clock_delay + (index - 1) * period + 1.5 * ui
                         for index in range(1, len(even_bits)))
    odd_updates = tuple(clock_delay + index * period + 0.5 * ui
                        for index in range(1, len(odd_bits)))
    template_path = args.source / "lane" / "lane_tb.spice.in"
    template = template_path.read_text()
    template = template.replace(
        "@SAMPLER_INCLUDE@",
        "@SAMPLER_INCLUDE@\n@RESTORER_INCLUDE@\n"
        ".include @FRONTEND_PEX@\n.include @DESERIALIZER_PEX@",
    )
    template = template.replace(
        "VTXCLKP TX_CLK_P_SRC 0 PULSE(0 @VDD_V@ @CLOCK_DELAY@ 20p 20p @UI@ @PERIOD@)\n"
        "VTXCLKN TX_CLK_N_SRC 0 PULSE(@VDD_V@ 0 @CLOCK_DELAY@ 20p 20p @UI@ @PERIOD@)",
        "VTXCLKP TX_CLK_P_SRC 0 @TX_CLOCK_PWL@\n"
        "VTXCLKN TX_CLK_N_SRC 0 @TX_CLOCK_N_PWL@",
    )
    template = template.replace("VDD VDD 0 PWL(0 0 500p @VDD_V@)",
                                "VDD VDD 0 @VDD_PWL@")
    template = template.replace("VBW RX_BW_EN_N_SRC 0 0",
                                "VBW RX_BW_EN_N_SRC 0 @RX_BW_EN_N_V@")
    template = template.replace(
        "VRXBIAS RX_BIAS_SRC 0 PWL(0 0 500p @RX_BIAS_V@)",
        "VRXBIAS RX_BIAS_SRC 0 PWL(0 0 500p @RX_BIAS_V@)\n"
        "@RESTORER_BIAS_SOURCE@",
    )
    template = template.replace(
        "R_RXBIAS RX_BIAS_SRC RX_BIAS 1",
        "R_RXBIAS RX_BIAS_SRC RX_BIAS 1\n@RESTORER_BIAS_RESISTOR@",
    )
    if args.restorer_mode != "none":
        restorer_cell = {
            "single": "cml_clock_restorer_pex",
            "cascade": "cml_clock_restorer_cascade_pex",
            "data": "cml_data_restorer_pex",
        }[args.restorer_mode]
        # One differential stage inverts; the two-stage cascade does not.
        restorer_outputs = ("RXON RXOP" if args.restorer_mode == "cascade"
                            else "RXOP RXON")
        template = template.replace(
            "XRX RXP RXN VTHP VTHN RX_BIAS RX_BW_EN_N VDD 0 RXOP RXON @RX_CELL@\n"
            "CRXOP RXOP 0 25f\nCRXON RXON 0 25f",
            "XRX RXP RXN VTHP VTHN RX_BIAS RX_BW_EN_N VDD 0 RX_RAWP RX_RAWN @RX_CELL@\n"
            "CRXRAWP RX_RAWP 0 25f\nCRXRAWN RX_RAWN 0 25f\n"
            "* Explicit output mapping preserves lane polarity for the selected stage count.\n"
            f"XREST RX_RAWP RX_RAWN REST_BIAS VDD 0 {restorer_outputs} {restorer_cell}\n"
            "CRESTOP RXOP 0 25f\nCRESTON RXON 0 25f",
        )
        template = template.replace(
            "let rx_diff = v(RXOP)-v(RXON)",
            "let rx_diff = v(RX_RAWP)-v(RX_RAWN)\n"
            "let rest_diff = v(RXOP)-v(RXON)\n"
            "let rest_cm = (v(RXOP)+v(RXON))/2",
        )
        template = template.replace(
            "let amp_cm = (v(RXOP)+v(RXON))/2",
            "let amp_cm = (v(RX_RAWP)+v(RX_RAWN))/2",
        )
    template = template.replace(
        "LPKG_P LP_P RXP @PACKAGE_L@\nLPKG_N LP_N RXN @PACKAGE_L@",
        "LPKG_P LP_P CH_IN_P @PACKAGE_L@\n"
        "LPKG_N LP_N CH_IN_N @PACKAGE_L@\n"
        "RCH_P1 CH_IN_P CH_M_P @CHANNEL_HALF_R@\n"
        "RCH_N1 CH_IN_N CH_M_N @CHANNEL_HALF_R@\n"
        "CCH_M CH_M_P CH_M_N @CHANNEL_HALF_C@\n"
        "RCH_P2 CH_M_P RXP @CHANNEL_HALF_R@\n"
        "RCH_N2 CH_M_N RXN @CHANNEL_HALF_R@\n"
        "CCH_O RXP RXN @CHANNEL_HALF_C@",
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
    scored_stages = ("tx", "pin", "rx", "rest", "fe", "q") \
        if args.restorer_mode != "none" else ("tx", "pin", "rx", "fe", "q")
    expected_scalars = len(pair_indices) * len(scored_stages) * 2 + 3 \
        + (1 if args.restorer_mode != "none" else 0)
    pex_paths = {
        "tx_pex": args.tx_pex, "termination_pex": args.term_pex,
        "rx_pex": args.rx_pex, "sampler_pex": args.sampler_pex,
        "frontend_pex": args.frontend_pex, "deserializer_pex": args.deserializer_pex,
    }
    if args.restorer_mode != "none":
        pex_paths["restorer_pex"] = args.restorer_pex
    physical_paths = {"deserializer_split": args.deserializer_physical}
    if args.restorer_mode != "none":
        physical_paths["restorer"] = args.restorer_physical
    deserializer_physical = json.loads(args.deserializer_physical.read_text())
    deserializer_pex_hash = spine.sha256(args.deserializer_pex)
    if (deserializer_physical.get("result") != "pass"
            or deserializer_physical.get("pex_sha256") != deserializer_pex_hash):
        raise SystemExit("split-capture physical evidence does not bind exact simulation PEX")
    if args.restorer_mode != "none":
        restorer_physical = json.loads(args.restorer_physical.read_text())
        if (restorer_physical.get("result") != "pass"
                or restorer_physical.get("pex_sha256") != spine.sha256(args.restorer_pex)):
            raise SystemExit("restorer physical evidence does not bind exact simulation PEX")

    def simulate(offset_ps: int) -> dict[str, object]:
        even_base = clock_delay + ui + 50e-12 + offset_ps * 1e-12
        odd_base = even_base + ui
        capture_close = odd_base + 1.0e-9
        measures = []
        restorer_eye_shift = ((135.0 - args.sampler_phase) / 360.0 * period
                              if args.restorer_mode != "none" else 0.0)
        stop_time = odd_base + (max(pair_indices) + 2) * period
        for pair in pair_indices:
            even_event = even_base + pair * period
            odd_event = odd_base + pair * period
            even_eye = clock_delay + (2 * pair + 0.5) * ui
            odd_eye = clock_delay + (2 * pair + 1.5) * ui
            output_time = odd_event + 1.28e-9
            measures.extend((
                f"meas tran tx_even_{pair} find tx_diff at={even_eye:.12g}",
                f"meas tran pin_even_{pair} find pin_diff at={even_eye:.12g}",
                f"meas tran rx_even_{pair} find rx_diff at={even_eye:.12g}",
                f"meas tran tx_odd_{pair} find tx_diff at={odd_eye:.12g}",
                f"meas tran pin_odd_{pair} find pin_diff at={odd_eye:.12g}",
                f"meas tran rx_odd_{pair} find rx_diff at={odd_eye:.12g}",
                f"meas tran fe_even_{pair} find fe_even_diff at={even_event + 750e-12:.12g}",
                f"meas tran fe_odd_{pair} find fe_odd_diff at={odd_event + 750e-12:.12g}",
                f"meas tran q_even_{pair} find q_even_diff at={output_time:.12g}",
                f"meas tran q_odd_{pair} find q_odd_diff at={output_time:.12g}",
            ))
            if args.restorer_mode != "none":
                measures.extend((
                    f"meas tran rest_even_{pair} find rest_diff "
                    f"at={even_eye + restorer_eye_shift:.12g}",
                    f"meas tran rest_odd_{pair} find rest_diff "
                    f"at={odd_eye + restorer_eye_shift:.12g}",
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
            "RESTORER_INCLUDE": (f".include {args.restorer_pex}"
                                   if args.restorer_mode != "none" else ""),
            "FRONTEND_PEX": str(args.frontend_pex),
            "DESERIALIZER_PEX": str(args.deserializer_pex),
            "TX_CELL": "serializer_tx_pex", "TERM_CELL": "serdes_termination_pex",
            "RX_CELL": "serdes_rx_pex", "SAMPLER_CELL": "cdr_sampler_pex",
            "MOS_CORNER": args.mos_corner, "RES_CORNER": args.res_corner,
            "TEMP_C": str(args.temperature), "VDD_V": f"{args.vdd:.2f}",
            "RX_VCM_V": f"{args.vdd * 0.5:.6f}",
            "TX_BIAS_V": f"{args.tx_bias:.2f}", "RX_BIAS_V": f"{args.rx_bias:.2f}",
            "SAMPLER_BIAS_V": f"{args.sampler_bias:.2f}",
            "RESTORER_BIAS_SOURCE": (
                f"VRESTBIAS REST_BIAS_SRC 0 PWL(0 0 500p {args.restorer_bias:.2f})"
                if args.restorer_mode != "none" else ""),
            "RESTORER_BIAS_RESISTOR": (
                "R_RESTBIAS REST_BIAS_SRC REST_BIAS 1"
                if args.restorer_mode != "none" else ""),
            "EVEN_P_PWL": spine.pwl(even_bits, even_updates, args.vdd),
            "EVEN_N_PWL": spine.pwl(tuple(1-bit for bit in even_bits), even_updates, args.vdd),
            "ODD_P_PWL": spine.pwl(odd_bits, odd_updates, args.vdd),
            "ODD_N_PWL": spine.pwl(tuple(1-bit for bit in odd_bits), odd_updates, args.vdd),
            "CLOCK_DELAY": f"{clock_delay:.12g}", "UI": f"{ui:.12g}",
            "PERIOD": f"{period:.12g}", "TERM_CONTROL_SOURCES": term_sources,
            "TX_CLOCK_PWL": clock_pwl(args.vdd, clock_delay, period,
                                         args.tx_clock_duty,
                                         args.tx_clock_jitter_ps * 1e-12,
                                         stop_time, False),
            "TX_CLOCK_N_PWL": clock_pwl(args.vdd, clock_delay, period,
                                           args.tx_clock_duty,
                                           args.tx_clock_jitter_ps * 1e-12,
                                           stop_time, True),
            "VDD_PWL": supply_pwl(args.vdd, stop_time,
                                    args.vdd_ripple_mv * 1e-3,
                                    args.vdd_ripple_hz),
            "RX_BW_EN_N_V": "0" if args.rx_bandwidth_mode == "high"
            else f"{args.vdd:.2f}",
            "TX_PAD_CAP": "300f", "RX_PAD_CAP": "500f", "AC_CAP": "100n",
            "AC_INITIAL_V": f"{args.vdd * 0.32:.6f}",
            "PACKAGE_R": "2", "PACKAGE_L": "1n", "BIAS_RETURN_R": "2k",
            "CHANNEL_HALF_R": f"{max(args.channel_series_ohm_per_leg / 2, 1e-3):.12g}",
            "CHANNEL_HALF_C": f"{max(args.channel_shunt_cap_f / 2, 1e-18):.12g}",
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
            "STOP_TIME": f"{stop_time:.12g}",
        }
        if args.restorer_mode != "none":
            values["MEASURE_LINES"] += "\nmeas tran rest_cm_avg avg rest_cm " \
                f"from={odd_base + 2 * period:.12g} to={stop_time:.12g}"
        case_id = f"convert_{offset_ps:03d}p"
        deck, log = args.work / f"{case_id}.spice", args.work / f"{case_id}.log"
        deck.write_text(spine.instantiate(template, values))
        with log.open("w") as output:
            try:
                run = subprocess.run(["ngspice", "-b", str(deck)], stdout=output,
                                     stderr=subprocess.STDOUT,
                                     timeout=args.simulation_timeout_s, check=False)
                return_code = run.returncode
            except subprocess.TimeoutExpired:
                return_code = 124
        observed = {name: float(value) for name, value in SCALAR.findall(log.read_text())}
        margins = {f"{stage}_{lane_name}": []
                   for stage in scored_stages
                   for lane_name in ("even", "odd")}
        for pair in pair_indices:
            signs = {"even": 1 if even_bits[pair] else -1,
                     "odd": 1 if odd_bits[pair] else -1}
            for stage in scored_stages:
                for lane_name in ("even", "odd"):
                    key = f"{stage}_{lane_name}"
                    margins[key].append(observed.get(f"{key}_{pair}", 0.0) * signs[lane_name])
        minima = {name: min(values_) for name, values_ in margins.items()}
        complete = return_code == 0 and len(observed) == expected_scalars
        current = observed.get("supply_current", 0.0)
        # Without a restorer, RXOP/RXON is the sampler contract and retains the
        # original 80 mV signed floor.  With a physical limiter inserted it is
        # an internal small-signal boundary; require 40 mV polarity there and
        # independently require 200 mV at the actual sampler input.
        rx_floor = 0.04 if args.restorer_mode != "none" else 0.08
        passed = (complete and min(minima["tx_even"], minima["tx_odd"]) >= 0.05
                  and min(minima["pin_even"], minima["pin_odd"]) >= 0.10
                  and min(minima["rx_even"], minima["rx_odd"]) >= rx_floor
                  and (args.restorer_mode == "none"
                       or min(minima["rest_even"], minima["rest_odd"]) >= 0.20)
                  and min(minima["fe_even"], minima["fe_odd"]) >= 0.30
                  and min(minima["q_even"], minima["q_odd"]) >= 0.50
                  and args.vdd * 0.5 - 0.25 <= observed.get("rx_cm_avg", 0.0)
                  <= args.vdd * 0.5 + 0.25
                  and 0.50 <= observed.get("amp_cm_avg", 0.0) <= args.vdd - 0.10
                  and (args.restorer_mode == "none"
                       or 0.50 <= observed.get("rest_cm_avg", 0.0) <= args.vdd - 0.10)
                  and 0.010 <= current <= 0.060)
        result = {
            "id": case_id, "conversion_offset_s": offset_ps * 1e-12,
            "capture_close_s": capture_close, "complete": complete,
            "minimum_tx_even_v": minima["tx_even"],
            "minimum_tx_odd_v": minima["tx_odd"],
            "minimum_pin_even_v": minima["pin_even"],
            "minimum_pin_odd_v": minima["pin_odd"],
            "minimum_rx_even_v": minima["rx_even"],
            "minimum_rx_odd_v": minima["rx_odd"],
            "minimum_frontend_even_v": minima["fe_even"],
            "minimum_frontend_odd_v": minima["fe_odd"],
            "minimum_capture_even_v": minima["q_even"],
            "minimum_capture_odd_v": minima["q_odd"],
            "rx_common_mode_v": observed.get("rx_cm_avg"),
            "amplifier_common_mode_v": observed.get("amp_cm_avg"),
            "supply_current_a": current, "result": "pass" if passed else "fail",
        }
        if args.restorer_mode != "none":
            result.update({
                "minimum_restored_even_v": minima["rest_even"],
                "minimum_restored_odd_v": minima["rest_odd"],
                "restored_common_mode_v": observed.get("rest_cm_avg"),
            })
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, offsets))
    passing = [case for case in cases if case["result"] == "pass"]
    selected = max(passing, key=lambda case: min(case["minimum_capture_even_v"],
                                                  case["minimum_capture_odd_v"])) if passing else None
    result = {
        "schema_version": 1,
        "claim": "extracted_1p25_gbd_lane_dual_cmos_capture",
        "case_id": args.case_id,
        "environment": [args.mos_corner, args.res_corner, args.vdd, args.temperature, 0.5],
        "controls": {"sampler_phase_deg": args.sampler_phase, "tx_bias_v": args.tx_bias,
                     "rx_bias_v": args.rx_bias, "sampler_bias_v": args.sampler_bias,
                     "termination_code": args.term_code,
                     "rx_bandwidth_mode": args.rx_bandwidth_mode,
                     "restorer_mode": args.restorer_mode,
                     "restorer_bias_v": (args.restorer_bias
                                          if args.restorer_mode != "none" else None)},
        "stimulus": {
            "pattern": args.pattern, "bit_count": len(bits),
            "scored_pair_count": len(pair_indices),
            "tx_clock_jitter_peak_s": args.tx_clock_jitter_ps * 1e-12,
            "tx_clock_duty": args.tx_clock_duty,
            "simulation_timeout_s": args.simulation_timeout_s,
        },
        "channel_stress": {
            "series_resistance_ohm_per_leg": args.channel_series_ohm_per_leg,
            "differential_shunt_capacitance_f": args.channel_shunt_cap_f,
            "topology": "symmetric_two_section_lumped_rc_proxy",
        },
        "supply_stress": {
            "vdd_ripple_peak_v": args.vdd_ripple_mv * 1e-3,
            "vdd_ripple_frequency_hz": args.vdd_ripple_hz,
        },
        "case_count": len(cases), "complete_case_count": sum(case["complete"] for case in cases),
        "passing_case_count": len(passing), "selected_case": selected, "cases": cases,
        "pex_sha256": {name: spine.sha256(path) for name, path in pex_paths.items()},
        "physical_sha256": {name: spine.sha256(path)
                            for name, path in physical_paths.items()},
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
