#!/usr/bin/env python3
"""Generate a local direct-write SENSE latch from full-duty START/END."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_state_free_physical_source as base
import compile_event_capture_state_free_buffered_physical_source as buffered


TOP = base.TOP
SOURCE_REVISION = "retimed_capture_start_end_direct_write_sr_v3_two_stage"

PRIMITIVE = """
.subckt cp_sense_direct_write_sr START END SENSE VDD VSS params: LM=1 WM=4 LPW=4u PRE=4 OUT=8
* START and END are full-duty states. Their local complements create two
* non-overlapping write conditions, but no narrow pulse becomes a routed net.
XIS START STARTB VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2
XIE END ENDB VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2
* Weak cross-coupled static storage. SET writes QB low while STARTB&END are
* high; RESET writes Q low while START&ENDB are high. Each branch is physically
* local to the state node it writes.
XQ QB Q VDD VSS cp_inv WP={LPW} WN=4u MP={LM} MN={LM}
XQB Q QB VDD VSS cp_inv WP={LPW} WN=4u MP={LM} MN={LM}
XSET QB STARTB END VSS cp_cond_npd_comp W=8u M={WM}
XRESET Q START ENDB VSS cp_cond_npd_comp W=8u M={WM}
* Minimal polarity-preserving path from QB. The first stage is deliberately
* moderate: 24-um input gate at PRE=4, then the established final driver.
XO0 QB O0 VDD VSS cp_inv WP=4u WN=2u MP={PRE} MN={PRE}
XO1 O0 SENSE VDD VSS cp_inv WP=8u WN=8u MP={OUT} MN={OUT}
.ends cp_sense_direct_write_sr
"""


def compile_source(latch_mult: int, write_mult: int, pre_mult: int = 4,
                   output_mult: int = 8, screening_top: bool = False,
                   latch_p_width_um: int = 4) -> str:
    if latch_mult not in (1, 2):
        raise ValueError("latch multiplier must be 1 or 2")
    if write_mult not in (2, 4, 8):
        raise ValueError("write multiplier must be 2, 4, or 8")
    if pre_mult not in (2, 4, 8):
        raise ValueError("predriver multiplier must be 2, 4, or 8")
    if output_mult not in (4, 8, 12, 16):
        raise ValueError("output multiplier must be 4, 8, 12, or 16")
    if latch_p_width_um not in (4, 8, 12):
        raise ValueError("latch PMOS width must be 4, 8, or 12 um")
    source = base.compile_source()
    marker = ".subckt sense_write_phase HCLK SSEL WSEL ESEL VDD VSS\n"
    if source.count(marker) != 1:
        raise ValueError("direct-write lowering lost its phase boundary")
    primitive = (PRIMITIVE.replace("{LM}", str(latch_mult))
                 .replace("{WM}", str(write_mult))
                 .replace("{LPW}", f"{latch_p_width_um}u")
                 .replace("{PRE}", str(pre_mult))
                 .replace("{OUT}", str(output_mult)))
    source = source.replace(marker, primitive + "\n" + marker, 1)
    old = "XSENSE SFDRV SSEL SENSE VDD VSS cp_sense_final_select PMP=24 BASE_MN=2 EXTRA_W=8u EXTRA_M=1"
    new = """XSENSEDW START END SENSE VDD VSS cp_sense_direct_write_sr
* SSEL is retained as an explicitly terminated compatibility pin; WSEL owns
* the physical reset-event interval.
XDWSELLOAD SSEL DWSEL_UNUSED VDD VSS cp_inv WP=4u WN=2u MP=1 MN=1"""
    if source.count(old) != 1:
        raise ValueError("direct-write lowering lost its SENSE boundary")
    source = source.replace(old, new, 1)
    top_name = TOP + "_pex" if screening_top else TOP
    return buffered.add_physical_interface(source, top_name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latch-mult", type=int, default=1)
    parser.add_argument("--write-mult", type=int, default=4)
    parser.add_argument("--pre-mult", type=int, default=4)
    parser.add_argument("--output-mult", type=int, default=8)
    parser.add_argument("--latch-p-width-um", type=int, default=4)
    parser.add_argument("--screening-top", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = compile_source(args.latch_mult, args.write_mult, args.pre_mult,
                            args.output_mult, args.screening_top,
                            args.latch_p_width_um)
    args.output.write_text(source)
    print(f"source_revision={SOURCE_REVISION} latch_mult={args.latch_mult} "
          f"write_mult={args.write_mult} pre_mult={args.pre_mult} "
          f"output_mult={args.output_mult} latch_p_width_um={args.latch_p_width_um} "
          f"schematic_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
