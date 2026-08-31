#!/usr/bin/env python3
"""Compile the first localized three-control pulse-recovery circuit."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_selected_physical_source as selected


TOP = "recovery_dual_control_pulse"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"recovery lowering expected one occurrence: {old!r}")
    return text.replace(old, new)


def compile_source() -> str:
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
    args = parser.parse_args()
    source = compile_source()
    args.output.write_text(source)
    print(f"top={TOP} source_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
