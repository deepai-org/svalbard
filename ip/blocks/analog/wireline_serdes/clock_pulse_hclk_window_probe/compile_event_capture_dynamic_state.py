#!/usr/bin/env python3
"""Lower a contention-free dynamic event state for bounded admission."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_source as selected


TOP = selected.TOP
SOURCE_REVISION = "retimed_joint_long_6_3_active_low_dynamic_state"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"dynamic-state lowering expected one occurrence: {old!r}")
    return text.replace(old, new)


def compile_source() -> str:
    source = selected.compile_source()
    source = replace_once(
        source,
        "XSB1 HSN SB1 VDD VSS cp_inv WP=8u WN=8u MP=8 MN=4",
        "XSB1 HSN HCLK SB1 VDD VSS cp_dynamic_event_state "
        "WP=8u WN=8u MP=8 MN=4",
    )
    return replace_once(
        source,
        ".subckt cp_fall_pulse A B Y VDD VSS",
        ".subckt cp_dynamic_event_state SETB RESET Q VDD VSS "
        "params: WP=8u WN=8u MP=8 MN=4\n"
        "XP Q SETB VDD VDD pfet_03v3 w={WP} l=0.28u m={MP}\n"
        "XN Q RESET VSS VSS nfet_03v3 w={WN} l=0.28u m={MN}\n"
        ".ends cp_dynamic_event_state\n\n"
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
