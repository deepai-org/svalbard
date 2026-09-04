from pathlib import Path
import json,re
import rewardkit as rk
BAD=(re.compile(r"\$system\b",re.I),re.compile(r"DPI-C",re.I),re.compile(r"`include\s+[\"'](?:/|\.\.)"))
@rk.criterion(description="The candidate is one bounded, self-contained SystemVerilog source.",shared=True)
def safe(workspace:Path)->bool:
  p=workspace/"output/rtl/quad_uart_controller.sv"
  try:t=p.read_text()
  except OSError:return False
  return p.is_file() and not p.is_symlink() and len(t)<=2_000_000 and not any(x.search(t) for x in BAD)
@rk.criterion(description="All functional and physical eligibility gates passed.",shared=True)
def eligible(workspace:Path)->bool:
  del workspace
  try:e=json.loads(Path("/logs/verifier/evidence.json").read_text())
  except Exception:return False
  return e=={"functional":True,"physical":True}
rk.safe(weight=1.0,name="G1");rk.eligible(weight=1.0,name="G2")
