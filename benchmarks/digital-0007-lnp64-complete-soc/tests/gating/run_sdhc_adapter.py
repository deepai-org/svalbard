#!/usr/bin/env python3
"""Run native four-bit SDHC boot against the pin-level card model."""

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
TESTS = Path("/tests") if Path("/tests/gating").is_dir() else ROOT / "tests"


def rtl_files(candidate: Path) -> list[Path]:
    rtl = candidate / "rtl"
    package, top = rtl / "lnp64_soc_pkg.sv", rtl / "lnp64_soc.sv"
    if not package.is_file() or not top.is_file():
        raise SystemExit("candidate is missing the required RTL files")
    return [package, *sorted(path for path in rtl.glob("*.sv") if path not in {package, top}), top]


def boot_spec():
    spec = importlib.util.spec_from_file_location("boot_image", INPUT / "spec/boot_image.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def payload() -> bytes:
    words = [int(line, 16) for line in (TESTS / "assets/platform_smoke.hex").read_text().splitlines() if line]
    return b"".join(struct.pack("<Q", word) for word in words)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    image = boot_spec().build_image(payload(), 0x40000000, 0x40000000)
    if len(image) > 512:
        raise SystemExit("SDHC smoke image no longer fits its frozen single-block fixture")
    with tempfile.TemporaryDirectory(prefix="lnp64-sdhc-") as temporary:
        work = Path(temporary)
        sector = work / "sector.bin"
        sector.write_bytes(image + bytes(512 - len(image)))
        corrupted = work / "corrupt-sector.bin"
        bad = bytearray(sector.read_bytes())
        bad[64] ^= 1
        corrupted.write_bytes(bad)
        obj = work / "obj"
        build = subprocess.run([
            "verilator", "--cc", "--exe", "--build", "-j", str(min(16, os.cpu_count() or 1)),
            "--top-module", "lnp64_soc", "--Mdir", str(obj), "--timing", "--timescale", "1ns/1ps",
            "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-TIMESCALEMOD", "-Wno-WIDTH",
            *map(str, rtl_files(args.candidate)), str(INPUT / "memory/lnp64_sram_macros.sv"),
            str(TESTS / "gating/lnp64_sdhc_platform.cpp"),
        ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if build.returncode:
            print(build.stdout, end="")
            raise SystemExit("candidate failed Verilator compilation")
        for arguments in ([str(sector)], [str(corrupted), "--expect-error"]):
            run = subprocess.run([str(obj / "Vlnp64_soc"), *arguments], text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(run.stdout, end="")
            if run.returncode:
                raise SystemExit(run.returncode)


if __name__ == "__main__":
    main()
