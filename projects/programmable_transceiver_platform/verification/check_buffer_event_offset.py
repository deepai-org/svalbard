#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-buffer-event-offset';B=R/'scratch/transceiver-buffer-finite-source'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
record=W/('result.json' if (W/'result.json').exists() else 'progress.json');rows=[]
out=dict(completed=False,status='pending',cases=rows,limitations=['Reduced four-FET buffer and electrically separate FB source, not an autonomous PLL.','Offsets change source-event timing; completion does not establish internal solver root cause.','No acquisition, startup or noise qualification.'])
if record.exists():
 r=json.loads(record.read_text());terminal=record.name=='result.json';out.update(status='terminal' if terminal else 'partial',provenance=r)
 if terminal:assert r['source_sha256_before']==r['source_sha256_after'] and sha(B/'buffer.spice')==r['baseline_deck_sha256']
 for c in r['cases']:
  n=c['name'];assert c['delay']=={'early':'99.999n','late':'100.001n'}[n]
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
  d=(W/(n+'.spice')).read_text();line=f"VFB FB 0 PULSE(0 3.3 {c['delay']} 100p 100p 25.5n 51.2n)";assert d.count(line)==1
  assert d.replace(line,'VFB FB 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)').replace(f'/work/{n}.dat','/work/buffer.dat')==(B/'buffer.spice').read_text()
  a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert a.shape[1]==5 and np.isfinite(a).all()
  with (W/(n+'.dat')).open() as f:assert f.readline().lower().split()==['time','v(refraw)','v(ref)','v(fb)','i(vdiv)']
  dt=np.diff(a[:,0]);log=(W/(n+'.log')).read_text().lower()
  completed=c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=800e-9 and 'aborted' not in log
  rows.append(dict(name=n,completed=completed,stop_ns=float(a[-1,0]*1e9),backward_steps=int(sum(dt<0)),equal_printed_steps=int(sum(dt==0)),timestep_error='timestep too small' in log))
 out['completed']=terminal and len(rows)==2 and all(x['completed'] for x in rows)
(P/'evidence/buffer-event-offset.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],rows)
