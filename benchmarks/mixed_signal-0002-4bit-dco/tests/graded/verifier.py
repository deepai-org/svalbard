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
    s=subprocess.run(["python3","/tests/characterize.py",candidate,"--json",log/"schematic.json","--jobs","4"],text=True,capture_output=True)
    (log/"schematic.log").write_text(s.stdout+s.stderr)
    p=subprocess.run(["python3","/tests/physical/run_gf180.py",candidate,"--work",log/"physical","--jobs","4"],text=True,capture_output=True)
    (log/"physical.log").write_text(p.stdout+p.stderr)
    CACHE={"schematic":s.returncode==0,"physical":p.returncode==0}
    (log/"evidence.json").write_text(json.dumps(CACHE,sort_keys=True)+"\n")
    return CACHE
@rk.criterion(description="The submitted GF180 circuit passes enable, all-code, and SS/TT/FF characterization.",shared=True)
def schematic(workspace:Path)->bool:return evidence(workspace)["schematic"]
@rk.criterion(description="The GDS passes interface, non-density DRC, LVS, and full-RC extracted TT checks.",shared=True)
def physical(workspace:Path)->bool:return evidence(workspace)["physical"]
rk.schematic(weight=4.0,name="R1");rk.physical(weight=6.0,name="R2")
