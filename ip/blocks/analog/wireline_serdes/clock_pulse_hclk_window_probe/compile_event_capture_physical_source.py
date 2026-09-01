#!/usr/bin/env python3
"""Lower the selected event source and capture-clock bridge into one macro."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_source as event_source


ROOT = Path(__file__).resolve().parent
BRIDGE = ROOT / "event_capture_bridge_direct_end_rebalanced.spice"
TOP = "retimed_event_capture_bridge"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"expected exactly one lowering site for {old!r}")
    return text.replace(old, new, 1)


def compile_source(source: str | None = None) -> str:
    source = event_source.compile_source() if source is None else source
    bridge_sha256 = hashlib.sha256(BRIDGE.read_bytes()).hexdigest()

    old_phase = ".subckt sense_write_phase HCLK SSEL WSEL ESEL VDD VSS SENSE BOOST START END"
    new_phase = """.subckt sense_write_phase HCLK SSEL WSEL ESEL VDD VSS
+ SENSE BOOST CAPTURE_CLK CAPTURE_CLKB"""
    source = replace_once(source, old_phase, new_phase)

    old_phase_end = """XWRITE HCLK WSEL ESEL VDD VSS START END hclk_select_window
.ends sense_write_phase"""
    new_phase_end = f"""XWRITE HCLK WSEL ESEL VDD VSS START END hclk_select_window

* Selected full-duty bridge identity: sha256={bridge_sha256}
* START drives CLKB first; inverted END drives CLK later.  The state remains
* full duty through the tree, so no narrow pulse is routed or regenerated.
XWCB0 START STARTB VDD VSS cp_inv WP=5u WN=3u MP=4 MN=4
XWCLKB STARTB CAPTURE_CLKB VDD VSS cp_inv WP=8u WN=10u MP=8 MN=8
XWCLK END CAPTURE_CLK VDD VSS cp_inv WP=12u WN=5u MP=8 MN=8
.ends sense_write_phase"""
    source = replace_once(source, old_phase_end, new_phase_end)

    old_top = """.subckt retimed_capture_events CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD VSS
+ E_SENSE E_BOOST E_START E_END O_SENSE O_BOOST O_START O_END
* SEL0=SENSE assist, SEL1=event interval, SEL2=event epoch.
XE CLKP_H SEL0 SEL1 SEL2 VDD VSS E_SENSE E_BOOST E_START E_END sense_write_phase
XO CLKN_H SEL0 SEL1 SEL2 VDD VSS O_SENSE O_BOOST O_START O_END sense_write_phase
.ends retimed_capture_events"""
    new_top = f""".subckt {TOP} CLKP_H CLKN_H SEL0 SEL1 SEL2 VDD VSS
+ E_SENSE E_BOOST E_CAPTURE_CLK E_CAPTURE_CLKB
+ O_SENSE O_BOOST O_CAPTURE_CLK O_CAPTURE_CLKB
* SEL0=SENSE assist, SEL1=event interval, SEL2=event epoch.
XE CLKP_H SEL0 SEL1 SEL2 VDD VSS
+ E_SENSE E_BOOST E_CAPTURE_CLK E_CAPTURE_CLKB sense_write_phase
XO CLKN_H SEL0 SEL1 SEL2 VDD VSS
+ O_SENSE O_BOOST O_CAPTURE_CLK O_CAPTURE_CLKB sense_write_phase
.ends {TOP}"""
    source = replace_once(source, old_top, new_top)
    if ".subckt retimed_capture_events" in source:
        raise ValueError("obsolete event-only top survived physical lowering")
    return source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = compile_source()
    args.output.write_text(source)
    print(
        f"top={TOP} source_revision={event_source.SOURCE_REVISION} "
        f"bridge_sha256={hashlib.sha256(BRIDGE.read_bytes()).hexdigest()} "
        f"schematic_sha256={hashlib.sha256(source.encode()).hexdigest()}"
    )


if __name__ == "__main__":
    main()
