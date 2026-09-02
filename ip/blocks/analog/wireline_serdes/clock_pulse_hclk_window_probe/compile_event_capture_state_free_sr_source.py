#!/usr/bin/env python3
"""Generate independently set/reset SENSE candidates from START and END."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_state_free_physical_source as base
import compile_event_capture_state_free_buffered_physical_source as buffered


TOP = base.TOP
SOURCE_REVISION = "retimed_capture_owned_start_end_sr_v7_timing_lane_core"

SR_PRIMITIVE = """
.subckt cp_sense_start_end_sr START END SENSE VDD VSS params: LM=2 PRE=4 OUT=8
* START falls before END: SETB is briefly active. START rises before END:
* RESETB is briefly active. The two full-duty input states make these windows
* non-overlapping; the cross-coupled NAND pair retains state between them.
XIS START STARTB VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2
XIE END ENDB VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2
XSETB STARTB END SETB VDD VSS cp_nand2_comp WP=4u WN=4u MP=2 MN={SETM}
XRESETB START ENDB RESETB VDD VSS cp_nand2_comp WP=4u WN=4u MP=2 MN=2
XQ RESETB QB Q VDD VSS cp_nand2_comp WP=4u WN=4u MP={LM} MN={LM}
XQB SETB Q QB VDD VSS cp_nand2_comp WP=4u WN=4u MP={LM} MN={LM}
* QB is the fully switching state for the START/END ordering. A four-stage
* taper limits the state-node input gate to 6 um, then restores drive while
* preserving polarity at SENSE.
XO0 QB O0 VDD VSS cp_inv WP=4u WN=2u MP=1 MN=1
XO1 O0 O1 VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2
XO2 O1 O2 VDD VSS cp_inv WP=8u WN=8u MP={PRE} MN={PRE}
XO3 O2 SENSE VDD VSS cp_inv WP=8u WN=8u MP={OUT} MN={OUT}
.ends cp_sense_start_end_sr
"""


def compile_source(latch_mult: int, pre_mult: int, output_mult: int,
                   screening_top: bool = False, set_mult: int = 2) -> str:
    if latch_mult not in (1, 2, 4):
        raise ValueError("latch multiplier must be 1, 2, or 4")
    if pre_mult not in (2, 4, 8):
        raise ValueError("predriver multiplier must be 2, 4, or 8")
    if output_mult not in (4, 8, 12, 16):
        raise ValueError("output multiplier must be 4, 8, 12, or 16")
    if set_mult not in (2, 8):
        raise ValueError("set multiplier must be 2 or 8")
    source = base.compile_source()
    marker = ".subckt sense_write_phase HCLK SSEL WSEL ESEL VDD VSS\n"
    if source.count(marker) != 1:
        raise ValueError("SR lowering lost its phase primitive boundary")
    source = source.replace(
        marker, SR_PRIMITIVE.replace("{SETM}", str(set_mult)) + "\n" + marker, 1)
    old = "XSENSE SFDRV SSEL SENSE VDD VSS cp_sense_final_select PMP=24 BASE_MN=2 EXTRA_W=8u EXTRA_M=1"
    new = ("XSENSESR START END SENSE VDD VSS cp_sense_start_end_sr "
           f"LM={latch_mult} PRE={pre_mult} OUT={output_mult}\n"
           "* SSEL is retained as a compatibility pin; WSEL selects the real "
           "reset-event interval.\n"
           "XSRSELLOAD SSEL SRSEL_UNUSED VDD VSS cp_inv WP=4u WN=2u MP=1 MN=1")
    if source.count(old) != 1:
        raise ValueError("SR lowering lost its SENSE boundary")
    source = source.replace(old, new, 1)
    top_name = TOP + "_pex" if screening_top else TOP
    return buffered.add_physical_interface(source, top_name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latch-mult", type=int, default=2)
    parser.add_argument("--pre-mult", type=int, default=4)
    parser.add_argument("--output-mult", type=int, default=8)
    parser.add_argument("--set-mult", type=int, default=2)
    parser.add_argument("--screening-top", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = compile_source(args.latch_mult, args.pre_mult, args.output_mult,
                            args.screening_top, args.set_mult)
    args.output.write_text(source)
    print(f"source_revision={SOURCE_REVISION} latch_mult={args.latch_mult} "
          f"pre_mult={args.pre_mult} output_mult={args.output_mult} "
          f"set_mult={args.set_mult} "
          f"schematic_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
