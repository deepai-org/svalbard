#!/usr/bin/env python3
"""Measured signed phase and charge, without claiming autonomous acquisition."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--follower",action="store_true");ap.add_argument("--control-range",action="store_true");ap.add_argument("--range-followup",action="store_true");args=ap.parse_args()
if args.range_followup:args.control_range=True
if args.control_range:args.follower=True
BASE="follower" if args.follower else "steering"
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-pump-'+BASE+'-phase');B=R/('scratch/transceiver-pump-'+BASE)
if args.control_range:W=R/'scratch/transceiver-pump-control-range'
if args.range_followup:W=R/'scratch/transceiver-pump-range-followup'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/(BASE+'.spice'))==m['baseline_deck_sha256']
record=W/('result.json' if (W/'result.json').exists() else 'progress.json');rows=[]
out=dict(status='pending',completed=False,cases=rows,limitations=['Ideal clocks and clamped output; follower variant has actual dummy driver but ideal bias currents; original variant has ideal dummy clamp.','Signed phase scenarios are not process/jitter bounds.','Measured charge sign is not lock/acquisition proof.'])
if record.exists():
 r=json.loads(record.read_text());terminal=record.name=='result.json';out.update(status='terminal' if terminal else 'partial',provenance=r)
 if terminal:assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for c in r['cases']:
  n=c['name'];phase_name=c['phase'] if args.control_range else n;control=c['control_v'] if args.control_range else 1.08
  assert c['delay']=={'early':'99.7n','late':'100.3n','late600':'100.6n'}[phase_name]
  if args.control_range:assert control in ((.98,1.3) if args.range_followup else (.98,1.16)) and n==f'v{control:g}_{phase_name}'
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
  d=(W/(n+'.spice')).read_text();line=f"VFB FB 0 PULSE(0 3.3 {c['delay']} 100p 100p 25.5n 51.2n)";assert d.count(line)==1
  if args.control_range:
   for old,new in (('VCLAMP CTRL 0 1.08',f'VCLAMP CTRL 0 {control:g}'),('.ic v(CTRL)=1.08 v(XFILT.Z)=1.08',f'.ic v(CTRL)={control:g} v(XFILT.Z)={control:g}'),('.ic v(DUMMY)=1.08',f'.ic v(DUMMY)={control:g}')):
    assert d.count(new)==1;d=d.replace(new,old)
  assert d.replace(line,'VFB FB 0 PULSE(0 3.3 99.999n 100p 100p 25.5n 51.2n)').replace(f'/work/{n}.dat',f'/work/{BASE}.dat')==(B/(BASE+'.spice')).read_text()
  with (W/(n+'.dat')).open() as f:h=f.readline().lower().split()
  with (B/(BASE+'.dat')).open() as f:assert f.readline().lower().split()==h
  a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  done=c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=800e-9 and 'aborted' not in (W/(n+'.log')).read_text().lower();row=dict(name=n,completed=done,actual_stop_ns=float(a[-1,0]*1e9))
  if done:
   w=a[(a[:,0]>=200e-9)&(a[:,0]<=790e-9)];t=w[:,0]
   def v(name):return w[:,h.index(name)]
   def edges(name):
    y=v(name)-1.65;k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));return t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
   ref=edges('v(ref)');fb=edges('v(fb)');assert len(ref)==len(fb)>5
   phase=(ref-fb)*1e12;assert np.max(abs(phase-({'early':300,'late':-300,'late600':-600}[phase_name])))<.01
   for node in (('v(ctrl)',) if args.follower else ('v(ctrl)','v(dummy)')):assert np.max(abs(v(node)-control))<1e-9
   residual=v('i(v.xcp.vp)')-v('i(v.xcp.vn)')-v('i(vsense)');assert np.max(abs(residual))<1e-9
   cycles=[]
   for l,u in zip(ref[:-1],ref[1:]):
    x=np.r_[l,t[(t>l)&(t<u)],u]
    q=float(np.trapezoid(np.interp(x,t,v('i(vsense)')),x));cycles.append(q)
   mean=float(np.mean(cycles));row.update(reference_minus_feedback_ps=phase.tolist(),cycle_charge_c=cycles,mean_charge_per_cycle_c=mean,mean_pump_current_a=mean/float(np.mean(np.diff(ref))),correction_sign_consistent_with_positive_vco_gain=bool(mean*np.mean(phase)<0))
   row['dummy_voltage_range_v']=[float(min(v('v(dummy)'))),float(max(v('v(dummy)')))]
   if args.follower:row['driver_supply_power_w']=float(-3.3*np.trapezoid(v('i(vdrv)'),t)/(t[-1]-t[0]))
  rows.append(row)
 expected={f'v{v:g}_{p}' for v in (.98,1.16) for p in ('early','late')} if args.control_range else {'early','late'}
 if args.range_followup:expected={'v0.98_late600','v1.3_early','v1.3_late'}
 assert len({c['name'] for c in rows})==len(rows) and {c['name'] for c in rows}<=expected
 out['completed']=terminal and {c['name'] for c in rows}==expected and all(c['completed'] for c in rows)
(P/('evidence/pump-range-followup.json' if args.range_followup else 'evidence/pump-control-range.json' if args.control_range else 'evidence/pump-'+BASE+'-phase.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],rows)
