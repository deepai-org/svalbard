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
             "final_drive_4_3", "split_final_drive", "end_final_drive",
             "retimed_tap_chain", "retimed_tap_fast2",
             "retimed_tap_p5n4", "retimed_tap_p4n5",
             "retimed_tap_m5", "retimed_tap_fast4",
             "retimed_p5n4_sense2", "retimed_p5n4_sense3",
             "retimed_p5n4_isolated_sense",
             "retimed_p5n4_isolated_sense2", "retimed_joint_long",
             "retimed_joint_long_6_3", "retimed_joint_long_6_3_compact",
             "retimed_joint_long_6_3_lean",
             "retimed_joint_long_6_3_latched",
             "retimed_joint_long_6_3_latched_strong")


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"recovery lowering expected one occurrence: {old!r}")
    return text.replace(old, new)


def replace_subckt(text: str, name: str, replacement: str) -> str:
    start = f".subckt {name} "
    end = f".ends {name}"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"recovery lowering cannot resolve subcircuit {name}")
    prefix, rest = text.split(start, 1)
    _, suffix = rest.split(end, 1)
    return prefix + replacement.strip() + suffix


RETIMED_TAP_CHAIN = """
.subckt hclk_select_window HCLK SEL ESEL VDD VSS WRITE WPN
XI_SEL SEL SELB VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2
XI_ESEL ESEL ESELB VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2

* Select epoch only between continuous full-duty clock states, then restore.
XED0 HCLK EDL VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2
XETG0 HCLK EMUX ESELB ESEL VDD VSS cp_tg W=8u M=2
XETG1 EDL EMUX ESEL ESELB VDD VSS cp_tg W=8u M=2
XEB0 EMUX EB0 VDD VSS cp_inv WP=8u WN=4u MP=2 MN=2
XEB1 EB0 EBASE VDD VSS cp_inv WP=8u WN=6u MP=3 MN=2

* A single compact tap chain defines interval.  START and both END choices
* come from full-duty states; no narrow event crosses a selector.
XTD0 EBASE T0 VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2
XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2
XTD2 T1 T2 VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2
XTG0 T1 ENDMUX SELB SEL VDD VSS cp_tg W=8u M=2
XTG1 T2 ENDMUX SEL SELB VDD VSS cp_tg W=8u M=2

* Matched detector-input restoration keeps load drive out of the delay taps.
XSR0 T0 SR0 VDD VSS cp_inv WP=8u WN=4u MP=2 MN=2
XSR1 SR0 START VDD VSS cp_inv WP=8u WN=6u MP=4 MN=3
XER0 ENDMUX ER0 VDD VSS cp_inv WP=8u WN=4u MP=2 MN=2
XER1 ER0 END VDD VSS cp_inv WP=8u WN=6u MP=4 MN=3

XDET START END WIN VDD VSS cp_fall_window
XWPN WIN WPN VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2
XWB0 WPN WB1 VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2
XWB1 WB1 WB2 VDD VSS cp_inv WP=4u WN=4u MP=4 MN=4
XWB2 WB2 WB3 VDD VSS cp_inv WP=8u WN=8u MP=4 MN=4
XWB3 WB3 WB4 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8
XWB4 WB4 WRITE VDD VSS cp_final_inv
.ends hclk_select_window
"""


ISOLATED_SENSE_SELECT = """
.subckt cp_sense_final_select A EN Y VDD VSS params: PMP=12 BASE_MN=5 EXTRA_W=8u EXTRA_M=4
XP Y A VDD VDD pfet_03v3 w=8u l=0.28u m={PMP}
XN Y A VSS VSS nfet_03v3 w=6.5u l=0.28u m={BASE_MN}
* Keep conditional drive off the output-side series stack.  EN selects A onto
* a local gate; ENB discharges that gate in the disabled state.
XI_EN EN ENB VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2
XTG A XG EN ENB VDD VSS cp_tg W=4u M=2
XOFF XG ENB VSS VSS nfet_03v3 w=4u l=0.28u m=2
XNEX Y XG VSS VSS nfet_03v3 w={EXTRA_W} l=0.28u m={EXTRA_M}
.ends cp_sense_final_select
"""


