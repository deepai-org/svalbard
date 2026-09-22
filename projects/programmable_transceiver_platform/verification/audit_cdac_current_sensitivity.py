#!/usr/bin/env python3
"""Compare current observables on native grids, without declaring convergence."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
windows=[(60,109.9),(110,159.9),(160,209.9),(122.5,125.35)]
roots={'default':R/'scratch/transceiver-cdac-branch-replay','reltol':R/'scratch/transceiver-cdac-probe-reltol/probed','combined':R/'scratch/transceiver-cdac-probe-convergence/probed'}
rows=[]
for name,root in roots.items():
 r=json.loads((root/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(root/('frames'+ext))==h
 with (root/'frames.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(root/'frames.dat',skiprows=1);t=a[:,0]
 assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]+1e-21>=209.9e-9
 def v(n):return a[:,h.index(n)]
 cases=[]
 for rail in ('h','l'):
  demand=v(f'i(vref{rail}_del)')-v(f'i(vref{rail}_res)')
  branches=sum(v(f'i(v.{inst}.x{side}{bit}.x{rail}.vport)') for inst in ('xd','xq_d') for side in ('p','n') for bit in range(8))
  residual=float(abs(demand-branches).max())
  if rail=='h':assert residual<1e-9
  for lo,hi in windows:
   mask=(t>=lo*1e-9)&(t<=hi*1e-9);assert mask.any()
   ix=np.flatnonzero(mask);peak=ix[int(np.argmax(abs(demand[mask])))];tt=np.r_[lo*1e-9,t[(t>lo*1e-9)&(t<hi*1e-9)],hi*1e-9]
   yy=np.interp(tt,t,demand)
   cases.append(dict(rail=rail,window_ns=[lo,hi],peak_signed_a=float(demand[peak]),peak_time_ns=float(t[peak]*1e9),signed_charge_c=float(np.trapezoid(yy,tt)),absolute_charge_c=float(np.trapezoid(abs(yy),tt)),branch_sum_max_residual_a=residual))
 rows.append(dict(setting=name,artifacts_sha256=r['artifacts_sha256'],cases=cases))
changes=[]
for j,base in enumerate(rows[0]['cases']):
 for candidate in rows[1:]:
  other=candidate['cases'][j];assert other['rail']==base['rail'] and other['window_ns']==base['window_ns']
  changes.append(dict(setting=candidate['setting'],rail=base['rail'],window_ns=base['window_ns'],peak_change_a=other['peak_signed_a']-base['peak_signed_a'],signed_charge_change_c=other['signed_charge_c']-base['signed_charge_c'],absolute_charge_change_c=other['absolute_charge_c']-base['absolute_charge_c']))
out=dict(cases=rows,changes_from_default=changes,limitations=['Native-grid peaks and endpoint-interpolated charge; no shifted waveform alignment.','No new acceptance threshold or numerical convergence claim.','Combined-tolerance unprobed parent failed startup; its probed result is sensitivity evidence only.','Original default probe reproduction remains failed.','Low-rail residual includes four dummy capacitors; high-rail KCL is independently checked.','Terminal currents include displacement; neither peaks nor charge alone prove conductive overlap.'])
(P/'evidence/cdac-current-sensitivity.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:
 print(row['setting'],[(x['rail'],x['window_ns'],round(x['peak_signed_a']*1e3,4),round(x['signed_charge_c']*1e12,5)) for x in row['cases']])
print('Max absolute peak delta A',max(abs(x['peak_change_a']) for x in changes))
print('Max signed charge delta C',max(abs(x['signed_charge_change_c']) for x in changes))
