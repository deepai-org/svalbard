#!/usr/bin/env python3
"""Generate edge-selective SENSE-release hold candidates."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_state_free_physical_source as base
import compile_event_capture_state_free_buffered_physical_source as buffered


TOP = base.TOP
SOURCE_REVISION = "retimed_capture_owned_start_edge_hold_v1"


def compile_source(hold_mult: int, delay_mult: int = 16,
                   screening_top: bool = False, hold_width_um: float = 8) -> str:
    if hold_mult not in (1, 2, 4, 8):
        raise ValueError("hold multiplier must be 1, 2, 4, or 8")
    if delay_mult not in (8, 16):
        raise ValueError("delay multiplier must be 8 or 16")
    if hold_width_um not in (0.5, 1, 1.5, 2, 4, 6, 8):
        raise ValueError("unsupported hold width")
    source = base.compile_source()
    old = "XSENSE SFDRV SSEL SENSE VDD VSS cp_sense_final_select PMP=24 BASE_MN=2 EXTRA_W=8u EXTRA_M=1"
    if source.count(old) != 1:
        raise ValueError("edge-hold lowering lost its SENSE boundary")
    new = "\n".join([
        old,
        f"XREL SFDRV SFREL VDD VSS cp_delay WP=4u WN=2u MP={delay_mult} MN={delay_mult}",
        f"XHOLD SENSE SFREL SSEL VSS cp_cond_npd_comp W={hold_width_um}u M={hold_mult}",
    ])
    source = source.replace(old, new, 1)
    top_name = TOP + "_pex" if screening_top else TOP
    return buffered.add_physical_interface(source, top_name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hold-mult", required=True, type=int)
    parser.add_argument("--delay-mult", type=int, default=16)
    parser.add_argument("--hold-width-um", type=float, default=8)
    parser.add_argument("--screening-top", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = compile_source(args.hold_mult, args.delay_mult, args.screening_top,
                            args.hold_width_um)
    args.output.write_text(source)
    print(f"source_revision={SOURCE_REVISION} hold_mult={args.hold_mult} "
          f"delay_mult={args.delay_mult} hold_width_um={args.hold_width_um} "
          f"schematic_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