def joint_long_tap_chain() -> str:
    text = replace_once(
        RETIMED_TAP_CHAIN,
        "XED0 HCLK EDL VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2\n"
        "XETG0 HCLK EMUX ESELB ESEL VDD VSS cp_tg W=8u M=2\n"
        "XETG1 EDL EMUX ESEL ESELB VDD VSS cp_tg W=8u M=2\n"
        "XEB0 EMUX EB0 VDD VSS cp_inv WP=8u WN=4u MP=2 MN=2",
        "XED0 HCLK EDL VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2\n"
        "XED1 EDL EDL2 VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2\n"
        "XETG0 HCLK EMUX ESELB ESEL VDD VSS cp_tg W=8u M=2\n"
        "XLN ESEL SEL LONGB VDD VSS cp_nand2_comp WP=4u WN=4u MP=2 MN=2\n"
        "XLI LONGB LONG VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2\n"
        "XNN ESEL SELB NORMB VDD VSS cp_nand2_comp WP=4u WN=4u MP=2 MN=2\n"
        "XNI NORMB NORM VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2\n"
        "XETG1 EDL EMUX NORM NORMB VDD VSS cp_tg W=8u M=2\n"
        "XETG2 EDL2 EMUX LONG LONGB VDD VSS cp_tg W=8u M=2\n"
        "XEB0 EMUX EB0 VDD VSS cp_inv WP=8u WN=4u MP=2 MN=2")
    return replace_once(
        text,
        "XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2",
        "XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=5 MN=4")


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
    if revision in ("retimed_tap_chain", "retimed_tap_fast2",
                    "retimed_tap_p5n4", "retimed_tap_p4n5",
                    "retimed_tap_m5", "retimed_tap_fast4",
                    "retimed_p5n4_sense2", "retimed_p5n4_sense3",
                    "retimed_p5n4_isolated_sense",
                    "retimed_p5n4_isolated_sense2", "retimed_joint_long",
                    "retimed_joint_long_6_3",
                    "retimed_joint_long_6_3_compact",
                    "retimed_joint_long_6_3_lean",
                    "retimed_joint_long_6_3_latched",
                    "retimed_joint_long_6_3_latched_strong"):
        tap_chain = (joint_long_tap_chain()
                     if revision in ("retimed_joint_long",
                                     "retimed_joint_long_6_3",
                                     "retimed_joint_long_6_3_compact",
                                     "retimed_joint_long_6_3_lean",
                                     "retimed_joint_long_6_3_latched",
                                     "retimed_joint_long_6_3_latched_strong")
                     else RETIMED_TAP_CHAIN)
        if revision in ("retimed_joint_long_6_3",
                        "retimed_joint_long_6_3_compact",
                        "retimed_joint_long_6_3_lean",
                        "retimed_joint_long_6_3_latched",
                        "retimed_joint_long_6_3_latched_strong"):
            tap_chain = replace_once(
                tap_chain,
                "XED1 EDL EDL2 VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2",
                "XED1 EDL EDL2 VDD VSS cp_delay WP=6u WN=3u MP=2 MN=2")
        if revision not in ("retimed_tap_chain", "retimed_joint_long",
                            "retimed_joint_long_6_3",
                            "retimed_joint_long_6_3_compact",
                            "retimed_joint_long_6_3_lean",
                            "retimed_joint_long_6_3_latched",
                            "retimed_joint_long_6_3_latched_strong"):
            p_multiplier, n_multiplier = {
                "retimed_tap_fast2": ("4", "4"),
                "retimed_tap_p5n4": ("5", "4"),
                "retimed_tap_p4n5": ("4", "5"),
                "retimed_tap_m5": ("5", "5"),
                "retimed_tap_fast4": ("8", "8"),
                "retimed_p5n4_sense2": ("5", "4"),
                "retimed_p5n4_sense3": ("5", "4"),
                "retimed_p5n4_isolated_sense": ("5", "4"),
                "retimed_p5n4_isolated_sense2": ("5", "4"),
            }[revision]
            tap_chain = replace_once(
                tap_chain,
                "XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u MP=2 MN=2",
                f"XTD1 T0 T1 VDD VSS cp_delay WP=8u WN=4u "
                f"MP={p_multiplier} MN={n_multiplier}")
        text = replace_subckt(text, "hclk_select_window", tap_chain)
    if revision in ("retimed_p5n4_sense2", "retimed_p5n4_sense3"):
        sense_width = "16u" if revision == "retimed_p5n4_sense2" else "24u"
        text = replace_once(
            text, "EXTRA_W=8u EXTRA_M=4", f"EXTRA_W={sense_width} EXTRA_M=4")
    if revision in ("retimed_p5n4_isolated_sense",
                    "retimed_p5n4_isolated_sense2"):
        text = replace_subckt(text, "cp_sense_final_select",
                              ISOLATED_SENSE_SELECT)
        if revision == "retimed_p5n4_isolated_sense2":
            text = replace_once(
                text,
                "cp_sense_final_select PMP=12 BASE_MN=4 EXTRA_W=8u EXTRA_M=4",
                "cp_sense_final_select PMP=12 BASE_MN=4 EXTRA_W=8u EXTRA_M=8")
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
    if revision in ("compact_taper", "balanced_compact", "isolated_compact",
                    "retimed_joint_long_6_3_compact"):
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
    if revision == "retimed_joint_long_6_3_lean":
        # Preserve six restoring inversions and the qualified final driver,
        # but reduce early diffusion/gate capacitance and grow monotonically.
        # The retained physical PEX showed transition survival through WPN
        # followed by alternate-stage amplitude loss dominated by capacitance.
        text = replace_once(
            text,
            "XWPN WIN WPN VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2\n"
            "XWB0 WPN WB1 VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2\n"
            "XWB1 WB1 WB2 VDD VSS cp_inv WP=4u WN=4u MP=4 MN=4\n"
            "XWB2 WB2 WB3 VDD VSS cp_inv WP=8u WN=8u MP=4 MN=4\n"
            "XWB3 WB3 WB4 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
            "XWB4 WB4 WRITE VDD VSS cp_final_inv",
            "XWPN WIN WPN VDD VSS cp_inv WP=2u WN=2u MP=2 MN=2\n"
            "XWB0 WPN WB1 VDD VSS cp_inv WP=3u WN=3u MP=2 MN=2\n"
            "XWB1 WB1 WB2 VDD VSS cp_inv WP=4u WN=4u MP=3 MN=3\n"
            "XWB2 WB2 WB3 VDD VSS cp_inv WP=6u WN=6u MP=4 MN=4\n"
            "XWB3 WB3 WB4 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
            "XWB4 WB4 WRITE VDD VSS cp_final_inv")
    if revision in ("retimed_joint_long_6_3_latched",
                    "retimed_joint_long_6_3_latched_strong"):
        latch = """
.subckt cp_output_nor_latch S R Q QB VDD VSS
* Q is the loaded pulse output: RESET directly discharges it, while the
* cross-coupled QB state enables a deliberately wide series PMOS pull-up.
XPQ0 PQ R VDD VDD pfet_03v3 w=8u l=0.28u m=28
XPQ1 Q QB PQ VDD pfet_03v3 w=8u l=0.28u m=28
XNQ0 Q R VSS VSS nfet_03v3 w=8u l=0.28u m=22
XNQ1 Q QB VSS VSS nfet_03v3 w=8u l=0.28u m=22
* The private complementary state drives gates rather than external load.
XPB0 PB S VDD VDD pfet_03v3 w=8u l=0.28u m=8
XPB1 QB Q PB VDD pfet_03v3 w=8u l=0.28u m=8
XNB0 QB S VSS VSS nfet_03v3 w=8u l=0.28u m=8
XNB1 QB Q VSS VSS nfet_03v3 w=8u l=0.28u m=8
.ends cp_output_nor_latch
"""
        text = replace_once(text, ".subckt hclk_select_window ",
                            latch.strip() + "\n\n.subckt hclk_select_window ")
        text = replace_once(
            text,
            "XDET START END WIN VDD VSS cp_fall_window\n"
            "XWPN WIN WPN VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2\n"
            "XWB0 WPN WB1 VDD VSS cp_inv WP=4u WN=4u MP=2 MN=2\n"
            "XWB1 WB1 WB2 VDD VSS cp_inv WP=4u WN=4u MP=4 MN=4\n"
            "XWB2 WB2 WB3 VDD VSS cp_inv WP=8u WN=8u MP=4 MN=4\n"
            "XWB3 WB3 WB4 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
            "XWB4 WB4 WRITE VDD VSS cp_final_inv",
            "XSET START SET VDD VSS cp_inv WP=8u WN=8u MP=4 MN=4\n"
            "XRST END RESET VDD VSS cp_inv WP=8u WN=8u MP=4 MN=4\n"
            "XLAT SET RESET WRITE WPN VDD VSS cp_output_nor_latch")
        if revision == "retimed_joint_long_6_3_latched_strong":
            text = replace_once(text, "m=28\nXPQ1", "m=112\nXPQ1")
            text = replace_once(text, "m=28\nXNQ0", "m=112\nXNQ0")
            text = replace_once(text, "m=22\nXNQ1", "m=44\nXNQ1")
            text = replace_once(text, "m=22\n* The private", "m=44\n* The private")
            text = replace_once(text, "m=8\nXPB1", "m=28\nXPB1")
            text = replace_once(text, "m=8\nXNB0", "m=28\nXNB0")
            text = replace_once(text, "m=8\nXNB1", "m=28\nXNB1")
            text = replace_once(text, "m=8\n.ends cp_output_nor_latch",
                                "m=28\n.ends cp_output_nor_latch")
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
