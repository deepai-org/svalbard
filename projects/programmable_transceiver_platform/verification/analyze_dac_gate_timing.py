#!/usr/bin/env python3
"""Measure physical DAC gate timing; threshold states are not channel currents."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-dynamic'
raw=json.loads((W/'result.json').read_text());assert raw['source_sha256_before']==raw['source_sha256_after']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def crossing(t,v,up):
 ix=np.flatnonzero(((v[:-1]<1.65)&(v[1:]>=1.65)) if up else ((v[:-1]>1.65)&(v[1:]<=1.65)))
 return t[ix]+(1.65-v[ix])*(t[ix+1]-t[ix])/(v[ix+1]-v[ix])
rows=[]
for c in raw['cases']:
 name=c['name']
 for ext,digest in c['artifacts_sha256'].items():assert sha(W/(name+ext))==digest
 wave=W/(name+'.dat')
 expected=['time','v(op)','v(on)','v(bn)','i(vdrv)']+[x for i in range(8) for x in (f'v(b{i})',f'v(b{i}b)')]+[f'v(d{i})' for i in range(8)]
 with wave.open() as f:assert f.readline().lower().split()==expected
 a=np.loadtxt(wave,skiprows=1);assert a.shape[1]==29 and np.isfinite(a).all()
 events=[]
 for start,reverse in ((30,False),(55,True)):
  w=a[(a[:,0]>=(start-1)*1e-9)&(a[:,0]<=(start+3)*1e-9)];t=w[:,0];bits=[]
  for bit in range(8):
   up=(bit==7)!=reverse
   command=crossing(t,w[:,21+bit],up);true=crossing(t,w[:,5+2*bit],up);comp=crossing(t,w[:,6+2*bit],not up)
   assert len(command)==len(true)==len(comp)==1
   bits.append(dict(bit=bit,command_crossing_ns=float(command[0]*1e9),true_crossing_ns=float(true[0]*1e9),complement_crossing_ns=float(comp[0]*1e9),true_delay_ps=float((true[0]-command[0])*1e12),complement_delay_ps=float((comp[0]-command[0])*1e12),complement_minus_true_ps=float((comp[0]-true[0])*1e12)))
  b=w[:,5:21:2]>1.65;bb=w[:,6:21:2]>1.65;weights=2**np.arange(8)
  events.append(dict(command_start_ns=start,bits=bits,max_weighted_both_high_units=int(np.max((b&bb)@weights)),max_weighted_both_low_units=int(np.max((~b&~bb)@weights))))
 rows.append(dict(name=name,events=events))
r=dict(status='measured_existing_DAC_gate_timing',cases=rows,source_manifest=raw['source_sha256_before'],limitations=['1.65V crossings describe gate timing, not FET conduction thresholds or current partition.', 'Both-high/both-low weighted counts are logical proxies only; finite edge slopes and source-node motion matter.', 'Nominal six-case existing waveforms; no driver modification or glitch-cause isolation claimed.'])
(P/'evidence/current-dac-gate-timing.json').write_text(json.dumps(r,indent=2)+'\n')
for c in rows:
 print(c['name'],[(round(e['bits'][7]['true_delay_ps'],2),round(e['bits'][7]['complement_delay_ps'],2),e['max_weighted_both_high_units'],e['max_weighted_both_low_units']) for e in c['events']])
