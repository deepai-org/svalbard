#!/usr/bin/env python3
import hashlib,json,sys
RING="--ring" in sys.argv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-quadrature-ring' if RING else 'scratch/transceiver-quadrature-buffered-transient');B=R/'scratch/transceiver-quadrature-rc-buffered'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rise(t,v):
 k=np.flatnonzero((v[:-1]<0)&(v[1:]>=0));return t[k]-v[k]*(t[k+1]-t[k])/(v[k+1]-v[k])
def duty(t,v):
 a=v[:-1]-1.65;b=v[1:]-1.65;fraction=(a>=0).astype(float)
 up=(a<0)&(b>=0);down=(a>=0)&(b<0)
 fraction[up]=b[up]/(b[up]-a[up]);fraction[down]=a[down]/(a[down]-b[down])
 return float(np.sum(fraction*np.diff(t))/(t[-1]-t[0]))
m=json.loads((W/'manifest.json').read_text());assert sha(B/'load25.spice')==m['baseline_deck_sha256']
out=dict(status='pending',completed=False,cases=[],limitations=['OP-initialized ideal sinusoidal source,25ohm per leg; not ring oscillator or cold startup.','Matched buffers,ideal supplies/CM and lumped loads; no mismatch/noise/process qualification.','Output swing and threshold duty are observations, not declared interface compliance.'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'];out.update(status='terminal',provenance=r)
 assert m.get('ring_mode',False)==RING
 assert [c['single_leg_peak_v'] for c in r['cases']]==([.4] if RING else [.2,.4])
 for c in r['cases']:
  name=c['name'];amp=c['single_leg_peak_v']
  expected=(B/'load25.spice').read_text().split('.control')[0].replace('VP SP 0 DC 1.5 AC .5',f'VP SP 0 SIN(1.5 {amp} 2.5g)').replace('VN SN 0 DC 1.5 AC .5 180',f'VN SN 0 SIN(1.5 {amp} 2.5g 0 0 180)')
  if RING:
   for line in (f'VP SP 0 SIN(1.5 {amp} 2.5g)\n',f'VN SN 0 SIN(1.5 {amp} 2.5g 0 0 180)\n','RP SP P 25\n','RN SN N 25\n'):expected=expected.replace(line,'')
   expected+='.include /screen/pll/ring_vco_split.spice\nVPLL PLLVDD 0 3.3\nVCTRL CTRL 0 1.08\nVREGEN REGEN 0 1.08\nXVCO CTRL REGEN PLLVDD 0 P N pt_split_ring LOAD_L=5.25u CAP_W=4u CAP_L=3u\nCP P 0 25f\nCN N 0 25f\n'
   for stage,vp,vn in [(0,1.718,1.714),(1,1.714,1.718),(2,1.718,1.714)]:expected+=f'.ic v(XVCO.N{stage}P)={vp} v(XVCO.N{stage}N)={vn}\n'
  assert (W/(name+'.spice')).read_text().split('.control')[0]==expected
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
  row=dict(single_leg_peak_v=None if RING else amp,completed=False)
  if (W/(name+'.dat')).exists():
   with (W/(name+'.dat')).open() as f:header=f.readline().lower().split()
   assert header==['time']+[p.lower() for p in m['probes']]
   a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==(17 if RING else 14) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
   row.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=81e-9 and 'aborted' not in (W/(name+'.log')).read_text().lower()))
   if row['completed']:
    row['windows']=[]
    for lo,hi in ((40,60),(60,80)):
     w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=w[:,0]
     def v(node):return w[:,header.index('v('+node.lower()+')')]
     record=dict(window_ns=[lo,hi],outputs={},bias_input_mean_v={node:float(np.trapezoid(v(node),t)/(t[-1]-t[0])) for node in ('BIP','BIN','BQP','BQN')},buffer_power_w=float(np.trapezoid(-3.3*w[:,header.index('i(vbuf)')],t)/(t[-1]-t[0])))
     for node in ('OIP','OIN','OQP','OQN'):record['outputs'][node]=dict(range_v=[float(v(node).min()),float(v(node).max())],duty_above_1p65=duty(t,v(node)))
     ei=rise(t,v('OIP')-v('OIN'));eq=rise(t,v('OQP')-v('OQN'));ph=[]
     period=float(np.mean(np.diff(ei))) if len(ei)>2 else None
     record['i_frequency_hz']=1/period if period else None
     if RING:
      re=rise(t,v('P')-v('N'));record['ring_frequency_hz']=float((len(re)-1)/(re[-1]-re[0])) if len(re)>2 else None
      record['ring_differential_range_v']=[float((v('P')-v('N')).min()),float((v('P')-v('N')).max())]
      record['ring_power_w']=float(np.trapezoid(-3.3*w[:,header.index('i(vpll)')],t)/(t[-1]-t[0]))
     for edge in ei:
      k=np.searchsorted(eq,edge)-1
      if period and k>=0 and edge-eq[k]<period:ph.append((edge-eq[k])/period*360)
     record.update(i_crossings=len(ei),q_crossings=len(eq),q_lead_degrees_range=[float(min(ph)),float(max(ph))] if ph else None,q_lead_degrees_mean=float(np.mean(ph)) if ph else None)
     row['windows'].append(record)
  out['cases'].append(row)
 out['completed']=all(c['completed'] for c in out['cases'])
if RING:out['limitations'][0]='Actual seeded free-running ring with fixed ideal control/regeneration; no PLL or cold-start claim. Mixer loads and actual common-mode/supplies remain absent.'
(P/('evidence/quadrature-ring.json' if RING else 'evidence/quadrature-buffered-transient.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed']);print(json.dumps(out['cases'],indent=2))
