#!/usr/bin/env python3
"""Compile namespace-safe transistor intent for the routed PCIe RX event parent."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
SERDES = HERE.parent
sys.path.insert(0, str(SERDES))
from spice_namespace import namespace_source, resolve_includes  # noqa: E402


TOP = "event_lane_routed_parent"
EVENT_TOP = "retimed_event_capture_bridge"
FANOUT_TOP = "local_clock_fanout"
LANE_TOP = "lane_rx_regenerative_capture"


def compile_source() -> str:
    event, _ = namespace_source(
        (SERDES / "clock_pulse_hclk_window_probe/event_capture_physical.spice").read_text(),
        "event", {EVENT_TOP})
    fanout, _ = namespace_source(
        (SERDES / "clock_pulse_hclk_window_probe/local_clock_fanout.spice").read_text(),
        "fanout", {FANOUT_TOP})
    lane_closure = resolve_includes(
        SERDES / "lane_rx_regenerative_capture/lane_rx_regenerative_capture.spice",
        SERDES)
    lane, _ = namespace_source(lane_closure, "lane", {LANE_TOP})
    converter, _ = namespace_source(
        (SERDES / "reference_level_receiver/reference_level_receiver.spice").read_text(),
        "event_level", {"reference_level_receiver"})
    parent = f"""
* Namespace-safe composed transistor intent. Regenerative and BOOST controls
* remain explicit so package-level calibration or static straps are realizable.
.subckt {TOP} CLKP_H CLKN_H SEL0 SEL1 SEL2 RXP RXN
+ TERM_EN0_N TERM_EN1_N TERM_EN2_N TERM_EN3_N TERM_EN4_N TERM_EN5_N TERM_EN6_N
+ VTHP VTHN RX_BIAS LEVEL_BIAS LEVEL_REF RX_BW_EN_N E_REGEN_CLK E_REGEN_CLKB E_SENSE_BOOST
+ O_REGEN_CLK O_REGEN_CLKB O_SENSE_BOOST VDD VSS
+ RX_RAWP RX_RAWN FE_E_P FE_E_N FE_O_P FE_O_N EVEN_Q EVEN_QB ODD_Q ODD_QB
XEVENT CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD VSS
+ E_EVENT_SENSE E_EVENT_BOOST E_CLK E_CLKB
+ O_EVENT_SENSE O_EVENT_BOOST O_CLK O_CLKB {EVENT_TOP}
XFANOUT E_CLK E_CLKB O_CLK O_CLKB VDD VSS
+ E_SENSE_PRE E_CAPTURE_CLK_PRE E_CAPTURE_CLKB_PRE
+ O_SENSE_PRE O_CAPTURE_CLK_PRE O_CAPTURE_CLKB_PRE {FANOUT_TOP}
* Each independently timed weak node is compared with an explicit reference;
* complementary outputs are generated locally rather than assumed upstream.
XLEVEL_SE E_SENSE_PRE LEVEL_REF LEVEL_BIAS VDD VSS
+ E_SENSE E_SENSE_UNUSED reference_level_receiver
XLEVEL_SO O_SENSE_PRE LEVEL_REF LEVEL_BIAS VDD VSS
+ O_SENSE O_SENSE_UNUSED reference_level_receiver
XLEVEL_E E_CAPTURE_CLK_PRE LEVEL_REF LEVEL_BIAS VDD VSS
+ E_CAPTURE_CLK E_CAPTURE_CLKB reference_level_receiver
XLEVEL_O O_CAPTURE_CLK_PRE LEVEL_REF LEVEL_BIAS VDD VSS
+ O_CAPTURE_CLK O_CAPTURE_CLKB reference_level_receiver
XLANE RXP RXN TERM_EN0_N TERM_EN1_N TERM_EN2_N TERM_EN3_N TERM_EN4_N
+ TERM_EN5_N TERM_EN6_N VTHP VTHN RX_BIAS RX_BW_EN_N
+ E_SENSE E_REGEN_CLK E_REGEN_CLKB E_CAPTURE_CLK E_CAPTURE_CLKB E_SENSE_BOOST
+ O_SENSE O_REGEN_CLK O_REGEN_CLKB O_CAPTURE_CLK O_CAPTURE_CLKB O_SENSE_BOOST
+ VDD VSS RX_RAWP RX_RAWN FE_E_P FE_E_N FE_O_P FE_O_N
+ EVEN_Q EVEN_QB ODD_Q ODD_QB {LANE_TOP}
.ends {TOP}
"""
    return ("* SPDX-License-Identifier: Apache-2.0\n" + event + fanout + lane
            + converter + parent)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(compile_source())


if __name__ == "__main__":
    main()
