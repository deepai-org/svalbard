#!/usr/bin/env python3
"""Lower the admitted state-free capture source with its selected bridge."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_physical_source as physical
import compile_event_capture_state_free as state_free


TOP = physical.TOP
BRIDGE = physical.BRIDGE


def compile_source() -> str:
    source = state_free.compile_source()
    write = "XWRITE HCLK WSEL ESEL VDD VSS START END hclk_select_window\n"
    if source.count(write) != 1:
        raise ValueError("state-free physical lowering lost its WRITE instance")
    source = source.replace(write, "", 1)
    marker = ("XBOOST SFDRV BOOST VDD VSS cp_inv WP=8u WN=8u MP=8 MN=8\n"
              ".ends sense_write_phase")
    if source.count(marker) != 1:
        raise ValueError("state-free physical lowering lost its phase boundary")
    source = source.replace(
        marker,
        marker.replace("\n.ends", f"\n{write}.ends"),
        1,
    )
    return physical.compile_source(source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = compile_source()
    args.output.write_text(source)
    print(f"top={TOP} source_revision={state_free.SOURCE_REVISION} "
          f"bridge_sha256={hashlib.sha256(BRIDGE.read_bytes()).hexdigest()} "
          f"schematic_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
