#!/usr/bin/env python3
"""Compile the first localized three-control pulse-recovery circuit."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_selected_physical_source as selected


TOP = "recovery_dual_control_pulse"
REVISIONS = ("retained", "balanced_event", "compact_taper",
             "balanced_compact", "isolated_event", "isolated_compact",
             "final_drive_4_3", "split_final_drive", "end_final_drive")


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"recovery lowering expected one occurrence: {old!r}")
    return text.replace(old, new)


def compile_source(revision: str = "retained") -> str:
    if revision not in REVISIONS:
        raise ValueError(f"unknown recovery revision: {revision}")
    text = selected.compile_source()
    text = replace_once(
        text,
        ".subckt sense_write_phase HCLK SEL ESEL VDD VSS SENSE BOOST WRITE WPN",
        ".subckt sense_write_phase HCLK SSEL WSEL ESEL VDD VSS SENSE BOOST WRITE WPN")
    text = replace_once(
        text, "XSB2 SB1 SEL SENSE VDD VSS cp_sense_final_select",
        "XSB2 SB1 SSEL SENSE VDD VSS cp_sense_final_select")
    text = replace_once(
        text,
        "XRB0 HSN RB0 VDD VSS cp_inv WP=8u WN=4u\n"
        "XRB1 RB0 RB1 VDD VSS cp_inv WP=8u WN=6u MP=3 MN=2\n"
        "XRB2 RB1 BOOST VDD VSS cp_inv WP=8u WN=8u MP=5 MN=3",
        "* Restore BOOST directly from the full-width SB1 state.\n"
        "XRB2 SB1 BOOST VDD VSS cp_inv WP=8u WN=8u MP=5 MN=8")
    text = replace_once(
        text, "XWRITE HCLK SEL ESEL VDD VSS WRITE WPN hclk_select_window",
        "XWRITE HCLK WSEL ESEL VDD VSS WRITE WPN hclk_select_window")
    if revision in ("balanced_event", "balanced_compact"):
        # Do not encode event timing in an under-driven detector input.  Give
        # START and END the same two-stage restoration and make the final
        # detector drivers strong enough for the explicit detector gate load.
        text = replace_once(
            text,
            "XSTR0 S0A STR0 VDD VSS cp_inv WP=3.4u WN=1.7u MP=1 MN=1\n"
            "XSTR1 STR0 START VDD VSS cp_inv WP=1.7u WN=1.275u MP=3 MN=2",
            "XSTR0 S0A STR0 VDD VSS cp_inv WP=8u WN=4u MP=2 MN=2\n"
            "XSTR1 STR0 START VDD VSS cp_inv WP=8u WN=6u MP=6 MN=4")
        text = replace_once(
            text,
            "XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=3 MN=2",
            "XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=6 MN=4")
    if revision in ("isolated_event", "isolated_compact"):
        # Preserve the calibrated weak timing states, but do not connect them
        # directly to the large detector gates.  Identical two-stage output
        # restorers make event timing and detector drive separate concerns.
        text = replace_once(
            text,
            "XSTR1 STR0 START VDD VSS cp_inv WP=1.7u WN=1.275u MP=3 MN=2",
            "XSTR1 STR0 START_RAW VDD VSS cp_inv WP=1.7u WN=1.275u MP=3 MN=2\n"
            "XSR2 START_RAW STARTB VDD VSS cp_inv WP=8u WN=4u MP=2 MN=2\n"
            "XSR3 STARTB START VDD VSS cp_inv WP=8u WN=6u MP=6 MN=4")
        text = replace_once(
            text,
            "XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=3 MN=2",
            "XER1 ER0 END_RAW VDD VSS cp_inv WP=8u WN=6u MP=3 MN=2\n"
            "XER2 END_RAW ENDB VDD VSS cp_inv WP=8u WN=4u MP=2 MN=2\n"
            "XER3 ENDB END VDD VSS cp_inv WP=8u WN=6u MP=6 MN=4")
    if revision in ("final_drive_4_3", "split_final_drive"):
        text = replace_once(
            text,
            "XSTR1 STR0 START VDD VSS cp_inv WP=1.7u WN=1.275u MP=3 MN=2",
            "XSTR1 STR0 START VDD VSS cp_inv WP=1.7u WN=1.275u MP=4 MN=3")
    if revision == "final_drive_4_3":
        text = replace_once(
            text,
            "XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=3 MN=2",
            "XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=4 MN=3")
    if revision in ("split_final_drive", "end_final_drive"):
        text = replace_once(
            text,
            "XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=3 MN=2",
            "XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=6 MN=4")
    if revision in ("compact_taper", "balanced_compact", "isolated_compact"):
        # Six stages visibly erode the extracted narrow event.  Preserve the
        # even inversion count with four monotonically growing stages.
        text = replace_once(
            text,
            "XWPN WIN WPN VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2\n"
            "XWB0 WPN WB1 VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2\n"
            "XWB1 WB1 WB2 VDD VSS cp_inv WP=4u WN=4u MP=4 MN=4\n"
            "XWB2 WB2 WB3 VDD VSS cp_inv WP=8u WN=8u MP=4 MN=4\n"
            "XWB3 WB3 WB4 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
            "XWB4 WB4 WRITE VDD VSS cp_final_inv",
            "XWPN WIN WPN VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2\n"
            "XWB0 WPN WB1 VDD VSS cp_inv WP=4u WN=4u MP=4 MN=4\n"
            "XWB1 WB1 WB2 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
            "XWB4 WB2 WRITE VDD VSS cp_final_inv")
    marker = f"\n.subckt {selected.TOP} "
    if text.count(marker) != 1:
        raise ValueError("selected top boundary must resolve once")
    text = text.split(marker, 1)[0].rstrip()
    top = f"""

.subckt {TOP} CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD VSS
+ E_SENSE E_BOOST E_WRITE O_SENSE O_BOOST O_WRITE
* SEL0=SENSE assist, SEL1=WRITE interval, SEL2=WRITE epoch.
XE CLKP_H SEL0 SEL1 SEL2 VDD VSS E_SENSE E_BOOST E_WRITE E_WPN sense_write_phase
XO CLKN_H SEL0 SEL1 SEL2 VDD VSS O_SENSE O_BOOST O_WRITE O_WPN sense_write_phase
.ends {TOP}
"""
    return text + top


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", choices=REVISIONS, default="retained")
    args = parser.parse_args()
    source = compile_source(args.revision)
    args.output.write_text(source)
    print(f"top={TOP} revision={args.revision} "
          f"source_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
