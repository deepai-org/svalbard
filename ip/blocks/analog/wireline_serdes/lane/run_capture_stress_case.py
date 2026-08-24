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
SAMPLER_SETUP_PS = (-200, -150, -100, -50, 0)
SCALAR = re.compile(
    r"^(tx_even_\d+|tx_odd_\d+|pin_even_\d+|pin_odd_\d+|"
    r"rx_even_\d+|rx_odd_\d+|rest_even_\d+|rest_odd_\d+|"
    r"samp_even_\d+|samp_odd_\d+|samp_even_cm_\d+|samp_odd_cm_\d+|"
    r"fe_even_\d+|fe_odd_\d+|q_even_\d+|q_odd_\d+|"
    r"fe_write_even_\d+|fe_write_odd_\d+|"
    r"fe_write_even_cm_\d+|fe_write_odd_cm_\d+|"
    r"samp_setup_m?\d+_(?:even|odd)_\d+|"
    r"rx_hold_even_\d+|rx_hold_odd_\d+|"
    r"pi_clk_rise|pi_clk_fall|"
    r"tx_cm_avg|rx_cm_avg|amp_cm_avg|rest_cm_avg|"
    r"supply_current)\s*=\s*([-+0-9.eE]+)", re.MULTILINE,
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    """Replace one structural template fragment or fail closed."""
    if text.count(old) != 1:
        raise SystemExit(f"testbench {label} boundary changed")
    return text.replace(old, new)


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


def differential_clock_pwl(common_mode: float, peak: float, frequency: float,
                           delay: float, phase_deg: float, edge_skew_s: float,
                           stop: float, inverted: bool) -> str:
    """Create a differential clock with independently displaced edge classes.

    Positive edge skew delays P-over-N crossings and advances N-over-P
    crossings by equal amounts.  Thus the average phase is unchanged while
    the two half-cycle widths change by ``edge_skew_s``.
    """
    period = 1 / frequency
    low, high = common_mode - peak, common_mode + peak
    edges = []
    for cycle in range(-4, math.ceil((stop - delay) / period) + 5):
        rise = delay + period * (cycle - phase_deg / 360.0)
        fall = delay + period * (cycle + 0.5 - phase_deg / 360.0)
        edges.extend(((rise + edge_skew_s / 2, True),
                      (fall - edge_skew_s / 2, False)))
    edges = sorted(edge for edge in edges if 0.5e-9 <= edge[0] <= stop + period)
    if not edges:
        raise ValueError("differential clock has no edges in simulation window")
    state_high = not edges[0][1]
    initial = high if state_high else low
    points = [(0.0, initial), (edges[0][0] - 30e-12, initial)]
    for edge, high_after in edges:
        before = high if state_high else low
        state_high = high_after
        after = high if state_high else low
        points.extend(((edge - 10e-12, before), (edge + 10e-12, after)))
    if inverted:
        points = [(time, 2 * common_mode - voltage) for time, voltage in points]
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


def duplicate_sampler_hold_devices(pex: str) -> tuple[str, int]:
    """Double only the extracted sampler cross-coupled hold devices."""
    output = []
    count = 0
    sampler_node = re.compile(r"SAMP_([EO])_([PN])\.t\d+")
    for line in pex.splitlines():
        output.append(line)
        tokens = line.split()
        if (len(tokens) < 7 or not tokens[0].startswith("X")
                or "nfet_03v3" not in tokens or "w=6u" not in tokens):
            continue
        outputs = [sampler_node.fullmatch(node) for node in tokens[1:4]]
        outputs = [match for match in outputs if match]
        if (len(outputs) != 2 or outputs[0].group(1) != outputs[1].group(1)
                or outputs[0].group(2) == outputs[1].group(2)
                or not any(node.startswith("a_") for node in tokens[1:4])):
            continue
        output.append(" ".join([f"XDIAG_HOLD_{count}"] + tokens[1:]))
        count += 1
    return "\n".join(output) + "\n", count


def insert_diagnostic_decision_retimer(pex: str) -> tuple[str, int]:
    """Insert full-cycle CML follower latches ahead of the converters.

    This deliberately produces a mixed schematic/PEX diagnostic, not physical
    qualification.  Only the 32 converter input-gate fingers are disconnected
    from the routed sampler nets.  The retained parent still supplies all
    upstream devices and parasitics, while two complementary-phase CML latches
    load and capture the real extracted sampler outputs.
    """
    output = []
    replacement_count = 0
    sampler_gate = re.compile(r"SAMP_([EO])_([PN])\.t\d+")
    for line in pex.splitlines():
        tokens = line.split()
        if (len(tokens) >= 7 and tokens[0].startswith("X")
                and "nfet_03v3" in tokens
                and any(f"XFE_{lane}.{device}" in " ".join(tokens[1:4])
                        for lane in "EO" for device in ("NIP", "NIN"))):
            match = sampler_gate.fullmatch(tokens[2])
            if match:
                tokens[2] = f"RET_{match.group(1)}_{match.group(2)}"
                line = " ".join(tokens)
                replacement_count += 1
        output.append(line)
    if replacement_count != 32:
        return pex, replacement_count
    end_indices = [index for index, line in enumerate(output)
                   if line.strip() == ".ends"]
    if len(end_indices) != 1 or any(line.strip()
                                    for line in output[end_indices[0] + 1:]):
        raise SystemExit("diagnostic retimer parent boundary changed")
    end_index = end_indices[0]
    output[end_index:end_index] = [
        "* Diagnostic full-cycle decision retimers; not extracted layout.",
        "XDIAG_RETIME_E SAMP_E_P SAMP_E_N PI_CLK_N PI_CLK_P SAMP_BIAS VDD VSS",
        "+ RET_E_P RET_E_N cml_sampler_latch",
        "XDIAG_RETIME_O SAMP_O_P SAMP_O_N PI_CLK_P PI_CLK_N SAMP_BIAS VDD VSS",
        "+ RET_O_P RET_O_N cml_sampler_latch",
    ]
    return "\n".join(output) + "\n", replacement_count


def rewire_direct_regenerative_sampler(pex: str) -> tuple[str, dict[str, int]]:
    """Feed both extracted StrongARM converters directly from the RX output.

    The modified netlist retains the routed receiver, converter, capture, clock,
    supply, and parasitic networks.  It disconnects the obsolete restorer and
    level-sensitive sampler input gates and changes only the converter input
    gates to the corresponding RX output.  This is a mechanism diagnostic;
    the eventual parent must physically route and extract the same topology.
    """
    counts = {"converter": 0, "sampler": 0, "restorer": 0}
    output = []
    converter_gate = re.compile(r"SAMP_([EO])_([PN])\.t\d+")
    sampler_gate = re.compile(r"RX_REST([PN])\.t\d+")
    restorer_gate = re.compile(r"RX_RAW[PN]\.t\d+")
    for line in pex.splitlines():
        tokens = line.split()
        if (len(tokens) >= 7 and tokens[0].startswith("X")
                and "nfet_03v3" in tokens):
            match = converter_gate.fullmatch(tokens[2])
            if (match and "w=8u" in tokens
                    and "XRX.XFRONT.XFE_" in " ".join(tokens[1:4])):
                tokens[2] = f"RX_RAW{match.group(2)}"
                counts["converter"] += 1
                line = " ".join(tokens)
            elif sampler_gate.fullmatch(tokens[2]) and "w=6u" in tokens:
                tokens[2] = "VSS"
                counts["sampler"] += 1
                line = " ".join(tokens)
            elif restorer_gate.fullmatch(tokens[2]) and "w=10u" in tokens:
                tokens[2] = "VSS"
                counts["restorer"] += 1
                line = " ".join(tokens)
        output.append(line)
    return "\n".join(output) + "\n", counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tx-pex", required=True, type=Path)
    parser.add_argument("--tx-physical", type=Path)
    parser.add_argument("--term-pex", type=Path)
    parser.add_argument("--term-physical", type=Path)
    parser.add_argument("--rx-pex", type=Path)
    parser.add_argument("--sampler-pex", type=Path)
    parser.add_argument("--rx-spine-pex", type=Path)
    parser.add_argument("--rx-spine-physical", type=Path)
    parser.add_argument("--rx-frontend-parent-pex", type=Path)
    parser.add_argument("--rx-frontend-parent-physical", type=Path)
    parser.add_argument("--rx-capture-parent-pex", type=Path)
    parser.add_argument("--rx-capture-parent-physical", type=Path)
    parser.add_argument("--rx-pi-capture-parent-pex", type=Path)
    parser.add_argument("--rx-pi-capture-parent-physical", type=Path)
    parser.add_argument("--rx-regenerative-capture-parent-pex", type=Path)
    parser.add_argument("--rx-regenerative-capture-parent-physical", type=Path)
    parser.add_argument("--frontend-pex", type=Path)
    parser.add_argument("--frontend-physical", type=Path)
    parser.add_argument("--deserializer-pex", type=Path)
    parser.add_argument("--deserializer-physical", type=Path)
    parser.add_argument("--base-physical", type=Path)
    parser.add_argument("--restorer-pex", type=Path)
    parser.add_argument("--restorer-physical", type=Path)
    parser.add_argument("--restorer-cell")
    parser.add_argument("--serial-rate-gbd", type=float,
                        choices=(1.25, 2.5), default=1.25)
    parser.add_argument("--latency-ui", type=int, choices=range(-3, 4), default=0)
    parser.add_argument("--sampler-latency-ui", type=int, choices=range(-3, 4))
    parser.add_argument("--frontend-latency-ui", type=int, choices=range(-3, 4))
    parser.add_argument("--frontend-write-latency-ui", type=int,
                        choices=range(-3, 4))
    parser.add_argument("--capture-latency-ui", type=int, choices=range(-3, 4))
    parser.add_argument("--sampler-overshoot-limit-mv", type=float, default=50.0)
    parser.add_argument("--rx-window-start-ps", type=int, default=0)
    parser.add_argument("--ac-initial-v", type=float)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--offset-ps", type=int, action="append")
    parser.add_argument("--sampler-phase", type=float, default=135.0)
    parser.add_argument("--pi-control-a", type=float, default=1.15)
    parser.add_argument("--pi-control-b", type=float, default=1.15)
    parser.add_argument("--pi-buffer-bias", type=float, default=1.15)
    parser.add_argument("--clock-restorer-bias", type=float, default=1.15)
    parser.add_argument("--pi-input-phase-deg", type=float, default=0.0)
    parser.add_argument("--pi-invert", action="store_true")
    parser.add_argument("--pi-output-clock-override", action="store_true")
    parser.add_argument("--pi-output-edge-skew-ps", type=float, default=0.0)
    parser.add_argument("--diagnostic-sampler-load-scale", type=float, default=1.0)
    parser.add_argument("--diagnostic-sampler-hold-scale", type=int,
                        choices=(1, 2), default=1)
    parser.add_argument("--diagnostic-decision-retimer", action="store_true")
    parser.add_argument("--diagnostic-restorer-load-length-um", type=float,
                        default=4.2)
    parser.add_argument("--diagnostic-restorer-bypass", action="store_true")
    parser.add_argument("--diagnostic-rx-single-stage", action="store_true")
    parser.add_argument("--diagnostic-direct-regenerative-sampler",
                        action="store_true")
    parser.add_argument("--sampler-observation-load-ff", type=float,
                        default=25.0)
    parser.add_argument("--capture-width-ps", type=int, default=380)
    parser.add_argument("--odd-capture-width-ps", type=int)
    parser.add_argument("--capture-delay-ps", type=int)
    parser.add_argument("--capture-output-delay-ps", type=int)
    parser.add_argument("--even-capture-skew-ps", type=int, default=0)
    parser.add_argument("--odd-capture-skew-ps", type=int, default=0)
    parser.add_argument("--frontend-sense-width-ps", type=int)
    parser.add_argument("--odd-frontend-sense-width-ps", type=int)
    parser.add_argument("--even-frontend-skew-ps", type=int, default=0)
    parser.add_argument("--odd-frontend-skew-ps", type=int, default=0)
    parser.add_argument("--tx-bias", type=float, default=1.1)
    parser.add_argument("--tx-load-code", type=int, choices=range(5), default=2)
    parser.add_argument("--rx-bias", type=float, default=1.1)
    parser.add_argument("--sampler-bias", type=float, default=1.1)
    parser.add_argument("--restorer-bias", type=float, default=1.1)
    parser.add_argument("--frontend-tail-boost", action="store_true")
    parser.add_argument("--even-frontend-tail-boost", action="store_true")
    parser.add_argument("--odd-frontend-tail-boost", action="store_true")
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
    routed_rx_spine = args.rx_spine_pex is not None
    routed_rx_frontend = args.rx_frontend_parent_pex is not None
    routed_rx_capture = args.rx_capture_parent_pex is not None
    routed_rx_pi_capture = args.rx_pi_capture_parent_pex is not None
    routed_rx_regenerative_capture = (
        args.rx_regenerative_capture_parent_pex is not None)
    routed_capture_parent = (routed_rx_capture or routed_rx_pi_capture
                             or routed_rx_regenerative_capture)
    routed_front_parent = routed_rx_frontend or routed_capture_parent
    routed_rx = routed_rx_spine or routed_front_parent
    if sum((routed_rx_spine, routed_rx_frontend, routed_rx_capture,
            routed_rx_pi_capture, routed_rx_regenerative_capture)) > 1:
        parser.error("select one routed RX parent")
    if not 1 <= args.jobs <= 4 or not 1 <= args.term_code <= 6:
        parser.error("jobs or termination code outside declared range")
    offsets = tuple(args.offset_ps) if args.offset_ps else DEFAULT_OFFSETS_PS
    maximum_offset_ps = 300 if args.serial_rate_gbd == 1.25 else 700
    if any(offset < 0 or offset > maximum_offset_ps for offset in offsets):
        parser.error(f"conversion offset must be 0--{maximum_offset_ps} ps")
    if not 12 <= args.bit_count <= 128 or args.bit_count % 2:
        parser.error("bit count must be an even value from 12 through 128")
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
    if not 100 <= args.capture_width_ps <= 650:
        parser.error("capture pulse width must be 100--650 ps")
    if (args.odd_capture_width_ps is not None
            and not 100 <= args.odd_capture_width_ps <= 650):
        parser.error("odd capture pulse width must be 100--650 ps")
    if (args.capture_delay_ps is not None
            and not 200 <= args.capture_delay_ps <= 600):
        parser.error("capture pulse delay must be 200--600 ps")
    if (args.capture_output_delay_ps is not None
            and not 600 <= args.capture_output_delay_ps <= 1200):
        parser.error("capture output delay must be 600--1200 ps")
    if not -150 <= args.even_capture_skew_ps <= 450:
        parser.error("even capture skew must be -150--450 ps")
    if not -250 <= args.odd_capture_skew_ps <= 150:
        parser.error("odd capture skew must be -250--150 ps")
    if (args.frontend_sense_width_ps is not None
            and not 250 <= args.frontend_sense_width_ps <= 700):
        parser.error("front-end sense pulse width must be 250--700 ps")
    if (args.odd_frontend_sense_width_ps is not None
            and not 250 <= args.odd_frontend_sense_width_ps <= 700):
        parser.error("odd front-end sense pulse width must be 250--700 ps")
    if not -150 <= args.even_frontend_skew_ps <= 450:
        parser.error("even front-end skew must be -150--450 ps")
    if not -450 <= args.odd_frontend_skew_ps <= 450:
        parser.error("odd front-end skew must be -450--450 ps")
    if (routed_rx and not routed_rx_regenerative_capture
            and args.restorer_mode != "data"):
        parser.error("routed RX parent requires --restorer-mode data")
    if routed_rx_regenerative_capture and args.restorer_mode != "none":
        parser.error("regenerative RX parent requires --restorer-mode none")
    if routed_rx_spine and not args.rx_spine_physical:
        parser.error("routed RX spine requires its physical record")
    if routed_rx_spine and not args.term_physical:
        parser.error("routed RX spine requires termination physical evidence")
    if routed_rx_frontend and not args.rx_frontend_parent_physical:
        parser.error("routed RX front end requires its physical record")
    if routed_rx_capture and not args.rx_capture_parent_physical:
        parser.error("routed RX capture requires its physical record")
    if routed_rx_pi_capture and not args.rx_pi_capture_parent_physical:
        parser.error("routed RX PI capture requires its physical record")
    if (routed_rx_regenerative_capture
            and not args.rx_regenerative_capture_parent_physical):
        parser.error("routed regenerative capture requires its physical record")
    if not routed_capture_parent and not (
            args.deserializer_pex and args.deserializer_physical):
        parser.error("leaf capture requires its PEX and physical record")
    if not routed_rx and not (args.rx_pex and args.sampler_pex):
        parser.error("provide an RX-spine PEX or both RX and sampler PEX")
    if (not routed_rx and args.restorer_mode != "none" and not (
            args.restorer_pex and args.restorer_physical)):
        parser.error("restorer mode requires its PEX and physical record")
    if routed_rx and args.base_physical is not None:
        parser.error("base leaf physical record is invalid with routed RX parent")
    if not routed_front_parent and not (args.term_pex and args.frontend_pex):
        parser.error("leaf composition requires termination and converter PEX")
    if args.restorer_cell is not None and not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]*", args.restorer_cell):
        parser.error("invalid restorer cell name")
    if not 0 <= args.rx_window_start_ps <= 250:
        parser.error("RX hold window must start between 0 and 250 ps")
    if args.ac_initial_v is not None and not 0.0 <= args.ac_initial_v <= 2.5:
        parser.error("AC-coupling initial voltage must be between 0 and 2.5 V")
    if routed_rx_pi_capture and not all(
            0.25 <= value <= 1.35 for value in
            (args.pi_control_a, args.pi_control_b, args.pi_buffer_bias,
             args.clock_restorer_bias)):
        parser.error("PI controls must be between 0.25 V and 1.35 V")
    if not 0.0 <= args.pi_input_phase_deg < 360.0:
        parser.error("PI input phase must be in [0, 360) degrees")
    if args.pi_output_clock_override and not routed_rx_pi_capture:
        parser.error("PI output clock override requires the routed PI parent")
    if not -320.0 <= args.pi_output_edge_skew_ps <= 320.0:
        parser.error("PI output edge skew must be between -320 and 320 ps")
    if not 0.0 <= args.sampler_overshoot_limit_mv <= 200.0:
        parser.error("sampler overshoot limit must be between 0 and 200 mV")
    if args.pi_output_edge_skew_ps and not args.pi_output_clock_override:
        parser.error("PI output edge skew requires the diagnostic clock override")
    if not 1.0 <= args.diagnostic_sampler_load_scale <= 2.5:
        parser.error("diagnostic sampler load scale must be between 1.0 and 2.5")
    if args.diagnostic_sampler_load_scale != 1.0 and not routed_rx_pi_capture:
        parser.error("diagnostic sampler load scaling requires the routed PI parent")
    if args.diagnostic_sampler_hold_scale != 1 and not routed_rx_pi_capture:
        parser.error("diagnostic sampler hold scaling requires the routed PI parent")
    if args.diagnostic_decision_retimer and not routed_rx_pi_capture:
        parser.error("diagnostic decision retimer requires the routed PI parent")
    if not 2.0 <= args.diagnostic_restorer_load_length_um <= 4.2:
        parser.error("diagnostic restorer load length must be 2.0--4.2 um")
    if (args.diagnostic_restorer_load_length_um != 4.2
            and not routed_rx_pi_capture):
        parser.error("diagnostic restorer load change requires the routed PI parent")
    if args.diagnostic_restorer_bypass and not routed_rx_pi_capture:
        parser.error("diagnostic restorer bypass requires the routed PI parent")
    if args.diagnostic_rx_single_stage and not args.diagnostic_restorer_bypass:
        parser.error("diagnostic single-stage RX requires restorer bypass")
    if (args.diagnostic_direct_regenerative_sampler
            and not routed_rx_pi_capture):
        parser.error("direct regenerative sampler requires the routed PI parent")
    if (args.diagnostic_direct_regenerative_sampler
            and (args.diagnostic_restorer_bypass
                 or args.diagnostic_rx_single_stage
                 or args.diagnostic_decision_retimer)):
        parser.error("direct regenerative sampler is exclusive with other rewires")
    if not 0.01 <= args.sampler_observation_load_ff <= 100.0:
        parser.error("sampler observation load must be 0.01--100 fF per rail")
    args.work.mkdir(parents=True, exist_ok=True)

    sampler_latency_ui = (args.sampler_latency_ui
                          if args.sampler_latency_ui is not None
                          else args.latency_ui)
    frontend_latency_ui = (args.frontend_latency_ui
                           if args.frontend_latency_ui is not None
                           else args.latency_ui)
    frontend_write_latency_ui = (
        args.frontend_write_latency_ui
        if args.frontend_write_latency_ui is not None else args.latency_ui)
    capture_latency_ui = (args.capture_latency_ui
                          if args.capture_latency_ui is not None
                          else args.latency_ui)

    rx_pi_include = args.rx_pi_capture_parent_pex
    modified_pex = (args.rx_pi_capture_parent_pex.read_text()
                    if routed_rx_pi_capture else "")
    if args.diagnostic_sampler_load_scale != 1.0:
        load_pattern = re.compile(
            r"^(X\S+ VDD\.t\d+ SAMP_[EO]_[PN]\.t\d+ VSS\.t\d+ "
            r"ppolyf_u r_width=2u r_length=)5u$", re.MULTILINE)
        replacement_length = 5 * args.diagnostic_sampler_load_scale
        modified_pex, replacement_count = load_pattern.subn(
            lambda match: f"{match.group(1)}{replacement_length:.6g}u", modified_pex)
        if replacement_count != 4:
            raise SystemExit(
                "diagnostic sampler load boundary no longer contains four loads")
    if args.diagnostic_sampler_hold_scale == 2:
        modified_pex, replacement_count = duplicate_sampler_hold_devices(
            modified_pex)
        if replacement_count != 8:
            raise SystemExit(
                "diagnostic sampler boundary no longer contains eight hold fingers")
    if args.diagnostic_decision_retimer:
        modified_pex, replacement_count = insert_diagnostic_decision_retimer(
            modified_pex)
        if replacement_count != 32:
            raise SystemExit(
                "diagnostic converter boundary no longer contains 32 input fingers")
    if args.diagnostic_restorer_load_length_um != 4.2:
        load_pattern = re.compile(
            r"^(X\S+ \S+ \S+ \S+ ppolyf_u r_width=2u r_length=)4\.2u$",
            re.MULTILINE)
        modified_pex, replacement_count = load_pattern.subn(
            lambda match: (f"{match.group(1)}"
                           f"{args.diagnostic_restorer_load_length_um:.6g}u"),
            modified_pex)
        if replacement_count != 4:
            raise SystemExit(
                "diagnostic restorer boundary no longer contains four loads")
    if args.diagnostic_restorer_bypass:
        sampler_input = re.compile(r"RX_REST([PN])\.t\d+")
        output = []
        sampler_replacement_count = 0
        restorer_replacement_count = 0
        for line in modified_pex.splitlines():
            tokens = line.split()
            if (len(tokens) >= 7 and tokens[0].startswith("X")
                    and "nfet_03v3" in tokens):
                match = sampler_input.fullmatch(tokens[2])
                if match and "w=6u" in tokens:
                    if args.diagnostic_rx_single_stage:
                        # The first RX stage is inverting.  Swap its two
                        # extracted output nets to preserve top-level polarity.
                        tokens[2] = ({"P": "a_n3600_5641.n2",
                                      "N": "a_n6572_3500.n2"}
                                     [match.group(1)])
                    else:
                        tokens[2] = f"RX_RAW{match.group(1)}"
                    line = " ".join(tokens)
                    sampler_replacement_count += 1
                elif re.fullmatch(r"RX_RAW[PN]\.t\d+", tokens[2]) \
                        and "w=10u" in tokens:
                    tokens[2] = "VSS"
                    line = " ".join(tokens)
                    restorer_replacement_count += 1
                elif (args.diagnostic_rx_single_stage and "w=5u" in tokens
                      and re.fullmatch(
                          r"a_n(?:6572_3500|3600_5641)\.t[67]", tokens[2])):
                    tokens[2] = "VSS"
                    line = " ".join(tokens)
                    restorer_replacement_count += 1
            output.append(line)
        expected_removed_inputs = 8 if args.diagnostic_rx_single_stage else 4
        if (sampler_replacement_count != 8
                or restorer_replacement_count != expected_removed_inputs):
            raise SystemExit(
                "diagnostic bypass boundary input-finger count changed")
        modified_pex = "\n".join(output) + "\n"
    if args.diagnostic_direct_regenerative_sampler:
        modified_pex, replacement_counts = rewire_direct_regenerative_sampler(
            modified_pex)
        if replacement_counts != {"converter": 32, "sampler": 8,
                                   "restorer": 4}:
            raise SystemExit(
                "diagnostic direct-sampler boundary changed: "
                f"{replacement_counts}")
    if (args.diagnostic_sampler_load_scale != 1.0
            or args.diagnostic_sampler_hold_scale != 1
            or args.diagnostic_decision_retimer
            or args.diagnostic_restorer_load_length_um != 4.2
            or args.diagnostic_restorer_bypass
            or args.diagnostic_rx_single_stage
            or args.diagnostic_direct_regenerative_sampler):
        rx_pi_include = args.work / "diagnostic_sampler_parent.pex.spice"
        rx_pi_include.write_text(modified_pex)

    rate = args.serial_rate_gbd * 1e9
    ui = 1 / rate
    period = 2 * ui
    timing_scale = 1.25e9 / rate
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
    for index in range(4):
        template = re.sub(
            rf"VLOAD{index} LOAD_EN{index}_N_SRC 0 (?:0|@VDD_V@)",
            f"VLOAD{index} LOAD_EN{index}_N_SRC 0 "
            + ("0" if index < args.tx_load_code else "@VDD_V@"),
            template,
        )
    template = template.replace(
        "@SAMPLER_INCLUDE@",
        "@SAMPLER_INCLUDE@\n@RESTORER_INCLUDE@\n"
        "@FRONTEND_INCLUDE@\n@DESERIALIZER_INCLUDE@",
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
    if routed_front_parent:
        template = replace_once(
            template,
            "XTERM RXP RXN TERM_EN0_N TERM_EN1_N TERM_EN2_N TERM_EN3_N TERM_EN4_N\n"
            "+ TERM_EN5_N TERM_EN6_N VDD 0 @TERM_CELL@\n",
            "",
            "termination instance",
        )
        parent_instance = (
            "XRXPICAP RXP RXN TERM_EN0_N TERM_EN1_N TERM_EN2_N TERM_EN3_N\n"
            "+ TERM_EN4_N TERM_EN5_N TERM_EN6_N VTHP VTHN RX_BIAS RX_BW_EN_N\n"
            "+ REST_BIAS SAMP_BIAS E_SENSE_CLK E_REGEN_CLK\n"
            "+ E_REGEN_CLKB E_CAPTURE_CLK E_CAPTURE_CLKB @E_SENSE_BOOST@\n"
            "+ O_SENSE_CLK O_REGEN_CLK O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB\n"
            "+ @O_SENSE_BOOST@ VDD 0 PHASE_A_P PHASE_A_N PHASE_B_P PHASE_B_N\n"
            "+ PI_CTRL_A PI_CTRL_B PI_BUF_BIAS CLK_REST_BIAS PI_RAW_P PI_RAW_N\n"
            "+ PI_CLK_P PI_CLK_N\n"
            "+ RX_RAWP RX_RAWN RXOP RXON\n"
            "+ SAMP_E_P SAMP_E_N SAMP_O_P SAMP_O_N FE_E_P FE_E_N FE_O_P FE_O_N\n"
            "+ EVEN_Q EVEN_QB ODD_Q ODD_QB lane_rx_pi_capture_pex\n"
            if routed_rx_pi_capture else
            "XREGENCAP RXP RXN TERM_EN0_N TERM_EN1_N TERM_EN2_N TERM_EN3_N\n"
            "+ TERM_EN4_N TERM_EN5_N TERM_EN6_N VTHP VTHN RX_BIAS RX_BW_EN_N\n"
            "+ E_SENSE_CLK E_REGEN_CLK E_REGEN_CLKB E_CAPTURE_CLK\n"
            "+ E_CAPTURE_CLKB @E_SENSE_BOOST@ O_SENSE_CLK O_REGEN_CLK\n"
            "+ O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB @O_SENSE_BOOST@\n"
            "+ VDD 0 RXOP RXON FE_E_P FE_E_N FE_O_P FE_O_N\n"
            "+ EVEN_Q EVEN_QB ODD_Q ODD_QB lane_rx_regenerative_capture_pex\n"
            if routed_rx_regenerative_capture else
            "XRXCAP RXP RXN TERM_EN0_N TERM_EN1_N TERM_EN2_N TERM_EN3_N\n"
            "+ TERM_EN4_N TERM_EN5_N TERM_EN6_N VTHP VTHN RX_BIAS RX_BW_EN_N\n"
            "+ REST_BIAS SAMP_CLK_P SAMP_CLK_N SAMP_BIAS E_SENSE_CLK\n"
            "+ E_REGEN_CLK E_REGEN_CLKB E_CAPTURE_CLK E_CAPTURE_CLKB @E_SENSE_BOOST@\n"
            "+ O_SENSE_CLK O_REGEN_CLK O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB\n"
            "+ @O_SENSE_BOOST@ VDD 0 RX_RAWP RX_RAWN RXOP RXON SAMP_E_P SAMP_E_N\n"
            "+ SAMP_O_P SAMP_O_N FE_E_P FE_E_N FE_O_P FE_O_N\n"
            "+ EVEN_Q EVEN_QB ODD_Q ODD_QB lane_rx_capture_pex\n"
            if routed_rx_capture else
            "XRXFRONT RXP RXN TERM_EN0_N TERM_EN1_N TERM_EN2_N TERM_EN3_N\n"
            "+ TERM_EN4_N TERM_EN5_N TERM_EN6_N VTHP VTHN RX_BIAS RX_BW_EN_N\n"
            "+ REST_BIAS SAMP_CLK_P SAMP_CLK_N SAMP_BIAS E_SENSE_CLK\n"
            "+ E_REGEN_CLK E_REGEN_CLKB E_CAPTURE_CLK E_CAPTURE_CLKB @E_SENSE_BOOST@\n"
            "+ O_SENSE_CLK O_REGEN_CLK O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB\n"
            "+ @O_SENSE_BOOST@ VDD 0 RX_RAWP RX_RAWN RXOP RXON SAMP_E_P SAMP_E_N\n"
            "+ SAMP_O_P SAMP_O_N FE_E_P FE_E_N FE_O_P FE_O_N lane_rx_frontend_pex\n"
        )
        template = replace_once(
            template,
            "XRX RXP RXN VTHP VTHN RX_BIAS RX_BW_EN_N VDD 0 RXOP RXON @RX_CELL@\n"
            "CRXOP RXOP 0 25f\nCRXON RXON 0 25f",
            parent_instance + (
                "CRXOP RXOP 0 25f\nCRXON RXON 0 25f"
                if routed_rx_regenerative_capture else
                "CRXRAWP RX_RAWP 0 25f\nCRXRAWN RX_RAWN 0 25f\n"
                "CRESTOP RXOP 0 25f\nCRESTON RXON 0 25f"),
            "RX instance",
        )
        template = replace_once(
            template,
            "XSAMPLER RXOP RXON SAMP_CLK_P SAMP_CLK_N SAMP_BIAS VDD 0\n"
            "+ SAMP_E_P SAMP_E_N SAMP_O_P SAMP_O_N @SAMPLER_CELL@\n"
            "CE_P SAMP_E_P 0 25f\nCE_N SAMP_E_N 0 25f\n"
            "CO_P SAMP_O_P 0 25f\nCO_N SAMP_O_N 0 25f",
            "CE_P SAMP_E_P 0 25f\nCE_N SAMP_E_N 0 25f\n"
            "CO_P SAMP_O_P 0 25f\nCO_N SAMP_O_N 0 25f",
            "sampler instance",
        )
        if routed_rx_pi_capture:
            phase_ap, phase_an, phase_bp, phase_bn = (
                (180, 0, 90, 270) if args.pi_invert else (0, 180, 270, 90)
            )
            phase_ap = (phase_ap + args.pi_input_phase_deg) % 360
            phase_an = (phase_an + args.pi_input_phase_deg) % 360
            phase_bp = (phase_bp + args.pi_input_phase_deg) % 360
            phase_bn = (phase_bn + args.pi_input_phase_deg) % 360
            template = replace_once(
                template,
                "VSCLKP SAMP_CLK_P_SRC 0 SIN(@SAMPLE_CLOCK_CM@ @SAMPLE_CLOCK_PEAK@ @CLOCK_HZ@ 1n 0 @CLOCK_PHASE@)\n"
                "VSCLKN SAMP_CLK_N_SRC 0 SIN(@SAMPLE_CLOCK_CM@ @SAMPLE_CLOCK_PEAK@ @CLOCK_HZ@ 1n 0 @CLOCK_N_PHASE@)\n"
                "RCLKP SAMP_CLK_P_SRC SAMP_CLK_P 1\n"
                "RCLKN SAMP_CLK_N_SRC SAMP_CLK_N 1",
                f"VPHASEAP PHASE_A_P_SRC 0 SIN(@PI_INPUT_CM@ 0.20 @CLOCK_HZ@ 1n 0 {phase_ap})\n"
                f"VPHASEAN PHASE_A_N_SRC 0 SIN(@PI_INPUT_CM@ 0.20 @CLOCK_HZ@ 1n 0 {phase_an})\n"
                f"VPHASEBP PHASE_B_P_SRC 0 SIN(@PI_INPUT_CM@ 0.20 @CLOCK_HZ@ 1n 0 {phase_bp})\n"
                f"VPHASEBN PHASE_B_N_SRC 0 SIN(@PI_INPUT_CM@ 0.20 @CLOCK_HZ@ 1n 0 {phase_bn})\n"
                "VPICTRLA PI_CTRL_A_SRC 0 PWL(0 0 500p @PI_CTRL_A_V@)\n"
                "VPICTRLB PI_CTRL_B_SRC 0 PWL(0 0 500p @PI_CTRL_B_V@)\n"
                "VPIBUF PI_BUF_BIAS_SRC 0 PWL(0 0 500p @PI_BUF_BIAS_V@)\n"
                "VCLKREST CLK_REST_BIAS_SRC 0 PWL(0 0 500p @CLK_REST_BIAS_V@)\n"
                "RPHASEAP PHASE_A_P_SRC PHASE_A_P 1\n"
                "RPHASEAN PHASE_A_N_SRC PHASE_A_N 1\n"
                "RPHASEBP PHASE_B_P_SRC PHASE_B_P 1\n"
                "RPHASEBN PHASE_B_N_SRC PHASE_B_N 1\n"
                "RPICTRLA PI_CTRL_A_SRC PI_CTRL_A 1\n"
                "RPICTRLB PI_CTRL_B_SRC PI_CTRL_B 1\n"
                "RPIBUF PI_BUF_BIAS_SRC PI_BUF_BIAS 1\n"
                "RCLKREST CLK_REST_BIAS_SRC CLK_REST_BIAS 1\n"
                "@PI_OUTPUT_CLOCK_OVERRIDE@",
                "sampler clock sources",
            )
    elif routed_rx_spine:
        template = replace_once(
            template,
            "XRX RXP RXN VTHP VTHN RX_BIAS RX_BW_EN_N VDD 0 RXOP RXON @RX_CELL@\n"
            "CRXOP RXOP 0 25f\nCRXON RXON 0 25f",
            "XRXSPINE RXP RXN VTHP VTHN RX_BIAS RX_BW_EN_N REST_BIAS\n"
            "+ SAMP_CLK_P SAMP_CLK_N SAMP_BIAS VDD 0 RX_RAWP RX_RAWN\n"
            "+ RXOP RXON SAMP_E_P SAMP_E_N SAMP_O_P SAMP_O_N lane_rx_spine_pex\n"
            "CRXRAWP RX_RAWP 0 25f\nCRXRAWN RX_RAWN 0 25f\n"
            "CRESTOP RXOP 0 25f\nCRESTON RXON 0 25f",
            "RX instance",
        )
        template = replace_once(
            template,
            "XSAMPLER RXOP RXON SAMP_CLK_P SAMP_CLK_N SAMP_BIAS VDD 0\n"
            "+ SAMP_E_P SAMP_E_N SAMP_O_P SAMP_O_N @SAMPLER_CELL@\n"
            "CE_P SAMP_E_P 0 25f\nCE_N SAMP_E_N 0 25f\n"
            "CO_P SAMP_O_P 0 25f\nCO_N SAMP_O_N 0 25f",
            "CE_P SAMP_E_P 0 25f\nCE_N SAMP_E_N 0 25f\n"
            "CO_P SAMP_O_P 0 25f\nCO_N SAMP_O_N 0 25f",
            "sampler instance",
        )
    elif args.restorer_mode != "none":
        restorer_cell = {
            "single": "cml_clock_restorer_pex",
            "cascade": "cml_clock_restorer_cascade_pex",
            "data": "cml_data_restorer_pex",
        }[args.restorer_mode]
        if args.restorer_cell is not None:
            restorer_cell = args.restorer_cell
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
        "CE_P SAMP_E_P 0 25f\nCE_N SAMP_E_N 0 25f\n"
        "CO_P SAMP_O_P 0 25f\nCO_N SAMP_O_N 0 25f",
        f"CE_P SAMP_E_P 0 {args.sampler_observation_load_ff:.6g}f\n"
        f"CE_N SAMP_E_N 0 {args.sampler_observation_load_ff:.6g}f\n"
        f"CO_P SAMP_O_P 0 {args.sampler_observation_load_ff:.6g}f\n"
        f"CO_N SAMP_O_N 0 {args.sampler_observation_load_ff:.6g}f",
    )
    if args.restorer_mode != "none":
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
VESENSE E_SENSE_SRC 0 PULSE(0 @VDD_V@ @E_SENSE_DELAY@ 20p 20p @SENSE_WIDTH@ @PERIOD@)
VEREGEN E_REGEN_SRC 0 PULSE(0 @VDD_V@ @E_REGEN_DELAY@ 20p 20p @REGEN_WIDTH@ @PERIOD@)
VEREGENB E_REGENB_SRC 0 PULSE(@VDD_V@ 0 @E_REGEN_DELAY@ 20p 20p @REGEN_WIDTH@ @PERIOD@)
VECLK E_CAPTURE_SRC 0 PULSE(0 @VDD_V@ @E_CAPTURE_DELAY@ 20p 20p @CAPTURE_WIDTH@ @PERIOD@)
VECLKB E_CAPTUREB_SRC 0 PULSE(@VDD_V@ 0 @E_CAPTURE_DELAY@ 20p 20p @CAPTURE_WIDTH@ @PERIOD@)
VOSENSE O_SENSE_SRC 0 PULSE(0 @VDD_V@ @O_SENSE_DELAY@ 20p 20p @O_SENSE_WIDTH@ @PERIOD@)
VOREGEN O_REGEN_SRC 0 PULSE(0 @VDD_V@ @O_REGEN_DELAY@ 20p 20p @O_REGEN_WIDTH@ @PERIOD@)
VOREGENB O_REGENB_SRC 0 PULSE(@VDD_V@ 0 @O_REGEN_DELAY@ 20p 20p @O_REGEN_WIDTH@ @PERIOD@)
VOCLK O_CAPTURE_SRC 0 PULSE(0 @VDD_V@ @O_CAPTURE_DELAY@ 20p 20p @O_CAPTURE_WIDTH@ @PERIOD@)
VOCLKB O_CAPTUREB_SRC 0 PULSE(@VDD_V@ 0 @O_CAPTURE_DELAY@ 20p 20p @O_CAPTURE_WIDTH@ @PERIOD@)
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
+ VDD 0 FE_E_P FE_E_N @E_SENSE_BOOST@ cml_to_cmos_pex
XFE_O SAMP_O_P SAMP_O_N O_SENSE_CLK O_REGEN_CLK O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB
+ VDD 0 FE_O_P FE_O_N @O_SENSE_BOOST@ cml_to_cmos_pex
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
    if routed_front_parent:
        downstream = replace_once(
            downstream,
            "XFE_E SAMP_E_P SAMP_E_N E_SENSE_CLK E_REGEN_CLK E_REGEN_CLKB E_CAPTURE_CLK E_CAPTURE_CLKB\n"
            "+ VDD 0 FE_E_P FE_E_N @E_SENSE_BOOST@ cml_to_cmos_pex\n"
            "XFE_O SAMP_O_P SAMP_O_N O_SENSE_CLK O_REGEN_CLK O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB\n"
            "+ VDD 0 FE_O_P FE_O_N @O_SENSE_BOOST@ cml_to_cmos_pex\n",
            "",
            "converter instances",
        )
    if routed_capture_parent:
        downstream = replace_once(
            downstream,
            "XCAP FE_E_P FE_E_N FE_O_P FE_O_N\n"
            "+ E_CAPTURE_CLK E_CAPTURE_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB VDD 0\n"
            "+ EVEN_Q EVEN_QB ODD_Q ODD_QB deserializer_split_capture_pex\n",
            "",
            "capture instance",
        )
    template = template.replace("\n.control\n", downstream + "\n.control\n")
    template = template.replace(
        "let odd_diff = v(SAMP_O_P)-v(SAMP_O_N)",
        "let odd_diff = v(SAMP_O_P)-v(SAMP_O_N)\n"
        "let even_cm = (v(SAMP_E_P)+v(SAMP_E_N))/2\n"
        "let odd_cm = (v(SAMP_O_P)+v(SAMP_O_N))/2\n"
        "let fe_even_diff = v(FE_E_P)-v(FE_E_N)\n"
        "let fe_odd_diff = v(FE_O_P)-v(FE_O_N)\n"
        "let fe_even_cm = (v(FE_E_P)+v(FE_E_N))/2\n"
        "let fe_odd_cm = (v(FE_O_P)+v(FE_O_N))/2\n"
        "let q_even_diff = v(EVEN_Q)-v(EVEN_QB)\n"
        "let q_odd_diff = v(ODD_Q)-v(ODD_QB)",
    )
    if routed_rx_regenerative_capture:
        template = replace_once(
            template,
            "let even_diff = v(SAMP_E_P)-v(SAMP_E_N)\n"
            "let odd_diff = v(SAMP_O_P)-v(SAMP_O_N)\n"
            "let even_cm = (v(SAMP_E_P)+v(SAMP_E_N))/2\n"
            "let odd_cm = (v(SAMP_O_P)+v(SAMP_O_N))/2",
            "let even_diff = v(RXOP)-v(RXON)\n"
            "let odd_diff = v(RXOP)-v(RXON)\n"
            "let even_cm = (v(RXOP)+v(RXON))/2\n"
            "let odd_cm = (v(RXOP)+v(RXON))/2",
            "regenerative parent probes",
        )
    if args.diagnostic_direct_regenerative_sampler:
        template = replace_once(
            template,
            "let even_diff = v(SAMP_E_P)-v(SAMP_E_N)\n"
            "let odd_diff = v(SAMP_O_P)-v(SAMP_O_N)\n"
            "let even_cm = (v(SAMP_E_P)+v(SAMP_E_N))/2\n"
            "let odd_cm = (v(SAMP_O_P)+v(SAMP_O_N))/2",
            "let even_diff = v(RX_RAWP)-v(RX_RAWN)\n"
            "let odd_diff = v(RX_RAWP)-v(RX_RAWN)\n"
            "let even_cm = (v(RX_RAWP)+v(RX_RAWN))/2\n"
            "let odd_cm = (v(RX_RAWP)+v(RX_RAWN))/2",
            "direct regenerative sampler probes",
        )
    scored_stages = ("tx", "pin", "rx", "rest", "samp", "fe", "q") \
        if args.restorer_mode != "none" else ("tx", "pin", "rx", "samp", "fe", "q")
    expected_scalars = len(pair_indices) * (len(scored_stages) * 2 + 2) + 4 \
        + (len(pair_indices) * 2 + 1 if args.restorer_mode != "none" else 0)
    expected_scalars += len(pair_indices) * 4
    expected_scalars += len(pair_indices) * 2 * len(SAMPLER_SETUP_PS)
    if routed_rx_pi_capture:
        expected_scalars += 2
    pex_paths = {"tx_pex": args.tx_pex}
    if not routed_capture_parent:
        pex_paths["deserializer_pex"] = args.deserializer_pex
    if routed_rx_pi_capture:
        pex_paths["rx_pi_capture_parent_pex"] = args.rx_pi_capture_parent_pex
        if rx_pi_include != args.rx_pi_capture_parent_pex:
            pex_paths["diagnostic_rx_pi_capture_parent_pex"] = rx_pi_include
    elif routed_rx_regenerative_capture:
        pex_paths["rx_regenerative_capture_parent_pex"] = (
            args.rx_regenerative_capture_parent_pex)
    elif routed_rx_capture:
        pex_paths["rx_capture_parent_pex"] = args.rx_capture_parent_pex
    elif routed_rx_frontend:
        pex_paths["rx_frontend_parent_pex"] = args.rx_frontend_parent_pex
    else:
        pex_paths.update({"termination_pex": args.term_pex,
                          "frontend_pex": args.frontend_pex})
    if routed_rx_spine:
        pex_paths["rx_spine_pex"] = args.rx_spine_pex
    elif not routed_front_parent:
        pex_paths.update({"rx_pex": args.rx_pex, "sampler_pex": args.sampler_pex})
    if args.restorer_mode != "none" and not routed_rx:
        pex_paths["restorer_pex"] = args.restorer_pex
    physical_paths = {}
    if not routed_capture_parent:
        physical_paths["deserializer_split"] = args.deserializer_physical
    if args.tx_physical is not None:
        physical_paths["tx"] = args.tx_physical
    if args.term_physical is not None and not routed_front_parent:
        physical_paths["termination"] = args.term_physical
    if args.frontend_physical is not None and not routed_front_parent:
        physical_paths["frontend"] = args.frontend_physical
    if routed_rx_spine:
        physical_paths["rx_spine"] = args.rx_spine_physical
    elif routed_rx_pi_capture:
        physical_paths["rx_pi_capture_parent"] = args.rx_pi_capture_parent_physical
    elif routed_rx_regenerative_capture:
        physical_paths["rx_regenerative_capture_parent"] = (
            args.rx_regenerative_capture_parent_physical)
    elif routed_rx_capture:
        physical_paths["rx_capture_parent"] = args.rx_capture_parent_physical
    elif routed_rx_frontend:
        physical_paths["rx_frontend_parent"] = args.rx_frontend_parent_physical
    elif args.base_physical is not None:
        physical_paths["base_lane"] = args.base_physical
    if args.restorer_mode != "none" and not routed_rx:
        physical_paths["restorer"] = args.restorer_physical
    if not routed_capture_parent:
        deserializer_physical = json.loads(args.deserializer_physical.read_text())
        deserializer_pex_hash = spine.sha256(args.deserializer_pex)
        if (deserializer_physical.get("result") != "pass"
                or deserializer_physical.get("pex_sha256") != deserializer_pex_hash):
            raise SystemExit(
                "split-capture physical evidence does not bind exact simulation PEX")
    if args.tx_physical is not None:
        tx_physical = json.loads(args.tx_physical.read_text())
        if (tx_physical.get("result") != "pass"
                or tx_physical.get("pex_sha256") != spine.sha256(args.tx_pex)):
            raise SystemExit("TX physical evidence does not bind exact simulation PEX")
    if args.term_physical is not None and not routed_front_parent:
        term_physical = json.loads(args.term_physical.read_text())
        term_record = term_physical.get("cells", {}).get(
            "termination", term_physical)
        if (term_physical.get("result") != "pass"
                or term_record.get("drc_error_count") != 0
                or term_record.get("lvs_unique") is not True
                or term_record.get("pex_sha256") != spine.sha256(args.term_pex)):
            raise SystemExit(
                "termination physical evidence does not bind exact simulation PEX")
    if args.frontend_physical is not None and not routed_front_parent:
        frontend_physical = json.loads(args.frontend_physical.read_text())
        if (frontend_physical.get("result") != "pass"
                or frontend_physical.get("pex_sha256")
                != spine.sha256(args.frontend_pex)):
            raise SystemExit(
                "front-end physical evidence does not bind exact simulation PEX")
    if routed_rx_spine:
        rx_spine_physical = json.loads(args.rx_spine_physical.read_text())
        if (rx_spine_physical.get("result") != "pass"
                or rx_spine_physical.get("drc_error_count") != 0
                or rx_spine_physical.get("lvs_unique") is not True
                or rx_spine_physical.get("pex_sha256")
                != spine.sha256(args.rx_spine_pex)):
            raise SystemExit(
                "RX-spine physical evidence does not bind exact simulation PEX")
    elif routed_rx_pi_capture:
        rx_pi_capture_physical = json.loads(
            args.rx_pi_capture_parent_physical.read_text())
        if (rx_pi_capture_physical.get("result") != "pass"
                or rx_pi_capture_physical.get("drc_error_count") != 0
                or rx_pi_capture_physical.get("lvs_unique") is not True
                or rx_pi_capture_physical.get("pex_sha256")
                != spine.sha256(args.rx_pi_capture_parent_pex)):
            raise SystemExit(
                "RX-PI-capture physical evidence does not bind exact simulation PEX")
    elif routed_rx_regenerative_capture:
        physical = json.loads(
            args.rx_regenerative_capture_parent_physical.read_text())
        if (physical.get("result") != "pass"
                or physical.get("drc_error_count") != 0
                or physical.get("lvs_unique") is not True
                or physical.get("pex_sha256")
                != spine.sha256(args.rx_regenerative_capture_parent_pex)):
            raise SystemExit(
                "regenerative capture evidence does not bind exact PEX")
    elif routed_rx_capture:
        rx_capture_physical = json.loads(
            args.rx_capture_parent_physical.read_text())
        if (rx_capture_physical.get("result") != "pass"
                or rx_capture_physical.get("drc_error_count") != 0
                or rx_capture_physical.get("lvs_unique") is not True
                or rx_capture_physical.get("pex_sha256")
                != spine.sha256(args.rx_capture_parent_pex)):
            raise SystemExit(
                "RX-capture physical evidence does not bind exact simulation PEX")
    elif routed_rx_frontend:
        rx_frontend_physical = json.loads(
            args.rx_frontend_parent_physical.read_text())
        if (rx_frontend_physical.get("result") != "pass"
                or rx_frontend_physical.get("drc_error_count") != 0
                or rx_frontend_physical.get("lvs_unique") is not True
                or rx_frontend_physical.get("pex_sha256")
                != spine.sha256(args.rx_frontend_parent_pex)):
            raise SystemExit(
                "RX-front-end physical evidence does not bind exact simulation PEX")
    elif args.restorer_mode != "none":
        restorer_physical = json.loads(args.restorer_physical.read_text())
        if (restorer_physical.get("result") != "pass"
                or restorer_physical.get("pex_sha256") != spine.sha256(args.restorer_pex)):
            raise SystemExit("restorer physical evidence does not bind exact simulation PEX")
    if args.base_physical is not None:
        base_physical = json.loads(args.base_physical.read_text())
        expected = {
            "termination": spine.sha256(args.term_pex),
            "rx": spine.sha256(args.rx_pex),
            "sampler": spine.sha256(args.sampler_pex),
        }
        observed_hashes = {
            name: base_physical.get("cells", {}).get(name, {}).get("pex_sha256")
            for name in expected
        }
        if base_physical.get("result") != "pass" or observed_hashes != expected:
            raise SystemExit("base physical evidence does not bind exact simulation PEX")

    def simulate(offset_ps: int) -> dict[str, object]:
        even_base = (clock_delay + ui + 50e-12 * timing_scale
                     + offset_ps * 1e-12)
        odd_base = even_base + ui
        capture_delay = ((args.capture_delay_ps * 1e-12)
                         if args.capture_delay_ps is not None
                         else 550e-12 * timing_scale)
        odd_capture_width_ps = (args.odd_capture_width_ps
                                if args.odd_capture_width_ps is not None
                                else args.capture_width_ps)
        capture_close = (odd_base + capture_delay
                         + args.odd_capture_skew_ps * 1e-12
                         + odd_capture_width_ps * 1e-12)
        measures = []
        restorer_eye_shift = (((135.0 - args.sampler_phase) % 360.0)
                              / 360.0 * period
                              if args.restorer_mode != "none" else 0.0)
        stop_time = odd_base + (max(pair_indices) + 2) * period
        for pair in pair_indices:
            even_event = even_base + pair * period
            odd_event = odd_base + pair * period
            even_eye = clock_delay + (2 * pair + 0.5) * ui
            odd_eye = clock_delay + (2 * pair + 1.5) * ui
            qualification_delay = 750e-12 * timing_scale
            output_delay = (
                args.capture_output_delay_ps * 1e-12
                if args.capture_output_delay_ps is not None else
                1.28e-9 * timing_scale
                if args.serial_rate_gbd == 1.25 else 720e-12
            )
            rx_shift = (args.rx_window_start_ps * 1e-12
                        if args.restorer_mode != "none" else 0.0)
            even_write_mid = (even_event + capture_delay
                              + args.even_capture_skew_ps * 1e-12
                              + args.capture_width_ps * 0.5e-12)
            odd_write_mid = (odd_event + capture_delay
                             + args.odd_capture_skew_ps * 1e-12
                             + odd_capture_width_ps * 0.5e-12)
            measures.extend((
                f"meas tran tx_even_{pair} find tx_diff at={even_eye:.12g}",
                f"meas tran pin_even_{pair} find pin_diff at={even_eye:.12g}",
                f"meas tran rx_even_{pair} find rx_diff at={even_eye + rx_shift:.12g}",
                f"meas tran tx_odd_{pair} find tx_diff at={odd_eye:.12g}",
                f"meas tran pin_odd_{pair} find pin_diff at={odd_eye:.12g}",
                f"meas tran rx_odd_{pair} find rx_diff at={odd_eye + rx_shift:.12g}",
                f"meas tran samp_even_{pair} find even_diff at={even_event - 10e-12:.12g}",
                f"meas tran samp_odd_{pair} find odd_diff at={odd_event - 10e-12:.12g}",
                f"meas tran samp_even_cm_{pair} find even_cm at={even_event - 10e-12:.12g}",
                f"meas tran samp_odd_cm_{pair} find odd_cm at={odd_event - 10e-12:.12g}",
                f"meas tran fe_even_{pair} find fe_even_diff "
                f"at={even_event + qualification_delay + args.even_frontend_skew_ps * 1e-12:.12g}",
                f"meas tran fe_odd_{pair} find fe_odd_diff "
                f"at={odd_event + qualification_delay + args.odd_frontend_skew_ps * 1e-12:.12g}",
                f"meas tran fe_write_even_{pair} find fe_even_diff at={even_write_mid:.12g}",
                f"meas tran fe_write_odd_{pair} find fe_odd_diff at={odd_write_mid:.12g}",
                f"meas tran fe_write_even_cm_{pair} find fe_even_cm at={even_write_mid:.12g}",
                f"meas tran fe_write_odd_cm_{pair} find fe_odd_cm at={odd_write_mid:.12g}",
                f"meas tran q_even_{pair} find q_even_diff "
                f"at={even_event + output_delay + args.even_capture_skew_ps * 1e-12:.12g}",
                f"meas tran q_odd_{pair} find q_odd_diff at={odd_event + output_delay:.12g}",
            ))
            for setup_ps in SAMPLER_SETUP_PS:
                setup_tag = f"m{abs(setup_ps)}" if setup_ps < 0 else str(setup_ps)
                measures.extend((
                    f"meas tran samp_setup_{setup_tag}_even_{pair} find even_diff "
                    f"at={even_event + setup_ps * 1e-12:.12g}",
                    f"meas tran samp_setup_{setup_tag}_odd_{pair} find odd_diff "
                    f"at={odd_event + setup_ps * 1e-12:.12g}",
                ))
            if args.restorer_mode != "none":
                measures.extend((
                    f"meas tran rx_hold_even_{pair} find rx_diff "
                    f"at={even_eye + rx_shift + 50e-12:.12g}",
                    f"meas tran rx_hold_odd_{pair} find rx_diff "
                    f"at={odd_eye + rx_shift + 50e-12:.12g}",
                    f"meas tran rest_even_{pair} find rest_diff "
                    f"at={even_eye + restorer_eye_shift:.12g}",
                    f"meas tran rest_odd_{pair} find rest_diff "
                    f"at={odd_eye + restorer_eye_shift:.12g}",
                ))
        if routed_rx_pi_capture:
            measures.extend((
                "meas tran pi_clk_rise when v(PI_CLK_P)=v(PI_CLK_N) "
                "rise=1 td=4n",
                "meas tran pi_clk_fall when v(PI_CLK_P)=v(PI_CLK_N) "
                "fall=1 td=4n",
            ))
        term_sources = "\n".join(
            f"VTERM{index} TERM_EN{index}_N_SRC 0 "
            + ("0" if index < args.term_code else f"{args.vdd:.2f}")
            + f"\nRTERM{index} TERM_EN{index}_N_SRC TERM_EN{index}_N 1"
            for index in range(7)
        )
        values = {
            "TX_INCLUDE": f".include {args.tx_pex}",
            "TERM_INCLUDE": ("" if routed_front_parent
                             else f".include {args.term_pex}"),
            "RX_INCLUDE": (f".include {rx_pi_include}"
                           if routed_rx_pi_capture else
                           f".include {args.rx_regenerative_capture_parent_pex}"
                           if routed_rx_regenerative_capture else
                           f".include {args.rx_capture_parent_pex}"
                           if routed_rx_capture else
                           f".include {args.rx_frontend_parent_pex}"
                           if routed_rx_frontend else
                           f".include {args.rx_spine_pex}" if routed_rx_spine
                           else f".include {args.rx_pex}"),
            "SAMPLER_INCLUDE": (f".include {args.source / 'cdr' / 'cdr_sampler.spice'}"
                                if args.diagnostic_decision_retimer else "" if routed_rx
                                else f".include {args.sampler_pex}"),
            "RESTORER_INCLUDE": (f".include {args.restorer_pex}"
                                   if args.restorer_mode != "none"
                                   and not routed_rx else ""),
            "FRONTEND_INCLUDE": ("" if routed_front_parent
                                  else f".include {args.frontend_pex}"),
            "DESERIALIZER_INCLUDE": (
                "" if routed_capture_parent else f".include {args.deserializer_pex}"),
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
            "E_SENSE_BOOST": ("E_SENSE_CLK" if (args.frontend_tail_boost
                                                    or args.even_frontend_tail_boost)
                                else "SENSE_BOOST"),
            "O_SENSE_BOOST": ("O_SENSE_CLK" if (args.frontend_tail_boost
                                                    or args.odd_frontend_tail_boost)
                                else "SENSE_BOOST"),
            "TX_PAD_CAP": "300f", "RX_PAD_CAP": "500f", "AC_CAP": "100n",
            "AC_INITIAL_V": f"{(args.ac_initial_v if args.ac_initial_v is not None else args.vdd * 0.32):.6f}",
            "PACKAGE_R": "2", "PACKAGE_L": "1n", "BIAS_RETURN_R": "2k",
            "CHANNEL_HALF_R": f"{max(args.channel_series_ohm_per_leg / 2, 1e-3):.12g}",
            "CHANNEL_HALF_C": f"{max(args.channel_shunt_cap_f / 2, 1e-18):.12g}",
            "SAMPLE_CLOCK_CM": f"{args.vdd * 2 / 3:.6f}", "SAMPLE_CLOCK_PEAK": "0.45",
            "PI_INPUT_CM": f"{args.vdd * 0.5:.6f}",
            "PI_CTRL_A_V": f"{args.pi_control_a:.6f}",
            "PI_CTRL_B_V": f"{args.pi_control_b:.6f}",
            "PI_BUF_BIAS_V": f"{args.pi_buffer_bias:.6f}",
            "CLK_REST_BIAS_V": f"{args.clock_restorer_bias:.6f}",
            "PI_OUTPUT_CLOCK_OVERRIDE": (
                f"VPIOVRP PI_CLK_P_OVR 0 {differential_clock_pwl(args.vdd * 2 / 3, 0.45, rate / 2, 1e-9, args.sampler_phase, args.pi_output_edge_skew_ps * 1e-12, stop_time, False)}\n"
                f"VPIOVRN PI_CLK_N_OVR 0 {differential_clock_pwl(args.vdd * 2 / 3, 0.45, rate / 2, 1e-9, args.sampler_phase, args.pi_output_edge_skew_ps * 1e-12, stop_time, True)}\n"
                "RPIOVRP PI_CLK_P_OVR PI_CLK_P 1\n"
                "RPIOVRN PI_CLK_N_OVR PI_CLK_N 1"
                if args.pi_output_clock_override else ""
            ),
            "CLOCK_HZ": f"{rate / 2:.12g}",
            "CLOCK_PHASE": f"{args.sampler_phase:.3f}",
            "CLOCK_N_PHASE": f"{args.sampler_phase + 180:.3f}",
            "SENSE_WIDTH": f"{((args.frontend_sense_width_ps * 1e-12)
                                  if args.frontend_sense_width_ps is not None
                                  else 575e-12 * timing_scale):.12g}",
            "REGEN_WIDTH": f"{((args.frontend_sense_width_ps - 10) * 1e-12
                                  if args.frontend_sense_width_ps is not None
                                  else 565e-12 * timing_scale):.12g}",
            "O_SENSE_WIDTH": f"{((args.odd_frontend_sense_width_ps * 1e-12)
                                    if args.odd_frontend_sense_width_ps is not None
                                    else (args.frontend_sense_width_ps * 1e-12)
                                    if args.frontend_sense_width_ps is not None
                                    else 575e-12 * timing_scale):.12g}",
            "O_REGEN_WIDTH": f"{(((args.odd_frontend_sense_width_ps - 10) * 1e-12)
                                    if args.odd_frontend_sense_width_ps is not None
                                    else ((args.frontend_sense_width_ps - 10) * 1e-12)
                                    if args.frontend_sense_width_ps is not None
                                    else 565e-12 * timing_scale):.12g}",
            # The static CMOS write cell needs its characterized pulse width;
            # device delay does not scale with the serial unit interval.
            "CAPTURE_WIDTH": f"{args.capture_width_ps * 1e-12:.12g}",
            "O_CAPTURE_WIDTH": f"{odd_capture_width_ps * 1e-12:.12g}",
            "E_SENSE_DELAY": f"{even_base + args.even_frontend_skew_ps * 1e-12:.12g}",
            "E_REGEN_DELAY": f"{even_base + 10e-12 * timing_scale + args.even_frontend_skew_ps * 1e-12:.12g}",
            "E_CAPTURE_DELAY": f"{even_base + capture_delay + args.even_capture_skew_ps * 1e-12:.12g}",
            "O_SENSE_DELAY": f"{odd_base + args.odd_frontend_skew_ps * 1e-12:.12g}",
            "O_REGEN_DELAY": f"{odd_base + 10e-12 * timing_scale + args.odd_frontend_skew_ps * 1e-12:.12g}",
            "O_CAPTURE_DELAY": f"{odd_base + capture_delay + args.odd_capture_skew_ps * 1e-12:.12g}",
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
        hold_margins = {"even": [], "odd": []}
        for pair in pair_indices:
            input_signs = {"even": 1 if even_bits[pair] else -1,
                           "odd": 1 if odd_bits[pair] else -1}
            stage_signs = {}
            for stage, latency in (("samp", sampler_latency_ui),
                                   ("fe", frontend_latency_ui),
                                   ("q", capture_latency_ui)):
                stage_signs[stage] = {
                    "even": 1 if bits[2 * pair - latency] else -1,
                    "odd": 1 if bits[2 * pair + 1 - latency] else -1,
                }
            for stage in scored_stages:
                for lane_name in ("even", "odd"):
                    key = f"{stage}_{lane_name}"
                    signs = stage_signs.get(stage, input_signs)
                    margins[key].append(observed.get(f"{key}_{pair}", 0.0)
                                        * signs[lane_name])
            if args.restorer_mode != "none":
                for lane_name in ("even", "odd"):
                    hold_margins[lane_name].append(
                        observed.get(f"rx_hold_{lane_name}_{pair}", 0.0)
                        * input_signs[lane_name]
                    )
        minima = {name: min(values_) for name, values_ in margins.items()}
        hold_minima = {name: min(values_) for name, values_ in hold_margins.items()} \
            if args.restorer_mode != "none" else {}
        complete = return_code == 0 and len(observed) == expected_scalars
        sampler_common_modes = [
            observed.get(f"samp_{lane_name}_cm_{pair}", 0.0)
            for pair in pair_indices for lane_name in ("even", "odd")
        ]
        sampler_magnitudes = [
            abs(observed.get(f"samp_{lane_name}_{pair}", 0.0))
            for pair in pair_indices for lane_name in ("even", "odd")
        ]
        sampler_setup_scan = []
        for setup_ps in SAMPLER_SETUP_PS:
            setup_tag = f"m{abs(setup_ps)}" if setup_ps < 0 else str(setup_ps)
            signed_setup = []
            for pair in pair_indices:
                signed_setup.extend((
                    observed[f"samp_setup_{setup_tag}_even_{pair}"]
                    * (1 if bits[2 * pair - sampler_latency_ui] else -1),
                    observed[f"samp_setup_{setup_tag}_odd_{pair}"]
                    * (1 if bits[2 * pair + 1 - sampler_latency_ui] else -1),
                ))
            sampler_setup_scan.append({
                "setup_ps": setup_ps,
                "minimum_signed_v": min(signed_setup),
                "minimum_magnitude_v": min(abs(value) for value in signed_setup),
            })
        frontend_write_common_modes = [
            observed.get(f"fe_write_{lane_name}_cm_{pair}", 0.0)
            for pair in pair_indices for lane_name in ("even", "odd")
        ]
        current = observed.get("supply_current", 0.0)
        # Without a restorer, RXOP/RXON is the sampler contract and retains the
        # original 80 mV signed floor.  With a physical limiter inserted it is
        # an internal small-signal boundary; require 40 mV polarity there and
        # independently require 200 mV at the actual sampler input.
        rx_floor = 0.04 if args.restorer_mode != "none" else 0.08
        passed = (complete and min(minima["tx_even"], minima["tx_odd"]) >= 0.05
                  and min(minima["pin_even"], minima["pin_odd"]) >= 0.10
                  and (routed_rx_regenerative_capture
                       or args.diagnostic_rx_single_stage
                       or min(minima["rx_even"], minima["rx_odd"]) >= rx_floor)
                  and (args.diagnostic_rx_single_stage
                       or args.restorer_mode == "none"
                       or min(hold_minima["even"], hold_minima["odd"]) >= rx_floor)
                  and (args.diagnostic_rx_single_stage
                       or args.restorer_mode == "none"
                       or args.diagnostic_restorer_bypass
                       or args.diagnostic_direct_regenerative_sampler
                       or min(minima["rest_even"], minima["rest_odd"]) >= 0.20)
                  # Restorer and sampler probes are dynamic internal states,
                  # not the final pipeline latency. Their scan stays visible;
                  # converter qualification/write and held output own polarity.
                  and (not routed_rx_regenerative_capture
                       or min(minima["samp_even"], minima["samp_odd"]) >= 0.04)
                  and min(sampler_common_modes) >= 0.50
                  # This clocked, capacitively kicked node can approach the
                  # rail. Bound absolute overshoot rather than impose DC
                  # headroom that the sampler output does not need.
                  and max(sampler_common_modes)
                  <= args.vdd + args.sampler_overshoot_limit_mv * 1e-3
                  and min(minima["fe_even"], minima["fe_odd"]) >= 0.30
                  and min(
                      min(observed[f"fe_write_even_{pair}"]
                          * (1 if bits[2 * pair - frontend_write_latency_ui]
                             else -1)
                          for pair in pair_indices),
                      min(observed[f"fe_write_odd_{pair}"]
                          * (1 if bits[2 * pair + 1
                                      - frontend_write_latency_ui] else -1)
                          for pair in pair_indices)) >= 0.30
                  and min(minima["q_even"], minima["q_odd"]) >= 0.50
                  and args.vdd * 0.5 - 0.25 <= observed.get("rx_cm_avg", 0.0)
                  <= args.vdd * 0.5 + 0.25
                  and (args.diagnostic_rx_single_stage
                       or 0.50 <= observed.get("amp_cm_avg", 0.0) <= args.vdd - 0.10)
                  and (args.diagnostic_rx_single_stage
                       or args.restorer_mode == "none"
                       or args.diagnostic_direct_regenerative_sampler
                       or 0.50 <= observed.get("rest_cm_avg", 0.0) <= args.vdd - 0.10)
                  and 0.010 <= current <= (0.075 if routed_rx_pi_capture else 0.060))
        result = {
            "id": case_id, "conversion_offset_s": offset_ps * 1e-12,
            "capture_close_s": capture_close, "complete": complete,
            "minimum_tx_even_v": minima["tx_even"],
            "minimum_tx_odd_v": minima["tx_odd"],
            "minimum_pin_even_v": minima["pin_even"],
            "minimum_pin_odd_v": minima["pin_odd"],
            "minimum_rx_even_v": minima["rx_even"],
            "minimum_rx_odd_v": minima["rx_odd"],
            "minimum_sampler_even_v": minima["samp_even"],
            "minimum_sampler_odd_v": minima["samp_odd"],
            "minimum_sampler_observed_magnitude_v": min(sampler_magnitudes),
            "sampler_setup_scan": sampler_setup_scan,
            "sampler_common_mode_min_v": min(sampler_common_modes),
            "sampler_common_mode_max_v": max(sampler_common_modes),
            "sampler_supply_overshoot_max_v": max(
                0.0, max(sampler_common_modes) - args.vdd),
            "minimum_frontend_even_v": minima["fe_even"],
            "minimum_frontend_odd_v": minima["fe_odd"],
            "minimum_frontend_write_even_v": min(
                observed[f"fe_write_even_{pair}"]
                * (1 if bits[2 * pair - frontend_write_latency_ui] else -1)
                for pair in pair_indices),
            "minimum_frontend_write_odd_v": min(
                observed[f"fe_write_odd_{pair}"]
                * (1 if bits[2 * pair + 1 - frontend_write_latency_ui] else -1)
                for pair in pair_indices),
            "frontend_write_common_mode_min_v": min(frontend_write_common_modes),
            "frontend_write_common_mode_max_v": max(frontend_write_common_modes),
            "minimum_capture_even_v": minima["q_even"],
            "minimum_capture_odd_v": minima["q_odd"],
            "rx_common_mode_v": observed.get("rx_cm_avg"),
            "tx_common_mode_v": observed.get("tx_cm_avg"),
            "amplifier_common_mode_v": observed.get("amp_cm_avg"),
            "supply_current_a": current,
            "observed_scalar_count": len(observed),
            "expected_scalar_count": expected_scalars,
            "result": "pass" if passed else "fail",
        }
        if routed_rx_pi_capture:
            result.update({
                "pi_clock_rise_s": observed.get("pi_clk_rise"),
                "pi_clock_fall_s": observed.get("pi_clk_fall"),
            })
        if args.restorer_mode != "none":
            result.update({
            "minimum_restored_even_v": minima["rest_even"],
                "minimum_restored_odd_v": minima["rest_odd"],
                "minimum_rx_hold_even_v": hold_minima["even"],
                "minimum_rx_hold_odd_v": hold_minima["odd"],
                "restored_common_mode_v": observed.get("rest_cm_avg"),
            })
        alignment_scan = []
        for latency in range(-3, 4):
            for swap_lanes in (False, True):
                stage_minima = {}
                for stage in ("samp", "fe", "q"):
                    signed_by_lane = {"even": [], "odd": []}
                    for pair in pair_indices:
                        even_sign = 1 if bits[2 * pair - latency] else -1
                        odd_sign = 1 if bits[2 * pair + 1 - latency] else -1
                        if swap_lanes:
                            even_sign, odd_sign = odd_sign, even_sign
                        signed_by_lane["even"].append(
                            observed.get(f"{stage}_even_{pair}", 0.0) * even_sign)
                        signed_by_lane["odd"].append(
                            observed.get(f"{stage}_odd_{pair}", 0.0) * odd_sign)
                    stage_minima[stage] = {
                        lane_name: min(lane_values)
                        for lane_name, lane_values in signed_by_lane.items()
                    }
                alignment_scan.append({
                    "latency_ui": latency,
                    "swap_lanes": swap_lanes,
                    "minimum_sampler_v": min(stage_minima["samp"].values()),
                    "minimum_sampler_even_v": stage_minima["samp"]["even"],
                    "minimum_sampler_odd_v": stage_minima["samp"]["odd"],
                    "minimum_frontend_v": min(stage_minima["fe"].values()),
                    "minimum_frontend_even_v": stage_minima["fe"]["even"],
                    "minimum_frontend_odd_v": stage_minima["fe"]["odd"],
                    "minimum_capture_v": min(stage_minima["q"].values()),
                    "minimum_capture_even_v": stage_minima["q"]["even"],
                    "minimum_capture_odd_v": stage_minima["q"]["odd"],
                })
        result["alignment_scan"] = alignment_scan
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        cases = list(executor.map(simulate, offsets))
    passing = [case for case in cases if case["result"] == "pass"]
    selected = max(passing, key=lambda case: min(case["minimum_capture_even_v"],
                                                  case["minimum_capture_odd_v"])) if passing else None
    result = {
        "schema_version": 1,
        "evidence_class": ("diagnostic_modified_pex"
                           if args.diagnostic_sampler_load_scale != 1.0
                           or args.diagnostic_sampler_hold_scale != 1
                           or args.diagnostic_decision_retimer
                           or args.diagnostic_restorer_load_length_um != 4.2
                           or args.diagnostic_restorer_bypass
                           or args.diagnostic_rx_single_stage
                           or args.diagnostic_direct_regenerative_sampler
                           else "diagnostic_fixture"
                           if args.pi_output_clock_override
                           or args.sampler_observation_load_ff != 25.0
                           else "exact_pex"),
        "claim": ("extracted_1p25_gbd_lane_dual_cmos_capture"
                  if args.serial_rate_gbd == 1.25 else
                  "extracted_2p5_gts_lane_dual_cmos_capture"),
        "case_id": args.case_id,
        "environment": [args.mos_corner, args.res_corner, args.vdd, args.temperature, 0.5],
        "controls": {"sampler_phase_deg": args.sampler_phase, "tx_bias_v": args.tx_bias,
                     "pi_control_a_v": (args.pi_control_a
                                          if routed_rx_pi_capture else None),
                     "pi_control_b_v": (args.pi_control_b
                                          if routed_rx_pi_capture else None),
                     "pi_buffer_bias_v": (args.pi_buffer_bias
                                            if routed_rx_pi_capture else None),
                     "clock_restorer_bias_v": (args.clock_restorer_bias
                                                 if routed_rx_pi_capture else None),
                     "pi_input_phase_deg": (args.pi_input_phase_deg
                                              if routed_rx_pi_capture else None),
                     "pi_input_polarity_inverted": (args.pi_invert
                                                       if routed_rx_pi_capture else None),
                     "pi_output_clock_override": (args.pi_output_clock_override
                                                     if routed_rx_pi_capture else None),
                     "pi_output_edge_skew_ps": (args.pi_output_edge_skew_ps
                                                   if routed_rx_pi_capture else None),
                     "diagnostic_sampler_load_scale": (
                         args.diagnostic_sampler_load_scale
                         if routed_rx_pi_capture else None),
                     "diagnostic_sampler_hold_scale": (
                         args.diagnostic_sampler_hold_scale
                         if routed_rx_pi_capture else None),
                     "diagnostic_decision_retimer": (
                         args.diagnostic_decision_retimer
                         if routed_rx_pi_capture else None),
                     "diagnostic_restorer_load_length_um": (
                         args.diagnostic_restorer_load_length_um
                         if routed_rx_pi_capture else None),
                     "diagnostic_restorer_bypass": (
                         args.diagnostic_restorer_bypass
                         if routed_rx_pi_capture else None),
                     "diagnostic_rx_single_stage": (
                         args.diagnostic_rx_single_stage
                         if routed_rx_pi_capture else None),
                     "diagnostic_direct_regenerative_sampler": (
                         args.diagnostic_direct_regenerative_sampler
                         if routed_rx_pi_capture else None),
                     "sampler_observation_load_ff":
                         args.sampler_observation_load_ff,
                     "tx_load_code": args.tx_load_code,
                     "capture_width_ps": args.capture_width_ps,
                     "odd_capture_width_ps": args.odd_capture_width_ps,
                     "capture_delay_ps": args.capture_delay_ps,
                     "capture_output_delay_ps": args.capture_output_delay_ps,
                     "even_capture_skew_ps": args.even_capture_skew_ps,
                     "odd_capture_skew_ps": args.odd_capture_skew_ps,
                     "frontend_sense_width_ps": args.frontend_sense_width_ps,
                     "odd_frontend_sense_width_ps":
                         args.odd_frontend_sense_width_ps,
                     "even_frontend_skew_ps": args.even_frontend_skew_ps,
                     "odd_frontend_skew_ps": args.odd_frontend_skew_ps,
                     "rx_bias_v": args.rx_bias, "sampler_bias_v": args.sampler_bias,
                     "termination_code": args.term_code,
                     "rx_bandwidth_mode": args.rx_bandwidth_mode,
                     "restorer_mode": args.restorer_mode,
                     "restorer_cell": args.restorer_cell,
                     "frontend_tail_boost": args.frontend_tail_boost,
                     "even_frontend_tail_boost":
                         args.even_frontend_tail_boost,
                     "odd_frontend_tail_boost": args.odd_frontend_tail_boost,
                     "latency_ui": args.latency_ui,
                     "sampler_latency_ui": sampler_latency_ui,
                     "frontend_latency_ui": frontend_latency_ui,
                     "frontend_write_latency_ui": frontend_write_latency_ui,
                     "capture_latency_ui": capture_latency_ui,
                     "rx_window_start_ps": args.rx_window_start_ps,
                     "restorer_bias_v": (args.restorer_bias
                                          if args.restorer_mode != "none" else None)},
        "physical_composition": (
            "diagnostic_modified_sampler_boundary_parent"
            if routed_rx_pi_capture and (args.diagnostic_sampler_load_scale != 1.0
                                         or args.diagnostic_sampler_hold_scale != 1
                                         or args.diagnostic_decision_retimer
                                         or args.diagnostic_restorer_load_length_um
                                         != 4.2
                                         or args.diagnostic_restorer_bypass
                                         or args.diagnostic_rx_single_stage
                                         or args.diagnostic_direct_regenerative_sampler) else
            "routed_phase_interpolator_termination_rx_dual_capture_parent"
            if routed_rx_pi_capture else
            "routed_termination_rx_dual_regenerative_sampler_capture_parent"
            if routed_rx_regenerative_capture else
            "routed_termination_rx_spine_dual_converter_capture_parent"
            if routed_rx_capture else
            "routed_termination_rx_spine_dual_converter_parent"
            if routed_rx_frontend else
            "routed_rx_restorer_sampler_parent"
            if routed_rx_spine else "ideal_wire_leaf_stack"),
        "stimulus": {
            "pattern": args.pattern, "bit_count": len(bits),
            "serial_rate_hz": rate,
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
        "acceptance_limits": {
            "sampler_supply_overshoot_max_v":
                args.sampler_overshoot_limit_mv * 1e-3,
        },
        "fixture_initialization": {
            "ac_coupling_initial_voltage_v": (
                args.ac_initial_v if args.ac_initial_v is not None
                else args.vdd * 0.32
            ),
            "note": "settled TX-to-RX common-mode difference; not a hardware trim",
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
