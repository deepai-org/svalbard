#!/usr/bin/env python3
"""Generate realizable state-free SENSE assertion-duration candidates."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_state_free_physical_source as base
import compile_event_capture_state_free_buffered_physical_source as buffered


TOP = base.TOP
SOURCE_REVISION = "retimed_capture_owned_start_stretched_v2"

STRETCH = """
.subckt cp_sense_stretch A B Y VDD VSS
* Fully restored active-low OR. A direct CMOS NOR's stacked PMOS reached only
* 1.10 V at slow/hot under the physical-interface gate load.
XIA A AB VDD VSS cp_inv WP=8u WN=8u MP=2 MN=2
XIB B BB VDD VSS cp_inv WP=8u WN=8u MP=2 MN=2
XOR AB BB ORSTATE VDD VSS cp_nand2_comp WP=8u WN=8u MP=4 MN=4
XO ORSTATE Y VDD VSS cp_inv WP=8u WN=8u MP=12 MN=12
.ends cp_sense_stretch

.subckt cp_stretch_enable A EN Y VDD VSS
XI EN ENB VDD VSS cp_inv WP=4u WN=2u MP=2 MN=2
XTG A Y EN ENB VDD VSS cp_tg W=8u M=2
XOFF Y ENB VSS VSS nfet_03v3 w=4u l=0.28u m=2
.ends cp_stretch_enable
"""


def compile_source(delay_cells: int, screening_top: bool = False,
                   delay_mult: int = 8) -> str:
    if not 0 <= delay_cells <= 4:
        raise ValueError("delay cells must be 0--4")
    if delay_mult not in (2, 4, 8, 16):
        raise ValueError("delay multiplier must be 2, 4, 8, or 16")
    source = base.compile_source()
    marker = ".subckt sense_write_phase HCLK SSEL WSEL ESEL VDD VSS\n"
    if source.count(marker) != 1:
        raise ValueError("stretched lowering lost its phase primitive boundary")
    source = source.replace(marker, STRETCH + "\n" + marker, 1)
    old = "XSENSE SFDRV SSEL SENSE VDD VSS cp_sense_final_select PMP=24 BASE_MN=2 EXTRA_W=8u EXTRA_M=1"
    if source.count(old) != 1:
        raise ValueError("stretched lowering lost its SENSE boundary")
    lines = []
    previous = "SFDRV"
    for index in range(delay_cells):
        output = "SFDELAY" if index + 1 == delay_cells else f"SFD{index}"
        lines.append(f"XSWD{index} {previous} {output} VDD VSS cp_delay WP=4u WN=2u MP={delay_mult} MN={delay_mult}")
        previous = output
    if delay_cells == 0:
        previous = "SFDRV"
    lines.extend([
        f"XSWEN {previous} SSEL SFWIDE VDD VSS cp_stretch_enable",
        "XSTRETCH SFDRV SFWIDE SENSE VDD VSS cp_sense_stretch",
    ])
    source = source.replace(old, "\n".join(lines), 1)
    top_name = TOP + "_pex" if screening_top else TOP
    return buffered.add_physical_interface(source, top_name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay-cells", required=True, type=int)
    parser.add_argument("--delay-mult", type=int, default=8)
    parser.add_argument("--screening-top", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = compile_source(args.delay_cells, args.screening_top, args.delay_mult)
    args.output.write_text(source)
    print(f"source_revision={SOURCE_REVISION} delay_cells={args.delay_cells} delay_mult={args.delay_mult} "
          f"schematic_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
