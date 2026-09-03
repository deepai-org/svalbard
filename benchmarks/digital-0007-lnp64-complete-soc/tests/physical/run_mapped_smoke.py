#!/usr/bin/env python3
"""Replay reset and JTAG sanity checks on an unmodified mapped netlist."""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = Path("/tests") if Path("/tests/physical").is_dir() else ROOT / "tests"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("netlist", type=Path)
    args = parser.parse_args()
    pdk = Path(os.environ.get("PDK_ROOT", "/foss/pdks")) / "gf180mcuD/libs.ref"
    sources = [
        pdk / "gf180mcu_fd_sc_mcu9t5v0/verilog/primitives.v",
        pdk / "gf180mcu_fd_sc_mcu9t5v0/verilog/gf180mcu_fd_sc_mcu9t5v0.v",
        TESTS / "physical/gf180_sram_functional.sv",
        args.netlist.resolve(),
    ]
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise SystemExit("mapped simulation input is missing: " + ", ".join(missing))
    with tempfile.TemporaryDirectory(prefix="lnp64-mapped-") as directory:
        obj = Path(directory) / "obj"
        command = [
            "verilator", "--cc", "--exe", "--build", "-j", str(min(16, os.cpu_count() or 1)),
            "--top-module", "lnp64_soc", "--Mdir", str(obj), "--timing", "--timescale", "1ns/1ps",
            "-O0", "--output-split", "1000", "--output-split-cfuncs", "1000",
            "-CFLAGS", "-O0",
            "-DFUNCTIONAL", "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-TIMESCALEMOD",
            "-Wno-WIDTH", "-Wno-PINMISSING", "-Wno-MULTITOP", "-Wno-MINTYPMAXDLY",
            "-Wno-SPECIFYIGN", *map(str, sources),
            str(TESTS / "physical/lnp64_mapped_smoke.cpp"),
        ]
        build = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if build.returncode:
            print(build.stdout, end="")
            raise SystemExit("mapped netlist failed Verilator compilation")
        run = subprocess.run([str(obj / "Vlnp64_soc")], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        print(run.stdout, end="")
        raise SystemExit(run.returncode)


if __name__ == "__main__":
    main()
