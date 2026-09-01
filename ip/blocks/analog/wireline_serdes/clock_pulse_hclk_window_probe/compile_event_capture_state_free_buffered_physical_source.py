#!/usr/bin/env python3
"""Lower the state-free event source with physical lane-interface buffers."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_state_free as state_free
import compile_event_capture_state_free_physical_source as base


TOP = base.TOP
SOURCE_REVISION = state_free.SOURCE_REVISION + "_physical_lane_interface_v4"

BUFFER = """
.subckt cp_lane_if_buffer SENSE_IN BOOST_IN CLK_IN CLKB_IN
+ SENSE BOOST CLK CLKB VDD VSS
* Two-stage logical-effort taper preserves the short pulse. Compared with v1,
* it reduces source gate width by 25% and predriver load by 37.5%.
XSENSEIF0 SENSE_IN SENSE_B VDD VSS cp_inv WP=8u WN=8u MP=4 MN=2
XSENSEIF1 SENSE_B SENSE VDD VSS cp_inv WP=8u WN=8u MP=8 MN=12
XBOOSTIF0 BOOST_IN BOOST_B VDD VSS cp_inv WP=8u WN=8u MP=4 MN=4
XBOOSTIF1 BOOST_B BOOST VDD VSS cp_inv WP=8u WN=8u MP=16 MN=16
XWCLKIF0 CLK_IN CLK_B VDD VSS cp_inv WP=8u WN=8u MP=4 MN=2
XWCLKIF1 CLK_B CLK VDD VSS cp_inv WP=8u WN=8u MP=8 MN=12
XWCLKBIF0 CLKB_IN CLKB_B VDD VSS cp_inv WP=8u WN=8u MP=4 MN=4
XWCLKBIF1 CLKB_B CLKB VDD VSS cp_inv WP=8u WN=8u MP=16 MN=16
.ends cp_lane_if_buffer
"""


def compile_source() -> str:
    source = base.compile_source()
    top = """.subckt retimed_event_capture_bridge CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD VSS
+ E_SENSE E_BOOST E_CAPTURE_CLK E_CAPTURE_CLKB
+ O_SENSE O_BOOST O_CAPTURE_CLK O_CAPTURE_CLKB
* SEL0=SENSE assist, SEL1=event interval, SEL2=event epoch.
XE CLKP_H SEL0 SEL1 SEL2 VDD VSS
+ E_SENSE E_BOOST E_CAPTURE_CLK E_CAPTURE_CLKB sense_write_phase
XO CLKN_H SEL0 SEL1 SEL2 VDD VSS
+ O_SENSE O_BOOST O_CAPTURE_CLK O_CAPTURE_CLKB sense_write_phase
.ends retimed_event_capture_bridge
"""
    if source.count(top) != 1:
        raise ValueError("state-free buffered lowering lost its top boundary")
    buffered_top = """.subckt retimed_event_capture_bridge CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD VSS
+ E_SENSE E_BOOST E_CAPTURE_CLK E_CAPTURE_CLKB
+ O_SENSE O_BOOST O_CAPTURE_CLK O_CAPTURE_CLKB
* SEL0=SENSE assist, SEL1=event interval, SEL2=event epoch.
XE CLKP_H SEL0 SEL1 SEL2 VDD VSS
+ E_SENSE_SRC E_BOOST_SRC E_CAPTURE_CLK_SRC E_CAPTURE_CLKB_SRC sense_write_phase
XO CLKN_H SEL0 SEL1 SEL2 VDD VSS
+ O_SENSE_SRC O_BOOST_SRC O_CAPTURE_CLK_SRC O_CAPTURE_CLKB_SRC sense_write_phase
XE_IF E_SENSE_SRC E_BOOST_SRC E_CAPTURE_CLK_SRC E_CAPTURE_CLKB_SRC
+ E_SENSE E_BOOST E_CAPTURE_CLK E_CAPTURE_CLKB VDD VSS cp_lane_if_buffer
XO_IF O_SENSE_SRC O_BOOST_SRC O_CAPTURE_CLK_SRC O_CAPTURE_CLKB_SRC
+ O_SENSE O_BOOST O_CAPTURE_CLK O_CAPTURE_CLKB VDD VSS cp_lane_if_buffer
.ends retimed_event_capture_bridge
"""
    return source.replace(top, BUFFER + "\n" + buffered_top, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = compile_source()
    args.output.write_text(source)
    print(f"top={TOP} source_revision={SOURCE_REVISION} "
          f"schematic_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
