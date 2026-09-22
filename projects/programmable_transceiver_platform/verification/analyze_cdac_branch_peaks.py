#!/usr/bin/env python3
"""Rank terminal-current contributions, retaining gates and opposing rail currents."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--reltol",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-cdac-branch-replay';E=P/'evidence/cdac-branch-replay.json'
if args.reltol:
 W=R/'scratch/transceiver-cdac-probe-reltol/probed';E=P/'evidence/cdac-probe-reltol.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads(E.read_text())
if args.reltol:
 assert e['completed'] and e['matched_pair']['below_original_10uv_limit'] and e['codes_match_all_runs'] and e['high_rail_kcl_verified']
 for case in ('baseline','probed'):
  root=W.parent/case
  assert sha(root/'manifest.json')==e['manifest_sha256'][case]
  assert sha(root/'result.json')==e['cases'][case]['result_sha256']
 r=json.loads((W/'result.json').read_text())
else:
 assert e['completed'] and e['analog_reproduction_verified'] and e['codes_match'] and e['high_rail_kcl_verified'],'Branch replay must pass diagnostic gates'
 r=e['provenance']
for ext,h in r['artifacts_sha256'].items():assert sha(W/('frames'+ext))==h
with (W/'frames.dat').open() as f:h=f.readline().lower().split()
a=np.loadtxt(W/'frames.dat',skiprows=1);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
def v(n):return a[:,h.index(n)]
demand=v('i(vrefh_del)')-v('i(vrefh_res)');rows=[]
for lo,hi in [(60,109.9),(110,159.9),(160,209.9),(122.5,125.35)]:
 ix=np.flatnonzero((t>=lo*1e-9)&(t<=hi*1e-9));k=ix[int(np.argmax(demand[ix]))];ports=[];bybit=[]
 for bit in range(8):
  total=0.;series=np.zeros_like(t)
  for inst,prefix in [('xd',''),('xq_d','q_')]:
   for side in ['p','n']:
    path=f'{inst}.x{side}{bit}';ih=float(v(f'i(v.{path}.xh.vport)')[k]);il=float(v(f'i(v.{path}.xl.vport)')[k]);total+=ih;series+=v(f'i(v.{path}.xh.vport)')
    ports.append(dict(channel=inst,bit=bit,side=side,high_a=ih,low_a=il,bottom_v=float(v(f'v({path}.bot)')[k]),b_v=float(v(f'v({prefix}b{bit})')[k]),bb_v=float(v(f'v({prefix}b{bit}b)')[k])))
  tt=np.r_[lo*1e-9,t[(t>lo*1e-9)&(t<hi*1e-9)],hi*1e-9];yy=np.interp(tt,t,series)
  bybit.append(dict(bit=bit,high_current_a=total,signed_high_charge_c=float(np.trapezoid(yy,tt)),absolute_high_charge_c=float(np.trapezoid(abs(yy),tt))))
 assert abs(sum(x['high_current_a'] for x in bybit)-float(demand[k]))<1e-9
 demand_charge=float(np.trapezoid(np.interp(tt,t,demand),tt))
 assert abs(sum(x['signed_high_charge_c'] for x in bybit)-demand_charge)<1e-18
 ports.sort(key=lambda x:abs(x['high_a']),reverse=True);bybit.sort(key=lambda x:abs(x['high_current_a']),reverse=True)
 rows.append(dict(window_ns=[lo,hi],peak_time_ns=float(t[k]*1e9),high_demand_a=float(demand[k]),high_rail_v=float(v('v(vh)')[k]),low_rail_v=float(v('v(vl)')[k]),bit_contributions=bybit,ports=ports))
out=dict(status='matched_reltol_branch_diagnostic' if args.reltol else 'validated_branch_peak_diagnostic',replay_evidence_sha256=sha(E),cases=rows,limitations=['Signed reference-port currents contain displacement; equal opposite currents are not proof of conductive crossover.','Integrated terminal charge is not dissipated energy or proof of a causal redesign.','RelTol matched probe agreement does not establish full numerical convergence; default gate remains failed.','Negative-side selector gate roles are swapped relative to positive side; B/BB reported as actual driver outputs.'])
(P/'evidence'/('cdac-branch-peaks-reltol.json' if args.reltol else 'cdac-branch-peaks.json')).write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['peak_time_ns'],r['high_demand_a'],r['bit_contributions'][:3],r['ports'][:2])
