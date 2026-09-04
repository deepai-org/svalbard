#!/usr/bin/env python3
from pathlib import Path
import argparse, os, subprocess, tempfile

p=argparse.ArgumentParser();p.add_argument("candidate",type=Path);a=p.parse_args()
rtl=a.candidate/"rtl/quad_uart_controller.sv"
tb=Path(__file__).parent/"assets/tb_hidden.sv"
with tempfile.TemporaryDirectory() as td:
    out=Path(td)/"sim.vvp"
    env=os.environ.copy();env["PATH"]="/foss/tools/bin:"+env.get("PATH","")
    env["LD_LIBRARY_PATH"]="/foss/tools/iverilog/lib:"+env.get("LD_LIBRARY_PATH","")
    subprocess.run(["iverilog","-g2012","-s","tb_hidden","-o",out,rtl,tb],check=True,env=env)
    r=subprocess.run(["vvp",out],text=True,capture_output=True,env=env)
    print(r.stdout,end="")
    if r.returncode or "HIDDEN_PASS" not in r.stdout: print(r.stderr);raise SystemExit(1)
