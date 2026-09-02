#!/usr/bin/env python3
"""Compile the selected local sampler/capture clock fanout schematic."""

from __future__ import annotations

import argparse
from pathlib import Path


TOP = "local_clock_fanout"
SOURCE_REVISION = "local_clock_fanout_v8_sampler_clkb_8_24_32_p32_capture4_8"


def compile_source() -> str:
    branches = []
    for phase, clock, clockb in (("E", "CLKP_H", "CLKP_HB"),
                                  ("O", "CLKN_H", "CLKN_HB")):
        branches.extend([
            f"X{phase}S {clockb} {phase}_SENSE VDD VSS clock_fanout_sampler",
            f"X{phase}C {clock} {phase}_CAPTURE_CLK VDD VSS clock_fanout_buffer PRE=4 OUT=8",
            f"X{phase}CB {clockb} {phase}_CAPTURE_CLKB VDD VSS clock_fanout_buffer PRE=4 OUT=8",
        ])
    return f"""* SPDX-License-Identifier: Apache-2.0
* source_revision: {SOURCE_REVISION}
.subckt cp_inv A Y VDD VSS params: MP=1 MN=1
XP Y A VDD VDD pfet_03v3 w=8u l=0.28u m={{MP}}
XN Y A VSS VSS nfet_03v3 w=8u l=0.28u m={{MN}}
.ends cp_inv

.subckt clock_fanout_buffer A Y VDD VSS params: PRE=4 OUT=8
XI0 A B VDD VSS cp_inv MP={{PRE}} MN={{PRE}}
XI1 B Y VDD VSS cp_inv MP={{OUT}} MN={{OUT}}
.ends clock_fanout_buffer

.subckt clock_fanout_sampler A Y VDD VSS
XI0 A B0 VDD VSS cp_inv MP=8 MN=8
XI1 B0 B1 VDD VSS cp_inv MP=24 MN=24
XI2 B1 Y VDD VSS cp_inv MP=32 MN=32
.ends clock_fanout_sampler

.subckt {TOP} CLKP_H CLKP_HB CLKN_H CLKN_HB VDD VSS
+ E_SENSE E_CAPTURE_CLK E_CAPTURE_CLKB
+ O_SENSE O_CAPTURE_CLK O_CAPTURE_CLKB
{chr(10).join(branches)}
.ends {TOP}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(compile_source())


if __name__ == "__main__":
    main()
