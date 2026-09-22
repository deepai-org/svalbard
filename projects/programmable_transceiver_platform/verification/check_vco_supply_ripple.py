#!/usr/bin/env python3
"""Matched crossing-index displacement; retain drift separately from ripple."""
import hashlib,json,sys
FINE="--fine" in sys.argv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-vco-supply-ripple-fine' if FINE else 'scratch/transceiver-vco-supply-ripple');B=R/'scratch/transceiver-vco-split-tuning'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def crossings(t,v):
 idx=np.flatnonzero((v[:-1]<0)&(v[1:]>=0))
 return t[idx]-v[idx]*(t[idx+1]-t[idx])/(v[idx+1]-v[idx])
def fit(t,delay):
 x=(t-t.mean())*1e9;theta=2*np.pi*50e6*(t-20e-9)
 design=np.column_stack((np.ones(len(t)),x,np.sin(theta),np.cos(theta)))
 co,_,rank,_=np.linalg.lstsq(design,delay*1e12,rcond=None);assert rank==4
 residual=delay*1e12-design@co
 return dict(offset_ps=float(co[0]),drift_ps_per_ns=float(co[1]),sin_ps=float(co[2]),cos_ps=float(co[3]),ripple_peak_ps=float(np.hypot(co[2],co[3])),residual_rms_ps=float(np.sqrt(np.mean(residual**2))),crossings=len(t))
# Measurement contract: known periodic displacement plus independent offset/drift.
test_t=np.linspace(40e-9,200e-9,401);theta=2*np.pi*50e6*(test_t-20e-9)
test_y=(7+.03*(test_t-test_t.mean())*1e9+3*np.sin(theta)+4*np.cos(theta))*1e-12
check=fit(test_t,test_y);assert abs(check['ripple_peak_ps']-5)<1e-9 and abs(check['drift_ps_per_ns']-.03)<1e-9 and check['residual_rms_ps']<1e-9
# Exercise interpolation as well as fitting with a sub-timestep displacement.
sample_t=np.arange(0,201e-9,2e-12)
known_delay=.8e-12*np.sin(2*np.pi*50e6*(sample_t-20e-9))
qe=crossings(sample_t,np.sin(2*np.pi*2.50075e9*sample_t-.7))
se=crossings(sample_t,np.sin(2*np.pi*2.50075e9*(sample_t-known_delay)-.7))
assert len(qe)==len(se)
mask=(qe>=40e-9)&(qe<=200e-9)
interpolation_check=fit(qe[mask],(se-qe)[mask])
assert abs(interpolation_check['ripple_peak_ps']-.8)<.001
m=json.loads((W/'manifest.json').read_text());assert m['ripple_mode'] and sha(B/'v1.08.spice')==m['baseline_deck_sha256']
out=dict(status='pending',completed=False,fit_contract_verified=True,cases=[],limitations=['Deterministic50MHz supply modulation; not intrinsic random jitter or closed-loop rejection.','Seeded/prebiased ring and fixed ideal biases; one amplitude/frequency at nominal process only.','Fit removes and separately reports mean offset and linear drift; residual is not a noise measurement.'])
out['synthetic_interpolation_check']=dict(expected_peak_ps=.8,sample_step_ps=2,result=interpolation_check,limitation='Sinusoidal synthetic carrier validates analysis only; actual circuit timestep convergence remains required.')
record=W/('result.json' if (W/'result.json').exists() else 'progress.json')
if record.exists():
 r=json.loads(record.read_text());terminal=record.name=='result.json'
 if terminal:assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 out['status']='terminal' if terminal else 'partial_case_record';out['provenance']=r
 out['source_hashes_rechecked_after_matrix']=terminal
 names=[c['name'] for c in r['cases']]
 assert names==['quiet','ripple'][:len(names)] and 1<=len(names)<=2
 if terminal:assert len(names)==2
 edges={}
 for c in r['cases']:
  name=c['name'];expected=(B/'v1.08.spice').read_text().replace('/work/v1.08.dat',f'/work/{name}.dat').replace('tran 2p 41n 0 2p uic','tran 2p 201n 0 2p uic')
  if name=='ripple':expected=expected.replace('VPLL PLLVDD 0 3.3','VPLL PLLVDD 0 SIN(3.3 .01 50meg 20n)')
  if FINE:expected=expected.replace('tran 2p 201n 0 2p uic','tran 1p 201n 0 1p uic')
  assert (W/(name+'.spice')).read_text()==expected
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
  assert c['deck_sha256_before']==c['artifacts_sha256']['.spice']
  row=dict(name=name,completed=False)
  if (W/(name+'.dat')).exists():
   with (W/(name+'.dat')).open() as f:header=f.readline().lower().split()
   a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==len(header) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
   row.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=201e-9 and 'aborted' not in (W/(name+'.log')).read_text().lower()))
   if row['completed']:
    t=a[:,0];v=a[:,header.index('cml')];e=crossings(t,v);edges[name]=e
    active=(t>=40e-9)&(t<=200e-9);gate=a[active,header.index('v(xrx.gate)')];assert gate.min()>1.4 and gate.max()<1.6
    row['gate_range_v']=[float(gate.min()),float(gate.max())]
    row['frequency_windows']=[]
    for lo,hi in ((40,120),(120,200)):
     selected=e[(e>=lo*1e-9)&(e<=hi*1e-9)];assert len(selected)>150
     row['frequency_windows'].append(dict(window_ns=[lo,hi],frequency_hz=float((len(selected)-1)/(selected[-1]-selected[0])),crossings=len(selected)))
  out['cases'].append(row)
 out['completed']=terminal and len(out['cases'])==2 and all(c['completed'] for c in out['cases'])
 if out['completed']:
  q=edges['quiet'];s=edges['ripple'];preq=q[q<19e-9];pres=s[s<19e-9];assert len(preq)==len(pres) and len(preq)>20
  before=float(np.max(abs(preq-pres)));assert before<1e-12
  out['pre_ripple_edge_difference_max_ps']=before*1e12
  n=min(len(q),len(s));q=q[:n];s=s[:n];delay=s-q
  # Detect missing/additional crossings before assuming cycle index pairing.
  for e in (q,s):assert np.all((np.diff(e[e>=20e-9])>.3e-9)&(np.diff(e[e>=20e-9])<.5e-9))
  out['windows']=[]
  for lo,hi in ((40,200),(40,120),(120,200)):
   mask=(q>=lo*1e-9)&(q<=hi*1e-9);assert mask.sum()>150
   row=fit(q[mask],delay[mask]);row['window_ns']=[lo,hi];row['raw_delay_range_ps']=[float(delay[mask].min()*1e12),float(delay[mask].max()*1e12)];out['windows'].append(row)
(P/('evidence/vco-supply-ripple-fine.json' if FINE else 'evidence/vco-supply-ripple.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed']);print(out.get('windows',[]))
