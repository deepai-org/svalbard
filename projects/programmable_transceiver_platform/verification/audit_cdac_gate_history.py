#!/usr/bin/env python3
"""Physical gate history around measured pulses; logic crossings are not FET thresholds."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-cdac-probe-reltol/probed'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
E=P/'evidence/cdac-branch-peaks-reltol.json';e=json.loads(E.read_text());parent=P/'evidence/cdac-probe-reltol.json';assert sha(parent)==e['replay_evidence_sha256']
r=json.loads((W/'result.json').read_text());assert sha(W/'result.json')==json.loads(parent.read_text())['cases']['probed']['result_sha256']
for ext,h in r['artifacts_sha256'].items():assert sha(W/('frames'+ext))==h
with (W/'frames.dat').open() as f:h=f.readline().lower().split()
a=np.loadtxt(W/'frames.dat',skiprows=1);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
def v(n):return a[:,h.index(n)]
def crossings(y,lo,hi):
 ix=np.flatnonzero((y[:-1]-1.65)*(y[1:]-1.65)<0);out=[]
 for k in ix:
  x=t[k]+(1.65-y[k])*(t[k+1]-t[k])/(y[k+1]-y[k])
  if lo*1e-9<=x<=hi*1e-9:out.append(dict(time_ns=float(x*1e9),direction='rising' if y[k+1]>y[k] else 'falling'))
 return out
rows=[]
for lo,hi in [(122.5,125.35),(157.5,159.9)]:
 for inst,prefix in [('xd',''),('xq_d','q_')]:
  for bit in (6,7):
   gates={name:crossings(v(f'v({prefix}b{bit}{suffix})'),lo,hi) for name,suffix in [('b',''),('bb','b')]}
   ports=[]
   for side in ('p','n'):
    path=f'{inst}.x{side}{bit}';high=v(f'i(v.{path}.xh.vport)');low=v(f'i(v.{path}.xl.vport)');ix=np.flatnonzero((t>=lo*1e-9)&(t<=hi*1e-9));k=ix[int(np.argmax(abs(high[ix])))];top=v(f'v({prefix}h{side})');bottom=v(f'v({path}.bot)')
    ports.append(dict(side=side,peak_time_ns=float(t[k]*1e9),high_a=float(high[k]),low_a=float(low[k]),net_port_a=float(high[k]+low[k]),top_v=float(top[k]),bottom_v=float(bottom[k]),b_v=float(v(f'v({prefix}b{bit})')[k]),bb_v=float(v(f'v({prefix}b{bit}b)')[k]),capacitor_voltage_change_v=float(np.interp(hi*1e-9,t,top-bottom)-np.interp(lo*1e-9,t,top-bottom))))
   rows.append(dict(window_ns=[lo,hi],channel=inst,bit=bit,logic_midpoint_crossings=gates,ports=ports))
out=dict(attribution_sha256=sha(E),cases=rows,limitations=['1.65V crossings are timing markers, not device conduction thresholds.','Port currents include channel and displacement currents; imbalance is not a complete capacitor-current decomposition.','Gate timing observations alone do not prove causality.'])
(P/'evidence/cdac-gate-history.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:
 if row['channel']=='xd':print(row['window_ns'],row['bit'],row['logic_midpoint_crossings'],[(p['side'],p['peak_time_ns'],p['high_a'],p['low_a']) for p in row['ports']])
