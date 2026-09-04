#!/usr/bin/env python3
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
gold=root/"solution/golden_output";mini=root/"solution/mini_incomplete"
subprocess.run(["python3",root/"environment/input_files/test_visible/run.py",gold],check=True)
subprocess.run(["python3",root/"tests/run_functional.py",gold],check=True)
bad=subprocess.run(["python3",root/"tests/run_functional.py",mini],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if bad.returncode==0:raise SystemExit("negative control unexpectedly passed")
rtl=gold/"rtl/quad_uart_controller.sv"
subprocess.run(["yosys","-q","-p",f"read_verilog -sv {rtl}; synth -top quad_uart_controller; check"],check=True)
print("SELFTEST_PASS")
