#!/usr/bin/env python3
"""Lower a small stored event node with capture-owned local clock drivers."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_source as selected


TOP = selected.TOP
SOURCE_REVISION = "retimed_joint_long_6_3_capture_integrated_shared_predriver_v2"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"integrated-state lowering expected one occurrence: {old!r}")
    return text.replace(old, new)


def compile_source() -> str:
    source = selected.compile_source()
    source = replace_once(
        source,
        "XSB1 HSN SB1 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=4\n"
        "XSI0 SB1 SIB VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
        "XSI1 SIB SDRV VDD VSS cp_inv WP=8u WN=8u MP=12 MN=16",
        "* HSN sets only the small stored node.  The reset edge is separated\n"
        "* by the full-duty HCLK state; neither device directly drives a clock load.\n"
        "XSTATE HSN HCLK ESTATE VDD VSS cp_capture_event_state WP=8u WN=4u MP=4 MN=1\n"
        "* One capture-local predriver serves both consumers, halving ESTATE\n"
        "* gate load. The robust LSTATE node, not the dynamic state, fans out.\n"
        "XLC0 ESTATE LCB VDD VSS cp_inv WP=4u WN=2u MP=4 MN=4\n"
        "XLC1 LCB LSTATE VDD VSS cp_inv WP=6u WN=3u MP=6 MN=6\n"
        "XLS2 LSTATE SIB VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
        "XLS3 SIB SDRV VDD VSS cp_inv WP=8u WN=8u MP=12 MN=16",
    )
    source = replace_once(
        source,
        "* Restore BOOST directly from the full-width SB1 state.\n"
        "XRB2 SB1 BOOST VDD VSS cp_inv WP=8u WN=8u MP=5 MN=8",
        "* BOOST splits only after the shared full-swing local predriver.\n"
        "XLB2 LSTATE BOOST VDD VSS cp_inv WP=8u WN=8u MP=5 MN=8",
    )
    source = replace_once(
        source,
        "XSB2 SDRV SSEL SENSE VDD VSS cp_sense_final_select "
        "PMP=12 BASE_MN=4 EXTRA_W=8u EXTRA_M=4",
        "XSB2 SDRV SSEL SENSE VDD VSS cp_sense_final_select "
        "PMP=24 BASE_MN=5 EXTRA_W=8u EXTRA_M=4",
    )
    return replace_once(
        source,
        ".subckt cp_fall_pulse A B Y VDD VSS",
        ".subckt cp_capture_event_state SETB RESET Q VDD VSS "
        "params: WP=8u WN=4u MP=4 MN=1\n"
        "XP Q SETB VDD VDD pfet_03v3 w={WP} l=0.28u m={MP}\n"
        "XN Q RESET VSS VSS nfet_03v3 w={WN} l=0.28u m={MN}\n"
        ".ends cp_capture_event_state\n\n"
        ".subckt cp_fall_pulse A B Y VDD VSS",
    )


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
