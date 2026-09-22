#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-vco-supply';B=R/'scratch/transceiver-vco-split-tuning'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'v1.08.spice')==m['baseline_deck_sha256']
out=dict(completed=False,status='pending',cases=[],limitations=['Deterministic seeded, prebiased open-loop supply sensitivity only; not random jitter or PLL rejection.','Only PLLVDD changes; fixed ideal biases and other supplies. No process or mismatch coverage.'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'];out['status']='terminal';out['provenance']=r
 assert [c['supply_v'] for c in r['cases']]==[3.29,3.3,3.31]
 for c in r['cases']:
  name=c['name'];expected=(B/'v1.08.spice').read_text().replace('VPLL PLLVDD 0 3.3',f"VPLL PLLVDD 0 {c['supply_v']}").replace('/work/v1.08.dat',f'/work/{name}.dat')
  assert (W/(name+'.spice')).read_text()==expected
  for e,h in c['artifacts_sha256'].items():assert sha(W/(name+e))==h
  row=dict(supply_v=c['supply_v'],completed=False)
  if (W/(name+'.dat')).exists():
   with (W/(name+'.dat')).open() as f:header=f.readline().lower().split()
   a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==len(header) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
   row.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=41e-9 and 'aborted' not in (W/(name+'.log')).read_text().lower()))
   if row['completed']:
    w=a[(a[:,0]>=20e-9)&(a[:,0]<=40e-9)];t=w[:,0];v=w[:,header.index('cml')];idx=np.flatnonzero((v[:-1]<0)&(v[1:]>=0));assert len(idx)>40
    edges=t[idx]-v[idx]*(t[idx+1]-t[idx])/(v[idx+1]-v[idx]);gate=w[:,header.index('v(xrx.gate)')];assert gate.min()>1.4 and gate.max()<1.6
    row.update(frequency_hz=float((len(edges)-1)/(edges[-1]-edges[0])),crossings=len(edges),gate_range_v=[float(gate.min()),float(gate.max())])
    row['subwindows']=[]
    for lo,hi in ((20,30),(30,40)):
     e=edges[(edges>=lo*1e-9)&(edges<=hi*1e-9)];assert len(e)>20
     row['subwindows'].append(dict(window_ns=[lo,hi],crossings=len(e),frequency_hz=float((len(e)-1)/(e[-1]-e[0]))))
    if c['supply_v']==3.3:row['nominal_vectors_bit_identical']=bool(np.array_equal(a,np.loadtxt(B/'v1.08.dat',skiprows=1)))
  out['cases'].append(row)
 out['completed']=all(c['completed'] for c in out['cases'])
 if out['completed']:out['local_slopes_hz_per_v']=[(b['frequency_hz']-a['frequency_hz'])/(b['supply_v']-a['supply_v']) for a,b in zip(out['cases'],out['cases'][1:])]
 if out['completed']:
  out['subwindow_slopes_hz_per_v']=[dict(window_ns=[lo,hi],slopes=[(b['subwindows'][j]['frequency_hz']-a['subwindows'][j]['frequency_hz'])/(b['supply_v']-a['supply_v']) for a,b in zip(out['cases'],out['cases'][1:])]) for j,(lo,hi) in enumerate(((20,30),(30,40)))]
(P/'evidence/vco-supply-screen.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],out.get('local_slopes_hz_per_v'))
