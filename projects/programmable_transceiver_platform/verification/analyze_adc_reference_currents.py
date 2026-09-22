#!/usr/bin/env python3
"""Attribute terminal delivery/reservoir/load currents after replay validation."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--scoped",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-reference-current';E=P/'evidence/adc-reference-current-replay.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads(E.read_text());assert e['completed']
scoped_hash=None
if args.scoped:
 scope_path=P/'evidence/adc-reference-reproduction-scope.json';scope=json.loads(scope_path.read_text())
 assert scope['scoped_current_diagnostic_valid'] and scope['replay_evidence_sha256']==sha(E)
 scoped_hash=sha(scope_path)
else:assert e['reproduction_verified'],'Replay reproduction must pass before attribution'
for ext,h in e['provenance']['artifacts_sha256'].items():assert sha(W/('frames'+ext))==h
with (W/'frames.dat').open() as f:h=f.readline().lower().split()
a=np.loadtxt(W/'frames.dat',skiprows=1);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
def v(name):return a[:,h.index(name)]
rows=[]
for hold in (70,120,170):
 for k in range(8):
  lo=hold+5*k;hi=min(lo+5,209.9)
  cycle=(t>=lo*1e-9)&(t<=hi*1e-9);decision=(t>=(lo+.2)*1e-9)&(t<=(lo+.35)*1e-9);ct=t[cycle];dt=t[decision];assert len(ct)>2 and len(dt)>2
  for rail,target in [('h',2.15),('l',1.15)]:
   delivered=v('i(vref'+rail+'_del)');reservoir=v('i(vref'+rail+'_res)');load=delivered-reservoir;voltage=v('v(v'+rail+')');currents={}
   for name,y in [('delivered',delivered),('reservoir',reservoir),('adc_demand',load)]:
    currents[name]=dict(cycle_range_a=[float(y[cycle].min()),float(y[cycle].max())],cycle_charge_c=float(np.trapezoid(y[cycle],ct)),decision_mean_a=float(np.trapezoid(y[decision],dt)/(dt[-1]-dt[0])))
   rows.append(dict(hold_ns=hold,bit=7-k,rail=rail,actual_cycle_ns=[ct[0]*1e9,ct[-1]*1e9],decision_voltage_mean_v=float(np.trapezoid(voltage[decision],dt)/(dt[-1]-dt[0])),decision_max_error_v=float(abs(voltage[decision]-target).max()),currents=currents))
out=dict(status='scoped_terminal_current_diagnostic' if args.scoped else 'validated_terminal_current_attribution',scoped_audit_sha256=scoped_hash,global_reproduction_verified=e['reproduction_verified'],replay_evidence_sha256=sha(E),cases=rows,limitations=['ADC demand is KCL-derived from two measured branches, not an independent KCL closure test.','Signed current/charge includes return to rail; peak values are not average power.','Windows include multiple switching events; a large error does not alone identify a device mechanism.','Selected nominal histories and ideal bias/supply remain.','Scoped mode excludes matched digital supply power and does not override failed global reproduction.'])
events=[]
for rail in ['h','l']:
 worst=max((r for r in rows if r['rail']==rail),key=lambda x:x['decision_max_error_v'])
 decision=worst['hold_ns']+5*(7-worst['bit']);mask=(t>=(decision-2.5)*1e-9)&(t<=(decision+.35)*1e-9);et=t[mask]
 delivered=v('i(vref'+rail+'_del)')[mask];reservoir=v('i(vref'+rail+'_res)')[mask];voltage=v('v(v'+rail+')')[mask]
 metrics={}
 for name,y in [('delivered',delivered),('reservoir',reservoir),('adc_demand',delivered-reservoir)]:
  k=int(y.argmin());j=int(y.argmax());metrics[name]=dict(min_a=float(y[k]),min_time_ns=float(et[k]*1e9),max_a=float(y[j]),max_time_ns=float(et[j]*1e9),charge_c=float(np.trapezoid(y,et)))
 events.append(dict(rail=rail,decision_ns=decision,actual_window_ns=[float(et[0]*1e9),float(et[-1]*1e9)],voltage_range_v=[float(voltage.min()),float(voltage.max())],currents=metrics))
out['worst_decision_preceding_events']=events
(P/'evidence/adc-reference-current-attribution.json').write_text(json.dumps(out,indent=2)+'\n')
for rail in ['h','l']:
 r=max((r for r in rows if r['rail']==rail),key=lambda x:x['decision_max_error_v']);print('worst',rail,r)
