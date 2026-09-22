#!/usr/bin/env python3
"""Check connected follower experiment, reporting rather than assuming stability."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pump-follower';B=R/'scratch/transceiver-pump-dummy-impedance'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'reservoir.spice')==m['baseline_deck_sha256']
d=(W/'follower.spice').read_text();assert d.count(m['replacement_new'])==1
d=d.replace(m['replacement_new'],m['replacement_old']).replace('/work/follower.dat','/work/reservoir.dat')
d='\n'.join(line.removesuffix(m['extra_probes']) if line.startswith(('save ','wrdata ')) else line for line in d.split('\n'))
assert d==(B/'reservoir.spice').read_text()
out=dict(status='pending',completed=False,limitations=m['limitations'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());out.update(status='terminal',provenance=r)
 assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for path,h in r['source_sha256_before'].items():
  if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('follower'+ext))==h
 if '.dat' in r['artifacts_sha256']:
  with (W/'follower.dat').open() as f:h=f.readline().lower().split()
  a=np.loadtxt(W/'follower.dat',skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  out['actual_stop_ns']=float(a[-1,0]*1e9)
  out['completed']=bool(r['returncode']==0 and not r['timed_out'] and a[-1,0]+1e-21>=800e-9 and 'aborted' not in (W/'follower.log').read_text().lower())
  if out['completed']:
   rows=[]
   for low,high in ((200e-9,450e-9),(550e-9,790e-9)):
    w=a[(a[:,0]>=low)&(a[:,0]<=high)];t=w[:,0]
    def v(n):return w[:,h.index(n)]
    def edges(n):
     y=v(n)-1.65;k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));return t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
    ref=edges('v(ref)');fb=edges('v(fb)');assert len(ref)==len(fb)>2
    assert max(abs((ref-fb)*1e12-1))<.01
    assert max(abs(v('v(ctrl)')-1.08))<1e-9
    err=v('i(v.xcp.vp)')-v('i(v.xcp.vn)')-v('i(vsense)');assert max(abs(err))<1e-9
    q=[]
    for l,u in zip(ref[:-1],ref[1:]):
     x=np.r_[l,t[(t>l)&(t<u)],u];q.append(float(np.trapezoid(np.interp(x,t,v('i(vsense)')),x)))
    power=float(-3.3*np.trapezoid(v('i(vdrv)'),t)/(t[-1]-t[0]))
    rows.append(dict(window_ns=[low*1e9,high*1e9],dummy_range_v=[float(min(v('v(dummy)'))),float(max(v('v(dummy)')))],cycle_charge_c=q,driver_supply_power_w=power,driver_current_range_a=[float(min(v('i(vdummy)'))),float(max(v('i(vdummy)')))],bias_n_range_v=[float(min(v('v(bdn)'))),float(max(v('v(bdn)')))],bias_p_range_v=[float(min(v('v(bdp)'))),float(max(v('v(bdp)')))]))
   out['windows']=rows
(P/'evidence/pump-follower.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out if out['status']=='pending' else {k:v for k,v in out.items() if k!='provenance'},indent=2))
