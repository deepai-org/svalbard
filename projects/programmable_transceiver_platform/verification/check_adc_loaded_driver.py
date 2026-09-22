#!/usr/bin/env python3
"""Validate reduced fixture and compare first acquisition with full ideal-reference ADC."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--damping",action="store_true");ap.add_argument("--two-k",action="store_true");args=ap.parse_args()
if args.two_k:args.damping=True
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-loaded-driver'
if args.damping:W=R/'scratch/transceiver-adc-loaded-driver-damping'
if args.two_k:W=R/'scratch/transceiver-adc-loaded-driver-damping2k'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(W/'loaded.spice')==m['deck_sha256_before']
d=(W/'loaded.spice').read_text()
assert 'XS IP IN HP HN VDD 0 VDD 0 wifi_if_transmission_gate' in d
assert 'XD HP HN VH VL '+' '.join(['0 VDD']*7+['VDD 0'])+' VDD 0 pt_cdac8_mim' in d
if args.damping:
 base=R/'scratch/transceiver-adc-loaded-driver/loaded.spice'
 assert sha(base)==m['baseline_deck_sha256']
 cell=(P/'analog/adc/sample_driver_headroom.spice').read_text().replace('RC X Z 100','RC X Z 2k' if args.two_k else 'RC X Z 1k')
 assert d.replace(cell,'.include /screen/adc/sample_driver_headroom.spice')==base.read_text()
out=dict(status='pending',completed=False)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('loaded'+ext))==h
 with (W/'loaded.dat').open() as f:header=f.readline().lower().split()
 assert header==['time']+next(l for l in d.splitlines() if l.startswith('wrdata ')).lower().split()[2:]
 a=np.loadtxt(W/'loaded.dat',skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 complete=r['returncode']==0 and not r['timed_out'] and a[-1,0]+1e-21>=100e-9 and 'aborted' not in (W/'loaded.log').read_text().lower()
 out.update(status='terminal',completed=bool(complete),provenance=r,actual_stop_ns=a[-1,0]*1e9)
 if complete:
  cases=[]
  for start,target in [(60,-.4),(80,.4)]:
   w=a[(a[:,0]>=(start+.1)*1e-9)&(a[:,0]<=(start+9.9)*1e-9)];t=w[:,0];metrics={}
   for name,p,n in [('driver','ip','in'),('plate','hp','hn')]:
    y=w[:,header.index('v('+p+')')]-w[:,header.index('v('+n+')')]
    k=int(np.argmax((y-target)*np.sign(target)))
    tail=(t>=(start+9.7)*1e-9)&(t<=(start+9.85)*1e-9)
    metrics[name]=dict(overshoot_v=float((y[k]-target)*np.sign(target)),peak_time_ns=t[k]*1e9,final_2ns_error_range_v=[float((y[t>=(start+8)*1e-9]-target).min()),float((y[t>=(start+8)*1e-9]-target).max())],near_10ns_mean_v=float(np.trapezoid(y[tail],t[tail])/(t[tail][-1]-t[tail][0])))
   cases.append(dict(step_ns=start,metrics=metrics))
  out['cases']=cases
  b=R/'scratch/transceiver-adc-shared-iq-fixed-references';br=json.loads((b/'result.json').read_text())
  for ext,h in br['artifacts_sha256'].items():assert sha(b/('frames'+ext))==h
  with (b/'frames.dat').open() as f:bh=f.readline().lower().split()
  ba=np.loadtxt(b/'frames.dat',skiprows=1);assert np.all(np.diff(ba[:,0])>0)
  t=a[(a[:,0]>=60e-9)&(a[:,0]<=70e-9),0];comparison={}
  for name,p,n in [('driver','ip','in'),('plate','hp','hn')]:
   v=lambda arr,h,node:arr[:,h.index('v('+node+')')]
   delta=np.interp(t,a[:,0],v(a,header,p)-v(a,header,n))-np.interp(t,ba[:,0],v(ba,bh,p)-v(ba,bh,n))
   comparison[name]=float(abs(delta).max())
  out['first_acquisition_max_waveform_difference_v']=comparison;out['baseline_artifacts_sha256']=br['artifacts_sha256']
out['limitations']=['Reduction removes comparator, control switching, Q channel and finite code-driver impedance; not full ADC qualification.','Second step at80ns is diagnostic, not20MS/s conversion operation.','Overshoot is not proof of small-signal instability; no loop phase margin measured.']
(P/('evidence/adc-loaded-driver-damping2k.json' if args.two_k else 'evidence/adc-loaded-driver-damping.json' if args.damping else 'evidence/adc-loaded-driver.json')).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('provenance','baseline_artifacts_sha256')},indent=2))
