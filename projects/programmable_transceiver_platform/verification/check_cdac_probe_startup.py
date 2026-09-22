#!/usr/bin/env python3
"""Verify the declared startup matrix, including failed and pending cases."""
import hashlib
import json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3]
P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-cdac-probe-startup'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
settings={'default':'','reltol':'option reltol=1e-5','abstol':'option abstol=1e-14','vntol':'option vntol=1e-8','combined':'option reltol=1e-5 abstol=1e-14 vntol=1e-8'}
rows=[]
for circuit,parent in [('baseline','transceiver-adc-reference-current'),('probed','transceiver-cdac-branch-replay')]:
 for variant,option in settings.items():
  case=variant+'-'+circuit; root=W/case
  row=dict(case=case,status='pending',completed=False)
  if (root/'result.json').exists():
   m=json.loads((root/'manifest.json').read_text());r=json.loads((root/'result.json').read_text())
   assert m['settings']==option and m['requested_horizon_ns']==1
   assert sha(root/'frames.spice')==m['deck_sha256_before']
   old=R/'scratch'/parent/'frames.spice';assert sha(old)==m['parent_deck_sha256']
   deck=(root/'frames.spice').read_text()
   restored=deck.replace('tran 5p 1n 0 5p','tran 5p 209.9n 0 5p').replace(f'wrdata /work/{case}/frames.dat','wrdata /work/frames.dat')
   if option: restored=restored.replace(option+'\n','')
   assert restored==old.read_text()
   assert r['source_sha256_before']==r['source_sha256_after']
   for ext,h in r['artifacts_sha256'].items(): assert sha(root/('frames'+ext))==h
   log=(root/'frames.log').read_text();errors=[l.strip() for l in log.splitlines() if 'timestep too small' in l.lower() or 'aborted' in l.lower()]
   end=None;count=0
   if (root/'frames.dat').exists():
    with (root/'frames.dat').open() as f: header=f.readline().split()
    a=np.loadtxt(root/'frames.dat',skiprows=1,ndmin=2)
    assert a.shape[1]==len(header) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
    end=float(a[-1,0]);count=len(a)
   done=r['returncode']==0 and not r['timed_out'] and not errors and end is not None and end+1e-21>=1e-9
   row.update(status='terminal',completed=done,returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,final_time_s=end,rows=count,elapsed_s=r['elapsed_s'],result_sha256=sha(root/'result.json'))
  rows.append(row)
out=dict(matrix_terminal=all(r['status']=='terminal' for r in rows),cases=rows,limitations=['Startup discriminator only; no full-history accuracy or physical qualification.','Sensitivity to a solver option is not proof of a device-level failure mechanism.'])
(P/'evidence/cdac-probe-startup.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows: print(r['case'],r['status'],r['completed'],r.get('final_time_s'))
