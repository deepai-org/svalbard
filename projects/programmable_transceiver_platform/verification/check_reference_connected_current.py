#!/usr/bin/env python3
"""Sensor invariance and measured-versus-channel current comparison."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-connected-current';B=R/'scratch/transceiver-reference-connected-headroom'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'connected.spice')==m['baseline_deck_sha256'];assert sha(W/'current.spice')==m['deck_sha256_before']
old='XREF HR LR VH VL RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned';new='XREF HR LR VHD VLD RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned\nVHS VHD VH 0\nVLS VLD VL 0'
d=(W/'current.spice').read_text();assert d.count(new)==1;assert d.replace(new,old).replace('wrdata /work/currents.dat i(VHS) i(VLS) v(VHD) v(VLD) v(VH) v(VL)\n','')==(B/'connected.spice').read_text()
for path,h in m['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
out=dict(status='pending_current_sensor_result',manifest=m,declared_change_verified=True)
result=W/'result.json'
if result.exists():
 r=json.loads(result.read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for name,h in r['artifacts_sha256'].items():assert sha(W/name)==h
 out['run_record']=r
 if r['returncode']==0 and not r['timed_out']:
  def read(p):
   with p.open() as f:h=f.readline().lower().split()
   a=np.loadtxt(p,skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0);return h,a
  h,a=read(W/'typical_first-1.dat');bh,b=read(B/'typical_first-1.dat');ph,p=read(W/'devices.dat');ch,c=read(W/'currents.dat')
  bm=json.loads((B/'manifest.json').read_text());br=json.loads((B/'result.json').read_text());bc=next(x for x in br['cases'] if x['name']=='connected');assert sha(B/'typical_first-1.dat')==bc['artifacts_sha256']['typical_first-1.dat']
  assert h==bh and len(h)==48 and ph==['time']+[x.lower() for x in bm['probes']]
  assert ch==['time','i(vhs)','i(vls)','v(vhd)','v(vld)','v(vh)','v(vl)']
  assert np.array_equal(a[:,0],p[:,0]) and np.array_equal(a[:,0],c[:,0]) and a[-1,0]>=209.9e-9
  assert np.max(abs(c[:,3]-c[:,5]))<1e-9 and np.max(abs(c[:,4]-c[:,6]))<1e-9
  errors={h[i]:float(np.max(abs(a[:,i]-np.interp(a[:,0],b[:,0],b[:,i])))) for i in range(1,len(h))}
  cols={v:i for i,v in enumerate(ph)}
  def v(name):return p[:,cols[name.lower()]]
  active=(a[:,0]>=60e-9)&(a[:,0]<=209.8e-9);rows=[]
  for rail,sensor in [('xhigh',1),('xlow',2)]:
   io=v(f'@m.xref.{rail}.xout.m0[id]');il=v(f'@m.xref.{rail}.xload.m0[id]');channel=io-il if rail=='xhigh' else il-io
   compensation=(v(f'v(xref.{rail}.x)')-v(f'v(xref.{rail}.z)'))/500;estimate=channel+compensation;measured=c[:,sensor];residual=measured-estimate
   rows.append(dict(rail=rail,measured_delivered_range_ma=[float(measured[active].min()*1e3),float(measured[active].max()*1e3)],estimated_delivered_range_ma=[float(estimate[active].min()*1e3),float(estimate[active].max()*1e3)],max_abs_unaccounted_current_ma=float(np.max(abs(residual[active]))*1e3),signed_unaccounted_charge_fc=float(np.trapezoid(residual[active],a[active,0])*1e15)))
  out.update(status='completed_current_sensor_diagnostic',original_vector_max_difference=errors,active_window_ns=[60,209.8],rails=rows)
 else:out['status']='failed_current_sensor_run'
out['limitations']=['Sensor measures amplifier current into the combined reservoir and ADC reference network, not ADC current alone.', 'Channel-plus-compensation estimate omits device displacement and feedback-gate currents.', 'Numerical waveform differences are reported before performance inference; ideal zero-volt sensors are not physical measurement circuitry.', 'No current-capacity, stability, noise or variation qualification.']
(P/'evidence/reference-connected-current.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'])
if 'rails' in out:print(json.dumps(out['rails'],indent=2));print('Max original-vector difference',max(out['original_vector_max_difference'].values()))
