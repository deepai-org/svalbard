#!/usr/bin/env python3
import hashlib,json,sys
ASYM="--asymmetric" in sys.argv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-quadrature-rc-asymmetric' if ASYM else 'scratch/transceiver-quadrature-rc')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
assert m.get('asymmetric',False)==ASYM
assert [(c['load_f'],c.get('q_load_f',c['load_f'])) for c in r['cases']]==([(25e-15,25e-15),(25e-15,100e-15),(100e-15,25e-15)] if ASYM else [(x,x) for x in (0,25e-15,100e-15)])
rows=[]
for c in r['cases']:
 assert c['returncode']==0
 if ASYM:
  baseline=R/'scratch/transceiver-quadrature-rc'
  prior=json.loads((baseline/'result.json').read_text())
  control=next(x for x in prior['cases'] if x['name']=='load25')
  assert sha(baseline/'load25.spice')==control['artifacts_sha256']['.spice']
  expected=(baseline/'load25.spice').read_text().replace('/work/load25.dat',f"/work/{c['name']}.dat")
  for node in ('IP','IN','QP','QN'):
   cap=c['load_f'] if node.startswith('I') else c['q_load_f']
   old=f'C{node} {node} CM 2.5e-14';assert expected.count(old)==1
   expected=expected.replace(old,f'C{node} {node} CM {cap}')
  assert (W/(c['name']+'.spice')).read_text()==expected
  if c['load_f']==c['q_load_f']==25e-15:
   assert sha(W/(c['name']+'.dat'))==control['artifacts_sha256']['.dat']
 for e,h in c['artifacts_sha256'].items():assert sha(W/(c['name']+e))==h
 assert c['deck_sha256_before']==c['artifacts_sha256']['.spice']
 with (W/(c['name']+'.dat')).open() as f:assert f.readline().lower().split()==['frequency','ir','ii','qr','qi']
 a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1);assert a.shape==(41,5) and np.isfinite(a).all() and np.allclose(a[:,0],np.linspace(2e9,3e9,41),rtol=1e-12,atol=0)
 i=a[:,1]+1j*a[:,2];q=a[:,3]+1j*a[:,4];phase=np.angle(q/i,deg=True);gain=abs(q/i)
 k=20;assert a[k,0]==2.5e9
 rows.append(dict(load_ff=c['load_f']*1e15,q_load_ff=c.get('q_load_f',c['load_f'])*1e15,at_2p5ghz=dict(i_gain=float(abs(i[k])),q_gain=float(abs(q[k])),q_over_i=float(gain[k]),q_lead_degrees=float(phase[k])),phase_range_deg=[float(phase.min()),float(phase.max())],gain_ratio_range=[float(gain.min()),float(gain.max())]))
out=dict(completed=True,cases=rows,provenance=r,limitations=['AC only with ideal1.5V common mode and25ohm source per leg; no oscillator or actual buffer/mixer load.','Single resistor geometry and nominal corner; lumped load scenarios are not process bounds.','Quadrature phase alone does not establish usable amplitude, edge timing, noise or image rejection.'])
(P/('evidence/quadrature-rc-asymmetric.json' if ASYM else 'evidence/quadrature-rc.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
