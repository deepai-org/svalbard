#!/usr/bin/env python3
from pathlib import Path
import os,subprocess

root=Path(__file__).resolve().parents[1];gold=root/"solution/golden_output";mini=root/"solution/mini_incomplete"
subprocess.run(["python3",root/"tests/check_interface.py",gold,"--require-gds"],check=True)
bad=subprocess.run(["python3",root/"tests/check_interface.py",mini,"--require-gds"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if bad.returncode==0:raise SystemExit("negative control unexpectedly passed")
if (Path(os.environ.get("PDK_ROOT","/foss/pdks"))/"gf180mcuD").is_dir():
  subprocess.run(["python3",root/"tests/characterize.py",gold,"--tt-only"],check=True)
print("SELFTEST_PASS")
