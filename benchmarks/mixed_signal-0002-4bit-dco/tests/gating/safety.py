from pathlib import Path
import json,re
import rewardkit as rk

@rk.criterion(description="The candidate contains only the three bounded, self-contained deliverables.",shared=True)
def safe(workspace:Path)->bool:
  root=workspace/"output";required={"analog/dco4.spice","layout/dco4.gds","integration/dco4.json"}
  try:files={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
  except OSError:return False
  if files!=required:return False
  spice=root/"analog/dco4.spice";gds=root/"layout/dco4.gds";manifest=root/"integration/dco4.json"
  if any(p.is_symlink() for p in (spice,gds,manifest)):return False
  if spice.stat().st_size>2_000_000 or gds.stat().st_size>20_000_000 or manifest.stat().st_size>4096:return False
  text=spice.read_text(errors="replace")
  return not re.search(r"(?im)^\s*\.(control|shell|exec|include|lib)\b",text)
@rk.criterion(description="All schematic and physical eligibility gates passed.",shared=True)
def eligible(workspace:Path)->bool:
  del workspace
  try:e=json.loads(Path("/logs/verifier/evidence.json").read_text())
  except Exception:return False
  return e=={"physical":True,"schematic":True}
rk.safe(weight=1.0,name="G1");rk.eligible(weight=1.0,name="G2")
