#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_boot_adapter.py OUTPUT")
    output = Path(sys.argv[1]).resolve()
    rtl = output / "rtl"
    package = rtl / "lnp64_soc_pkg.sv"
    top = rtl / "lnp64_soc.sv"
    if not package.is_file() or not top.is_file():
        raise SystemExit("candidate package or top is missing")
    sources = [package, *sorted(path for path in rtl.glob("*.sv") if path not in {package, top}), top]
    with tempfile.TemporaryDirectory(prefix="lnp64-boot-") as temp:
        executable = Path(temp) / "uart-invalid.vvp"
        command = ["iverilog", "-g2012", "-s", "tb_uart_invalid_image", "-o", str(executable)]
        command += [str(path) for path in sources]
        command += [str(Path(__file__).with_name("tb_uart_invalid_image.sv"))]
        subprocess.run(command, check=True)
        subprocess.run(["vvp", str(executable)], check=True, env={**os.environ, "LC_ALL": "C"})


if __name__ == "__main__":
    main()
