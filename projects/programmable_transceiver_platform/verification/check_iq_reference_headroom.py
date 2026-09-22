#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-iq-reference-headroom';B=R/'scratch/transceiver-adc-shared-iq-same'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'frames.spice')==m['baseline_deck_sha256']
rails=('xhigh','xlow');devices=('xin','xip','xt','xmp','xmn','xout','xload');params=('vds','vdsat','vgs','id')
probes=[f'v(XREF.{rail}.{node})' for rail in ('XHIGH','XLOW') for node in ('A','T','X','Z')]+[f'@m.xref.{rail}.{dev}.m0[{param}]' for rail in rails for dev in devices for param in params];assert m['probes']==probes
expected=(B/'frames.spice').read_text().replace('tran 5p 209.9n 0 5p','save all '+' '.join(probes)+'\ntran 5p 209.9n 0 5p').replace('.endc','wrdata /work/devices.dat '+' '.join(probes)+'\n.endc')
out=dict(status='pending',completed=False)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'];out['provenance']=r
 for c in r['cases']:
  for file,h in c['artifacts_sha256'].items():assert sha(W/file)==h
 c=next(c for c in r['cases'] if c['name']=='connected');assert (W/'connected.spice').read_text()==expected and sha(W/'connected.spice')==c['deck_sha256_before']
 out.update(status='terminal',returncode=c['returncode'],timed_out=c['timed_out'])
 if (W/'devices.dat').exists() and (W/'frames.dat').exists():
  with (W/'devices.dat').open() as f:assert f.readline().lower().split()==['time']+[x.lower() for x in probes]
  a=np.loadtxt(W/'devices.dat',skiprows=1);assert a.shape[1]==65 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  orig=np.loadtxt(B/'frames.dat',skiprows=1);observed=np.loadtxt(W/'frames.dat',skiprows=1)
  out.update(original_vectors_bit_identical=bool(np.array_equal(orig,observed)),actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and 'aborted' not in (W/'connected.log').read_text().lower() and a[-1,0]+1e-21>=209.9e-9))
  out['devices']=[];active=(a[:,0]>=60e-9)&(a[:,0]<=209.8e-9)
  for rail in rails:
   for dev in devices:
    def q(param):return a[:,1+probes.index(f'@m.xref.{rail}.{dev}.m0[{param}]')]
    margin=q('vds')-q('vdsat');indices=np.flatnonzero(active);idx=indices[np.argmin(margin[active])]
    out['devices'].append(dict(device=rail+'.'+dev,min_reported_vds_minus_vdsat_v=float(margin[idx]),at_ns=float(a[idx,0]*1e9),negative_reported_vds_samples=int(np.sum(q('vds')[active]<0)),reported_id_range_a=[float(q('id')[active].min()),float(q('id')[active].max())]))
  # Correlate device state with measured error, not independent extrema.
  assert np.array_equal(a[:,0],observed[:,0])
  with (W/'frames.dat').open() as f:wh=f.readline().lower().split()
  baseline_audit=json.loads((P/'evidence/adc-shared-iq-same.json').read_text())
  assert baseline_audit['completed'] and baseline_audit['provenance']['artifacts_sha256']['.dat']==sha(B/'frames.dat')
  steps=[x for frame in baseline_audit['frames'] for x in frame['shared_reference_decisions']]
  out['tail_decision_windows']=[]
  for step in steps:
   lo,hi=step['window_ns'];ids=np.flatnonzero((a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9))
   if not len(ids) or a[-1,0]<hi*1e-9:continue
   row=dict(window_ns=[lo,hi])
   for rail in rails:
    vd=a[ids,1+probes.index(f'@m.xref.{rail}.xt.m0[vds]')]
    vs=a[ids,1+probes.index(f'@m.xref.{rail}.xt.m0[vdsat]')]
    row[rail]=dict(margin_range_v=[float((vd-vs).min()),float((vd-vs).max())],all_samples_below_boundary=bool(np.all(vd<vs)))
   out['tail_decision_windows'].append(row)
  out['error_correlations']=[]
  for rail,target,node,metric in [('xhigh',2.15,'v(vh)','high_max_error_v'),('xlow',1.15,'v(vl)','low_max_error_v')]:
   worst=max(steps,key=lambda x:x[metric]);lo,hi=worst['window_ns']
   ids=np.flatnonzero((a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9))
   if not len(ids) or a[-1,0]<hi*1e-9:continue
   idx=ids[np.argmax(abs(observed[ids,wh.index(node)]-target))]
   sample={}
   for dev in devices:
    vals={param:float(a[idx,1+probes.index(f'@m.xref.{rail}.{dev}.m0[{param}]')]) for param in params}
    vals['reported_vds_minus_vdsat_v']=vals['vds']-vals['vdsat'];sample[dev]=vals
   out['error_correlations'].append(dict(rail=rail,window_ns=[lo,hi],at_ns=float(a[idx,0]*1e9),reference_v=float(observed[idx,wh.index(node)]),signed_error_v=float(observed[idx,wh.index(node)]-target),devices_at_same_time=sample))
out['limitations']=['Observation-only probe run; current parameters include multiplicity but exclude displacement current from a delivered-output-current estimate.', 'VDS-VDSAT interpretation needs conduction polarity; negative VDS counts reported separately.', 'Finite nominal histories only; no stability/noise/mismatch or reference-sharing qualification.']
(P/'evidence/iq-reference-headroom.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
