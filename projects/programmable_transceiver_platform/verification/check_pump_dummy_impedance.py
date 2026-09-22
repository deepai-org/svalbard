#!/usr/bin/env python3
"""Finite dummy-source diagnostic, without assuming a real bias generator."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pump-dummy-impedance';B=R/'scratch/transceiver-pump-steering'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'steering.spice')==m['baseline_deck_sha256']
record=W/('result.json' if (W/'result.json').exists() else 'progress.json');rows=[]
out=dict(status='pending',completed=False,cases=rows,limitations=['Ideal clocks and output clamp; dummy source has1kohm impedance with optional precharged MIM bank, not a physical voltage generator.','Signed phase scenarios are not process/jitter bounds.','Measured charge sign is not lock/acquisition proof.'])
if record.exists():
 r=json.loads(record.read_text());terminal=record.name=='result.json';out.update(status='terminal' if terminal else 'partial',provenance=r)
 if terminal:assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for c in r['cases']:
  n=c['name'];assert n in ('resistive','reservoir')
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
  d=(W/(n+'.spice')).read_text()
  line='VDUMMY DDRIVE 0 1.08\nRDUMMY DDRIVE DUMMY 1k';assert d.count(line)==1
  d=d.replace(line,'VDUMMY DUMMY 0 1.08').replace(f'/work/{n}.dat','/work/steering.dat')
  if n=='reservoir':
   for line in ('.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical','.include /screen/reference/reservoir_mim.spice','XDC DUMMY 0 pt_ref_reservoir_32','.ic v(DUMMY)=1.08'):
    assert d.count(line+'\n')==1;d=d.replace(line+'\n','')
  assert d==(B/'steering.spice').read_text()
  with (W/(n+'.dat')).open() as f:h=f.readline().lower().split()
  with (B/'steering.dat').open() as f:assert f.readline().lower().split()==h
  a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  done=c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=800e-9 and 'aborted' not in (W/(n+'.log')).read_text().lower();row=dict(name=n,completed=done,actual_stop_ns=float(a[-1,0]*1e9))
  if done:
   w=a[(a[:,0]>=200e-9)&(a[:,0]<=790e-9)];t=w[:,0]
   def v(name):return w[:,h.index(name)]
   def edges(name):
    y=v(name)-1.65;k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));return t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
   ref=edges('v(ref)');fb=edges('v(fb)');assert len(ref)==len(fb)>5
   phase=(ref-fb)*1e12;assert np.max(abs(phase-1))<.01
   for node in ('v(ctrl)',):assert np.max(abs(v(node)-1.08))<1e-9
   residual=v('i(v.xcp.vp)')-v('i(v.xcp.vn)')-v('i(vsense)');assert np.max(abs(residual))<1e-9
   cycles=[]
   for l,u in zip(ref[:-1],ref[1:]):
    x=np.r_[l,t[(t>l)&(t<u)],u]
    q=float(np.trapezoid(np.interp(x,t,v('i(vsense)')),x));cycles.append(q)
   mean=float(np.mean(cycles));row.update(reference_minus_feedback_ps=phase.tolist(),cycle_charge_c=cycles,mean_charge_per_cycle_c=mean,mean_pump_current_a=mean/float(np.mean(np.diff(ref))),correction_sign_consistent_with_positive_vco_gain=bool(mean*np.mean(phase)<0))
   row['dummy_voltage_range_v']=[float(v('v(dummy)').min()),float(v('v(dummy)').max())]
   row['dummy_drive_current_range_a']=[float(v('i(vdummy)').min()),float(v('i(vdummy)').max())]
   # Source current is positive into its positive terminal; resistor current
   # delivered to DUMMY therefore has the opposite sign.
   ohm_error=v('i(vdummy)')+(1.08-v('v(dummy)'))/1000
   row['dummy_resistor_kcl_max_error_a']=float(np.max(abs(ohm_error)))
   assert row['dummy_resistor_kcl_max_error_a']<1e-12
  rows.append(row)
 out['completed']=terminal and len(rows)==2 and all(c['completed'] for c in rows)
(P/'evidence/pump-dummy-impedance.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],rows)
