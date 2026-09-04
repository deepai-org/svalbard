from __future__ import annotations
import json, subprocess, threading
from pathlib import Path
import rewardkit as rk

LOCK=threading.Lock();CACHE=None
def evidence(workspace:Path):
  global CACHE
  with LOCK:
    if CACHE is not None:return CACHE
    candidate=workspace/"output";log=Path("/logs/verifier");log.mkdir(parents=True,exist_ok=True)
    f=subprocess.run(["python3","/tests/run_functional.py",candidate],text=True,capture_output=True)
    (log/"functional.log").write_text(f.stdout+f.stderr)
    p=subprocess.run(["python3","/tests/physical/run_gf180.py",candidate,"--work",log/"physical","--jobs","4"],text=True,capture_output=True)
    (log/"physical.log").write_text(p.stdout+p.stderr)
    CACHE={"functional":f.returncode==0,"physical":p.returncode==0}
    (log/"evidence.json").write_text(json.dumps(CACHE,sort_keys=True)+"\n")
    return CACHE
@rk.criterion(description="SECDED, SDRAM protocol, refresh, RMW, and backpressure pass the hidden suite.",shared=True)
def functional(workspace:Path)->bool:return evidence(workspace)["functional"]
@rk.criterion(description="Mapped replay and routed GF180MCU signoff close at 100 MHz.",shared=True)
def physical(workspace:Path)->bool:return evidence(workspace)["physical"]
rk.functional(weight=4.0,name="R1");rk.physical(weight=6.0,name="R2")
