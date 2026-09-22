#!/usr/bin/env python3
import hashlib,json,sys
CLAMP="--clamped" in sys.argv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-pump-clamped' if CLAMP else 'scratch/transceiver-pfd-event-offset');B=R/('scratch/transceiver-pfd-event-offset' if CLAMP else 'scratch/transceiver-pfd-matched-waveform')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
record=W/('result.json' if (W/'result.json').exists() else 'progress.json');rows=[]
out=dict(completed=False,status='pending',cases=rows,limitations=['Actual PFD/pump/filter driven by ideal clocks, not an autonomous PLL.','Offsets change source-event timing; completion does not establish internal solver root cause.','No acquisition, startup or noise qualification.'])
if record.exists():
 r=json.loads(record.read_text());terminal=record.name=='result.json';out.update(status='terminal' if terminal else 'partial',provenance=r)
 if terminal:
  assert r['source_sha256_before']==r['source_sha256_after']
  if not CLAMP:assert sha(B/'mixed.spice')==r['baseline_deck_sha256']
 for c in r['cases']:
  n=c['name'];assert c['delay']=={'early':'99.999n','late':'100.001n'}[n]
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
  d=(W/(n+'.spice')).read_text();line=f"VFB FB 0 PULSE(0 3.3 {c['delay']} 100p 100p 25.5n 51.2n)";assert d.count(line)==1
  if CLAMP:
   assert d.count('VCLAMP CTRL 0 1.08\n')==1
   probes=' v(XCP.UPB) v(XCP.PS) v(XCP.NS) v(BPCP) v(BNCP) i(VCLAMP)'
   assert d.count(probes)==2
   assert sha(B/(n+'.spice'))==c['baseline_deck_sha256']
   assert d.replace('VCLAMP CTRL 0 1.08\n','').replace(probes,'')==(B/(n+'.spice')).read_text()
  else:assert d.replace(line,'VFB FB 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)').replace(f'/work/{n}.dat','/work/mixed.dat')==(B/'mixed.spice').read_text()
  a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert a.shape[1]==(13 if CLAMP else 7) and np.isfinite(a).all()
  with (W/(n+'.dat')).open() as f:assert f.readline().lower().split()==['time','v(ref)','v(fb)','v(up)','v(dn)','v(ctrl)','i(vsense)']+(['v(xcp.upb)','v(xcp.ps)','v(xcp.ns)','v(bpcp)','v(bncp)','i(vclamp)'] if CLAMP else [])
  dt=np.diff(a[:,0]);log=(W/(n+'.log')).read_text().lower()
  completed=c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=800e-9 and 'aborted' not in log
  row=dict(name=n,completed=completed,stop_ns=float(a[-1,0]*1e9),backward_steps=int(sum(dt<0)),equal_printed_steps=int(sum(dt==0)),timestep_error='timestep too small' in log)
  if completed and np.all(dt>0):
   w=a[(a[:,0]>=200e-9)&(a[:,0]<=790e-9)];t=w[:,0]
   def edges(col):
    y=w[:,col]-1.65;k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));return t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
   ref=edges(1);fb=edges(2);assert len(ref)==len(fb)>5
   start,stop=ref[0],ref[-1];x=np.r_[start,t[(t>start)&(t<stop)],stop]
   def integral(col):return float(np.trapezoid(np.interp(x,t,w[:,col]),x))
   row.update(integration_window_ns=[float(start*1e9),float(stop*1e9)],reference_cycles=len(ref)-1,reference_minus_feedback_edge_ps=(1e12*(ref-fb)).tolist(),control_range_v=[float(w[:,5].min()),float(w[:,5].max())],pump_charge_c=integral(6),mean_up_v=integral(3)/(stop-start),mean_dn_v=integral(4)/(stop-start))
   cycles=[]
   for left,right in zip(ref[:-1],ref[1:]):
    xt=np.r_[left,t[(t>left)&(t<right)],right]
    current=np.interp(xt,t,w[:,6]);charge=float(np.trapezoid(current,xt))
    positive=float(np.trapezoid(np.maximum(current,0),xt));negative=float(np.trapezoid(np.minimum(current,0),xt))
    assert abs(charge-positive-negative)<1e-24
    cycles.append(dict(start_ns=float(left*1e9),stop_ns=float(right*1e9),net_charge_c=charge,positive_charge_c=positive,negative_charge_c=negative,mean_pump_current_a=charge/(right-left),control_start_v=float(np.interp(left,t,w[:,5])),control_stop_v=float(np.interp(right,t,w[:,5]))))
   assert abs(sum(q['net_charge_c'] for q in cycles)-row['pump_charge_c'])<1e-24
   row['cycles']=cycles
   if CLAMP:
    row['clamp_max_error_v']=float(np.max(abs(w[:,5]-1.08)));assert row['clamp_max_error_v']<1e-9
    row['probe_ranges']={name:[float(w[:,col].min()),float(w[:,col].max())] for col,name in enumerate(('upb','ps','ns','bpcp','bncp'),7)}
    row['clamp_charge_c']=integral(12)
  rows.append(row)
 out['completed']=terminal and len(rows)==2 and all(x['completed'] for x in rows)
(P/('evidence/pump-clamped.json' if CLAMP else 'evidence/pfd-event-offset.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],rows)
