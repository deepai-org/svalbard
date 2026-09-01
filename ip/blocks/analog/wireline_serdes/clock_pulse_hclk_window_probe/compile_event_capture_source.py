#!/usr/bin/env python3
"""Lower the retained retimed source to full-duty capture events.

This is a separate circuit identity from the rejected WRITE-pulse macro.  It
exports restored START and END states and removes the detector/output taper;
the capture consumer, not a 650-fF proxy, owns local clock formation.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_recovery_physical_source as recovery


TOP = "retimed_capture_events"
SOURCE_REVISION = "retimed_joint_long_6_3_active_low_nand_state"
BASE_REVISION = "retimed_joint_long_6_3"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"event lowering expected one occurrence: {old!r}")
    return text.replace(old, new)


def compile_source() -> str:
    text = recovery.compile_source(BASE_REVISION)
    # SB1 otherwise drives roughly 250 um of final-selector gate width plus
    # extracted route capacitance and loses its high state at SS/hot.  Two
    # ordinary CMOS stages preserve polarity and taper the load.  Physical
    # closure keeps the strong selector because the compact experiment lost
    # SS/hot low-rail margin; layout ordering owns the timing-path compaction.
    text = replace_once(
        text,
        "XSB1 SB0 SB1 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=4\n"
        "* Code 0 uses only the weakened base pull-down, widening SENSE at SS/hot.",
        "XSB1 SB0 SB1 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=4\n"
        "XSI0 SB1 SIB VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
        "XSI1 SIB SDRV VDD VSS cp_inv WP=8u WN=8u MP=12 MN=16\n"
        "* Code 0 uses only the weakened base pull-down, widening SENSE at SS/hot.")
    text = replace_once(
        text,
        "XSB2 SB1 SSEL SENSE VDD VSS cp_sense_final_select "
        "PMP=12 BASE_MN=4 EXTRA_W=8u EXTRA_M=4",
        "XSB2 SDRV SSEL SENSE VDD VSS cp_sense_final_select "
        "PMP=12 BASE_MN=4 EXTRA_W=8u EXTRA_M=4")
    text = replace_once(
        text,
        "XHSD2 HSD HSDX VDD VSS cp_delay WP=2u WN=1u MP=2 MN=2\n"
        "XHSN HCLK HSDX HSN VDD VSS cp_fall_pulse\n"
        "XSB0 HSN SB0 VDD VSS cp_inv WP=8u WN=10u MP=2 MN=2\n"
        "XSB1 SB0 SB1 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=4",
        "XHSD2 HSD HSDX VDD VSS cp_delay WP=2u WN=1u MP=2 MN=2\n"
        "XHSN HCLK HSDX HSN VDD VSS cp_fall_nand_bar\n"
        "XSB1 HSN SB1 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=4")
    text = replace_once(
        text,
        ".subckt cp_fall_pulse A B Y VDD VSS",
        ".subckt cp_fall_nand_bar A B YB VDD VSS\n"
        "XIA A AB VDD VSS cp_inv WP=8u WN=8u\n"
        "XN B AB YB VDD VSS cp_nand2_comp WP=8u WN=8u MP=3 MN=3\n"
        ".ends cp_fall_nand_bar\n\n"
        ".subckt cp_fall_pulse A B Y VDD VSS")
    text = replace_once(
        text,
        ".subckt hclk_select_window HCLK SEL ESEL VDD VSS WRITE WPN",
        ".subckt hclk_select_window HCLK SEL ESEL VDD VSS START END")
    text = replace_once(
        text,
        "XDET START END WIN VDD VSS cp_fall_window\n"
        "XWPN WIN WPN VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2\n"
        "XWB0 WPN WB1 VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2\n"
        "XWB1 WB1 WB2 VDD VSS cp_inv WP=4u WN=4u MP=4 MN=4\n"
        "XWB2 WB2 WB3 VDD VSS cp_inv WP=8u WN=8u MP=4 MN=4\n"
        "XWB3 WB3 WB4 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
        "XWB4 WB4 WRITE VDD VSS cp_final_inv",
        "* START and END are full-duty output states owned by the consumer.")
    text = replace_once(
        text,
        ".subckt sense_write_phase HCLK SSEL WSEL ESEL VDD VSS SENSE BOOST WRITE WPN",
        ".subckt sense_write_phase HCLK SSEL WSEL ESEL VDD VSS SENSE BOOST START END")
    text = replace_once(
        text,
        "XWRITE HCLK WSEL ESEL VDD VSS WRITE WPN hclk_select_window",
        "XWRITE HCLK WSEL ESEL VDD VSS START END hclk_select_window")
    old_top = (
        ".subckt recovery_dual_control_pulse CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD VSS\n"
        "+ E_SENSE E_BOOST E_WRITE O_SENSE O_BOOST O_WRITE\n"
        "* SEL0=SENSE assist, SEL1=WRITE interval, SEL2=WRITE epoch.\n"
        "XE CLKP_H SEL0 SEL1 SEL2 VDD VSS E_SENSE E_BOOST E_WRITE E_WPN sense_write_phase\n"
        "XO CLKN_H SEL0 SEL1 SEL2 VDD VSS O_SENSE O_BOOST O_WRITE O_WPN sense_write_phase\n"
        ".ends recovery_dual_control_pulse")
    new_top = (
        f".subckt {TOP} CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD VSS\n"
        "+ E_SENSE E_BOOST E_START E_END O_SENSE O_BOOST O_START O_END\n"
        "* SEL0=SENSE assist, SEL1=event interval, SEL2=event epoch.\n"
        "XE CLKP_H SEL0 SEL1 SEL2 VDD VSS E_SENSE E_BOOST E_START E_END sense_write_phase\n"
        "XO CLKN_H SEL0 SEL1 SEL2 VDD VSS O_SENSE O_BOOST O_START O_END sense_write_phase\n"
        f".ends {TOP}")
    return replace_once(text, old_top, new_top)


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
