#!/usr/bin/env python3
"""Verify sensor insertion, KCL, voltage drops, and cycle-integrated branch charge."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pump-branch';B=R/'scratch/transceiver-pump-device'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());out=dict(completed=False,status='running_or_unrecorded',limitations=['Ideal zero-volt sensors are a measurement fixture, not proposed silicon.','Numerical replay differences must be inspected before attributing charge changes.','One clamped nominal history; no autonomous PLL or transistor mechanism qualification.'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('early'+ext))==h
 assert sha(B/'early.spice')==m['baseline_deck_sha256']
 cellpath=P/'analog/pll/charge_pump.spice';assert sha(cellpath)==m['cell_sha256'];cell=cellpath.read_text()
 modified=cell.replace('XPU OUT ','XPU DP ').replace('XND OUT ','XND DNODE ').replace('.ends pt_charge_pump','VP DP OUT 0\nVN OUT DNODE 0\n.ends pt_charge_pump').rstrip()
 d=(W/'early.spice').read_text();extra=' '+' '.join(m['probes']);assert d.count(extra)==2 and d.count(modified)==1
 assert d.replace(extra,'').replace(modified,'.include /screen/pll/charge_pump.spice')==(B/'early.spice').read_text()
 a=np.loadtxt(W/'early.dat',skiprows=1);b=np.loadtxt(B/'early.dat',skiprows=1)
 with (W/'early.dat').open() as f:h=f.readline().lower().split()
 with (B/'early.dat').open() as f:bh=f.readline().lower().split()
 assert h==bh+m['probes'] and a.shape[1]==37 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and np.all(np.diff(b[:,0])>0)
 done=r['returncode']==0 and not r['timed_out'] and a[-1,0]+1e-21>=800e-9 and 'aborted' not in (W/'early.log').read_text().lower()
 out.update(status='terminal',completed=done,provenance=r)
 if done:
  w=a[(a[:,0]>=200e-9)&(a[:,0]<=790e-9)];t=w[:,0]
  def v(n):return w[:,h.index(n)]
  errors={n:float(np.max(abs(v(n)-np.interp(t,b[:,0],b[:,bh.index(n)])))) for n in bh[1:]}
  drop=max(float(np.max(abs(v(n)-v('v(ctrl)')))) for n in ('v(xcp.dp)','v(xcp.dnode)'));assert drop<1e-9
  kcl=v('i(v.xcp.vp)')-v('i(v.xcp.vn)')-v('i(vsense)');assert np.max(abs(kcl))<1e-9
  y=v('v(ref)')-1.65;k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));edges=t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
  x=np.r_[edges[0],t[(t>edges[0])&(t<edges[-1])],edges[-1]];cycles=len(edges)-1
  q=lambda n:float(np.trapezoid(np.interp(x,t,v(n)),x))/cycles
  charges={n:q(n) for n in ('i(v.xcp.vp)','i(v.xcp.vn)','i(vsense)','@m.xcp.xpu.m0[id]','@m.xcp.xnd.m0[id]')}
  assert abs(charges['i(v.xcp.vp)']-charges['i(v.xcp.vn)']-charges['i(vsense)'])<1e-21
  oriented={}
  for device,sensor in (('xpu','i(v.xcp.vp)'),('xnd','i(v.xcp.vn)')):
   raw=v(f'@m.xcp.{device}.m0[id]');vd=v(f'@m.xcp.{device}.m0[vds]')
   oriented_q=float(np.trapezoid(np.interp(x,t,raw*np.sign(vd)),x))/cycles
   oriented[device]=dict(vds_oriented_id_charge_c=oriented_q,terminal_sensor_charge_c=charges[sensor],difference_c=charges[sensor]-oriented_q)
  out['orientation_diagnostic']=oriented
  out.update(original_vectors_identical=bool(np.array_equal(a[:,:33],b)),late_interpolated_max_errors=errors,maximum_sensor_drop_v=drop,kcl_max_error_a=float(np.max(abs(kcl))),reference_cycles=cycles,charge_per_cycle_c=charges)
(P/'evidence/pump-branch.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
