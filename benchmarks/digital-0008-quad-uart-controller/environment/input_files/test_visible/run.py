#!/usr/bin/env python3
from pathlib import Path
import subprocess, sys, tempfile

root = Path(__file__).resolve().parents[1]
candidate = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/output")
rtl = candidate / "rtl/quad_uart_controller.sv"
with tempfile.TemporaryDirectory() as td:
    out = Path(td) / "sim.vvp"
    subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", out,
                    rtl, Path(__file__).with_name("tb.sv")], check=True)
    result = subprocess.run(["vvp", out], text=True, capture_output=True)
    print(result.stdout, end="")
    if result.returncode or "VISIBLE_PASS" not in result.stdout:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(1)
