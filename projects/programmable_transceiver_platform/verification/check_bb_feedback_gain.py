#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-bb-feedback-gain'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after'];rows=[]
assert {(x['common_mode_v'],x['feedback_ohm']) for x in r['cases']}=={(c,f) for c in (.9,1.177) for f in (20000,40000)}
for c in r['cases']:
 assert c['returncode']==0
 n=c['name']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
 log=(W/(n+'.log')).read_text().lower();assert not any(x in log for x in ['error','aborted','warning'])
 def read(ext):
  with (W/(n+ext)).open() as f:h=f.readline().lower().split()
  a=np.loadtxt(W/(n+ext),skiprows=1,ndmin=2);assert a.shape[1]==len(h) and np.isfinite(a).all();return h,a
 h,a=read('.dat');oh,op=read('-op.dat');assert h==['frequency','gr','gi','ir','ii'] and len(a)==100 and np.all(np.diff(a[:,0])>0)
 assert abs(a[0,0]-1e6)<1 and abs(a[-1,0]-1e8)<1
 gain=a[:,1]+1j*a[:,2];gates=a[:,3]+1j*a[:,4]
 points=[]
 for f in (1e6,5e6,10e6,20e6):
  i=int(np.argmin(abs(a[:,0]-f)));assert abs(a[i,0]-f)<1
  points.append(dict(frequency_hz=f,source_to_output_gain=float(abs(gain[i])),input_terminal_to_output_gain=float(abs(gain[i]/gates[i]))))
 same=None
 if c['feedback_ohm']==20000:
  old=R/'scratch/transceiver-bb-interface'/f"cm{c['common_mode_v']:g}_r1000.dat"
  prior=json.loads((old.parent/'result.json').read_text());pc=next(x for x in prior['cases'] if x['name']==old.stem)
  assert sha(old)==pc['artifacts_sha256']['.dat'];same=bool(np.array_equal(a,np.loadtxt(old,skiprows=1)));assert same
 rows.append(dict(name=n,points=points,output_common_mode_v=float((op[0,oh.index('v(op)')]+op[0,oh.index('v(on)')])/2),supply_power_w=float(-3.3*op[0,oh.index('i(vdd)')]),original_baseline_identical=same,peak_gain=float(abs(gain).max()),peak_frequency_hz=float(a[abs(gain).argmax(),0])))
out=dict(completed=True,cases=rows,provenance=r,limitations=['Stationary small-signal fixture, ideal2.25V bias and1kohm source per leg; not switched mixer loading.','No return-ratio stability, noise, large-signal swing or programmable resistor implementation qualification.','Increasing feedback resistance is not assumed to scale gain proportionally.'])
(P/'evidence/bb-feedback-gain.json').write_text(json.dumps(out,indent=2)+'\n')
for x in rows:print(x['name'],x['points'],x['output_common_mode_v'])
