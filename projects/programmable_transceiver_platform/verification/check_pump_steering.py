#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pump-steering';B=R/'scratch/transceiver-pump-branch'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'early.spice')==m['baseline_deck_sha256']
record=W/('result.json' if (W/'result.json').exists() else 'progress.json');rows=[]
out=dict(completed=False,status='pending',cases=rows,limitations=['Ideal output and dummy1.08V clamps; dummy-voltage generator is not implemented.','Added switches also change PFD loading; compare actual behavior, not ideal complementary controls.','Single nominal phase/history, not lock, noise, variation or compliance qualification.'])
if record.exists():
 r=json.loads(record.read_text());terminal=record.name=='result.json';out.update(status='terminal' if terminal else 'partial',provenance=r)
 if terminal:assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for c in r['cases']:
  n=c['name'];assert n in ('control','steering')
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
  d=(W/(n+'.spice')).read_text();probes=' i(VDIV) i(VDUMMY) v(DUMMY)'+(' v(XCP.DNB)' if n=='steering' else '')
  assert d.count(probes)==2 and d.count('VDUMMY DUMMY 0 1.08\n')==1
  d=d.replace(probes,'').replace('VDUMMY DUMMY 0 1.08\n','').replace(f'/work/{n}.dat','/work/early.dat')
  if n=='steering':
   assert d.count(m['steering_addition'])==1
   d=d.replace(m['steering_addition'],'').replace('.subckt pt_charge_pump UP DN OUT BP BN VDD VSS DUMMY','.subckt pt_charge_pump UP DN OUT BP BN VDD VSS').replace('XCP UP DN PUMP BPCP BNCP VDIV 0 DUMMY pt_charge_pump','XCP UP DN PUMP BPCP BNCP VDIV 0 pt_charge_pump')
  assert d==(B/'early.spice').read_text()
  a=np.loadtxt(W/(n+'.dat'),skiprows=1)
  with (W/(n+'.dat')).open() as f:h=f.readline().lower().split()
  with (B/'early.dat').open() as f:bh=f.readline().lower().split()
  assert h==bh+probes.lower().split() and a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  done=c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=800e-9 and 'aborted' not in (W/(n+'.log')).read_text().lower();row=dict(name=n,completed=done)
  if done:
   w=a[(a[:,0]>=200e-9)&(a[:,0]<=790e-9)];t=w[:,0]
   def v(name):return w[:,h.index(name)]
   for name in ('v(ctrl)','v(dummy)'):assert np.max(abs(v(name)-1.08))<1e-9
   residual=v('i(v.xcp.vp)')-v('i(v.xcp.vn)')-v('i(vsense)');assert np.max(abs(residual))<1e-9
   y=v('v(ref)')-1.65;k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));edges=t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k];count=len(edges)-1
   x=np.r_[edges[0],t[(t>edges[0])&(t<edges[-1])],edges[-1]]
   integral=lambda name:float(np.trapezoid(np.interp(x,t,v(name)),x))
   row.update(reference_cycles=count,net_pump_charge_per_cycle_c=integral('i(vsense)')/count,pmos_delivery_per_cycle_c=integral('i(v.xcp.vp)')/count,nmos_withdrawal_per_cycle_c=integral('i(v.xcp.vn)')/count,supply_power_w=-3.3*integral('i(vdiv)')/(x[-1]-x[0]),dummy_source_power_w=-1.08*integral('i(vdummy)')/(x[-1]-x[0]),node_ranges_v={name:[float(v(name).min()),float(v(name).max())] for name in ('v(xcp.ps)','v(xcp.ns)','v(bpcp)','v(bncp)')},kcl_max_error_a=float(np.max(abs(residual))))
   cycle_records=[]
   for left,right in zip(edges[:-1],edges[1:]):
    xt=np.r_[left,t[(t>left)&(t<right)],right]
    iq=np.interp(xt,t,v('i(vsense)'));idd=np.interp(xt,t,v('i(vdummy)'))
    cycle_records.append(dict(start_ns=float(left*1e9),net_pump_charge_c=float(np.trapezoid(iq,xt)),dummy_absorbed_charge_c=float(np.trapezoid(idd,xt))))
   assert abs(sum(q['net_pump_charge_c'] for q in cycle_records)/count-row['net_pump_charge_per_cycle_c'])<1e-22
   row['cycles']=cycle_records
   row['net_charge_cycle_range_c']=[min(q['net_pump_charge_c'] for q in cycle_records),max(q['net_pump_charge_c'] for q in cycle_records)]
   dummy_current=np.interp(x,t,v('i(vdummy)'))
   row['dummy_source_demand']=dict(peak_supply_current_a=float(max(0,-dummy_current.min())),peak_sink_current_a=float(max(0,dummy_current.max())),supplied_charge_per_cycle_c=float(np.trapezoid(np.maximum(-dummy_current,0),x))/count,absorbed_charge_per_cycle_c=float(np.trapezoid(np.maximum(dummy_current,0),x))/count)
   row['output_clamp_absorbed_power_w']=1.08*integral('i(vclamp)')/(x[-1]-x[0])
   if n=='control':
    b=np.loadtxt(B/'early.dat',skiprows=1);row['baseline_vectors_identical']=bool(np.array_equal(a[:,:37],b))
    row['baseline_max_interpolated_voltage_error_v']=max(float(np.max(abs(v(name)-np.interp(t,b[:,0],b[:,bh.index(name)])))) for name in bh if name.startswith('v('))
  rows.append(row)
 out['completed']=terminal and len(rows)==2 and all(c['completed'] for c in rows)
if out['completed']:
 control,candidate=rows
 assert control['name']=='control' and candidate['name']=='steering'
 out['comparison']=dict(net_charge_ratio=candidate['net_pump_charge_per_cycle_c']/control['net_pump_charge_per_cycle_c'],supply_power_change_w=candidate['supply_power_w']-control['supply_power_w'],dummy_source_power_change_w=candidate['dummy_source_power_w']-control['dummy_source_power_w'])
(P/'evidence/pump-steering.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
