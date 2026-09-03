#!/usr/bin/env python3
"""Run the compact valid-UART-boot, four-core, UART, and SDRAM integration test."""

from __future__ import annotations

import argparse
import importlib.util
import os
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = Path("/app/input_files") if Path("/app/input_files/spec").is_dir() else ROOT / "environment/input_files"
TESTS = Path("/tests") if Path("/tests/assets").is_dir() else ROOT / "tests"


def load_boot_spec():
    spec = importlib.util.spec_from_file_location("boot_image", INPUT / "spec/boot_image.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def rtl_files(candidate: Path) -> list[Path]:
    rtl = candidate / "rtl"
    package, top = rtl / "lnp64_soc_pkg.sv", rtl / "lnp64_soc.sv"
    if not package.is_file() or not top.is_file():
        raise SystemExit("candidate is missing the required RTL files")
    return [package, *sorted(path for path in rtl.glob("*.sv") if path not in {package, top}), top]


def smoke_payload() -> bytes:
    words = [int(line, 16) for line in (TESTS / "assets/platform_smoke.hex").read_text().splitlines() if line]
    return b"".join(struct.pack("<Q", word) for word in words)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    boot = load_boot_spec()
    payload = smoke_payload()
    image = boot.build_image(payload, 0x40000000, 0x40000000)
    frame = boot.frame_uart(image)

    with tempfile.TemporaryDirectory(prefix="lnp64-platform-") as temporary:
        work = Path(temporary)
        frame_path = work / "boot.frame"
        frame_path.write_bytes(frame)
        obj = work / "obj"
        command = [
            "verilator", "--cc", "--exe", "--build", "-j", str(min(16, os.cpu_count() or 1)),
            "--top-module", "lnp64_soc", "--Mdir", str(obj), "--timing", "--timescale", "1ns/1ps",
            "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-TIMESCALEMOD", "-Wno-WIDTH",
            *map(str, rtl_files(args.candidate)), str(INPUT / "memory/lnp64_sram_macros.sv"),
            str(TESTS / "gating/lnp64_uart_platform.cpp"),
        ]
        build = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if build.returncode:
            print(build.stdout, end="")
            raise SystemExit("candidate failed Verilator compilation")
        run = subprocess.run([str(obj / "Vlnp64_soc"), str(frame_path)], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(run.stdout, end="")
        raise SystemExit(run.returncode)


if __name__ == "__main__":
    main()
