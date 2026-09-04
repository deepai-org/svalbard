#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
def load(p):
  try:v=json.loads(Path(p).read_text());return v if isinstance(v,dict) else None
  except Exception:return None
def num(v):
  try:v=float(v)
  except (TypeError,ValueError):return None
  return v if math.isfinite(v) and 0<=v<=1 else None
ap=argparse.ArgumentParser();ap.add_argument("--graded",required=True);ap.add_argument("--graded-rc",type=int,required=True);ap.add_argument("--gating",required=True);ap.add_argument("--gating-rc",type=int,required=True);ap.add_argument("--out",required=True);a=ap.parse_args()
g=load(a.graded);v=load(a.gating);score=num((g or {}).get("reward"));gates=[num(x) for x in (v or {}).values()]
ok=a.graded_rc==0 and score is not None and a.gating_rc==0 and gates and all(x is not None for x in gates)
veto=bool(ok and min(gates)<1)
Path(a.out).write_text(json.dumps({"graded_score":score or 0.0,"gating":0.0 if veto else 1.0,"reward":score if ok and not veto else 0.0,"verifier_error":0.0 if ok else 1.0},indent=2)+"\n")
