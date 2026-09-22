#!/usr/bin/env python3
"""Localize tolerance sensitivity; no passing criterion is introduced post hoc."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
E=P/'evidence/cdac-probe-reltol.json';e=json.loads(E.read_text());assert e['completed']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(root):
 r=json.loads((root/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(root/('frames'+ext))==h
 with (root/'frames.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(root/'frames.dat',skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 return h,a,r['artifacts_sha256']
rows=[]
for case,old in [('baseline','transceiver-adc-reference-current'),('probed','transceiver-cdac-branch-replay')]:
 h,a,ah=read(R/'scratch/transceiver-cdac-probe-reltol'/case);bh,b,bhash=read(R/'scratch'/old)
 t=a[:,0]
 def v(n):return a[:,h.index(n)]
 def original(n):return np.interp(t,b[:,0],b[:,bh.index(n)])
 metrics={}
 for name in ['v(hp)','v(hn)','v(q_hp)','v(q_hn)','v(vh)','v(vl)','v(ip)','v(in)']:
  err=abs(v(name)-original(name));k=int(err.argmax());windows=[]
  for hold in (70,120,170):
   for bit in range(8):
    lo=hold+5*bit+.2;hi=lo+.15;mask=(t>=lo*1e-9)&(t<=hi*1e-9);assert mask.any()
    windows.append(dict(hold_ns=hold,bit_index=bit,max_error_v=float(err[mask].max())))
  metrics[name]=dict(global_max_error_v=float(err[k]),global_peak_ns=float(t[k]*1e9),worst_predecision=max(windows,key=lambda x:x['max_error_v']),decision_windows=windows)
 held=[]
 for prefix in ('','q_'):
  diff=v(f'v({prefix}hp)')-v(f'v({prefix}hn)');old_diff=original(f'v({prefix}hp)')-original(f'v({prefix}hn)')
  for hold in (70,120,170):
   lo=(hold+.2)*1e-9;hi=(hold+.35)*1e-9
   # Include exact endpoints rather than silently shrinking the integration interval.
   tt=np.r_[lo,t[(t>lo)&(t<hi)],hi]
   now=float(np.trapezoid(np.interp(tt,t,diff),tt)/(hi-lo));prior=float(np.trapezoid(np.interp(tt,t,old_diff),tt)/(hi-lo))
   held.append(dict(channel=prefix or 'i',hold_ns=hold,reltol_held_diff_v=now,default_held_diff_v=prior,change_v=now-prior))
 rows.append(dict(case=case,artifacts_sha256=ah,original_artifacts_sha256=bhash,nodes=metrics,held=held))
out=dict(parent_evidence_sha256=sha(E),cases=rows,limitations=['Post-inspection localization, not an acceptance gate or proof of convergence.','Default trajectories linearly interpolated onto tightened timestamps without time alignment.','No transient-noise, mismatch or ENOB qualification.'])
(P/'evidence/cdac-tolerance-windows.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:
 print(row['case'],'held change max V',max(abs(x['change_v']) for x in row['held']))
 for n in ['v(hp)','v(hn)','v(vh)','v(vl)']:
  q=row['nodes'][n];print(n,q['global_peak_ns'],q['worst_predecision'])
