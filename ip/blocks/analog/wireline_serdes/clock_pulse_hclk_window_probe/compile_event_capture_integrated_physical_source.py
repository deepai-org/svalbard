#!/usr/bin/env python3
"""Lower the admitted capture-integrated event state with the selected bridge."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import compile_event_capture_integrated_state as integrated
import compile_event_capture_physical_source as physical


TOP = physical.TOP
BRIDGE = physical.BRIDGE


def compile_source() -> str:
    return physical.compile_source(integrated.compile_source())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = compile_source()
    args.output.write_text(source)
    print(f"top={TOP} source_revision={integrated.SOURCE_REVISION} "
          f"bridge_sha256={hashlib.sha256(BRIDGE.read_bytes()).hexdigest()} "
          f"schematic_sha256={hashlib.sha256(source.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
