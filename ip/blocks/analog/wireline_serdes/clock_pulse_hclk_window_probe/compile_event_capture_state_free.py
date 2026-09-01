#!/usr/bin/env python3
"""Lower recovery assists from the restored full-duty START state.

The capture clock bridge already consumes START and END.  Reusing START for the
parallel SENSE/BOOST assists removes the dynamic HSN/state fanout while keeping
SENSE independent of the END interval choice.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_source as selected


TOP = selected.TOP
SOURCE_REVISION = "retimed_joint_long_6_3_capture_owned_start_v3"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"state-free lowering expected one occurrence: {old!r}")
    return text.replace(old, new)


def compile_source() -> str:
    source = selected.compile_source()
    old = """XHSD0 HCLK HSM VDD VSS cp_delay WP=4u WN=2u MP=2 MN=2
XHSD1 HSM HSD VDD VSS cp_sense_tail_delay
XHSD2 HSD HSDX VDD VSS cp_delay WP=2u WN=1u MP=2 MN=2
XHSN HCLK HSDX HSN VDD VSS cp_fall_nand_bar
XSB1 HSN SB1 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=4
XSI0 SB1 SIB VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8
XSI1 SIB SDRV VDD VSS cp_inv WP=8u WN=8u MP=12 MN=16
* Code 0 uses only the weakened base pull-down, widening SENSE at SS/hot.
* Code 1 enables a parallel series branch that advances only the SENSE falling
* edge needed to remove FF/cold overlap; the event source and rising edge stay fixed.
XSB2 SDRV SSEL SENSE VDD VSS cp_sense_final_select PMP=12 BASE_MN=4 EXTRA_W=8u EXTRA_M=4
* Restore BOOST directly from the full-width SB1 state.
XRB2 SB1 BOOST VDD VSS cp_inv WP=8u WN=8u MP=5 MN=8
XWRITE HCLK WSEL ESEL VDD VSS START END hclk_select_window"""
    new = """* END is a restored full-duty state selected for this capture phase.
* Two small local stages isolate its clock branch; only restored static states
* cross the capture boundary and no dynamic node drives a distributed taper.
XWRITE HCLK WSEL ESEL VDD VSS START END hclk_select_window
XSF0 START SFB VDD VSS cp_inv WP=4u WN=2u MP=4 MN=4
XSF1 SFB SFDRV VDD VSS cp_inv WP=8u WN=4u MP=12 MN=12
* Retain the existing assist bit: it changes only the falling edge of SENSE.
XSENSE SFDRV SSEL SENSE VDD VSS cp_sense_final_select PMP=24 BASE_MN=2 EXTRA_W=8u EXTRA_M=1
XBOOST SFDRV BOOST VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8"""
    return replace_once(source, old, new)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = compile_source()
    args.output.write_text(source)
    print(f"top={TOP} source_revision={SOURCE_REVISION} "
          f"source_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
