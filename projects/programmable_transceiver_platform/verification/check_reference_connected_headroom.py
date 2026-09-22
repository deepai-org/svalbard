#!/usr/bin/env python3
"""Verify observation-only trace and audit device margins at ADC decisions."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-connected-headroom';B=R/'scratch/transceiver-adc-sar8-reference-compensated'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());raw=json.loads((W/'result.json').read_text());assert raw['source_sha256_before']==raw['source_sha256_after']==m['source_sha256_before']
for path,h in m['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
c=next(c for c in raw['cases'] if c['name']=='connected');assert c['returncode']==0 and not c['timed_out']
for name,h in c['artifacts_sha256'].items():assert sha(W/name)==h
assert sha(W/'connected.spice')==c['deck_sha256_before']
source=B/'typical_first-1.spice';assert sha(source)==m['baseline_deck_sha256']
d=(W/'connected.spice').read_text().replace('save all '+' '.join(m['probes'])+'\n','').replace('wrdata /work/devices.dat '+' '.join(m['probes'])+'\n','');assert d==source.read_text()
baserecord=json.loads((B/'result.json').read_text());bc=next(c for c in baserecord['cases'] if c['name']=='typical_first-1');assert sha(B/'typical_first-1.dat')==bc['artifacts_sha256']['.dat']
def read(path):
 with path.open() as f:header=f.readline().lower().split()
 a=np.loadtxt(path,skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0);return header,a
h,a=read(W/'typical_first-1.dat');bh,b=read(B/'typical_first-1.dat');ph,p=read(W/'devices.dat');assert h==bh and a.shape[1]==48 and ph==['time']+[s.lower() for s in m['probes']]
assert a[-1,0]>=209.9e-9 and np.array_equal(a[:,0],p[:,0])
# Report numerical change; do not silently assume added observations are neutral.
errors={h[i]:float(np.max(abs(a[:,i]-np.interp(a[:,0],b[:,0],b[:,i])))) for i in range(1,a.shape[1])}
cols={name:i for i,name in enumerate(ph)}
def vector(name):return p[:,cols[name.lower()]]
steps=[]
for hold in (70,120,170):
 for bit in range(7,-1,-1):
  lo=hold+.2+5*(7-bit);hi=hold+.35+5*(7-bit);mask=(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9);devices=[]
  for rail in ('xhigh','xlow'):
   for dev in ('xin','xip','xout','xload'):
    prefix=f'@m.xref.{rail}.{dev}.m0';vds=vector(prefix+'[vds]');sat=vector(prefix+'[vdsat]');current=vector(prefix+'[id]')
    assert np.all(vds[mask]>=0) and np.all(sat[mask]>=0)
    devices.append(dict(rail=rail,device=dev,min_vds_minus_vdsat_v=float(np.min(vds[mask]-sat[mask])),id_range_ma=[float(current[mask].min()*1e3),float(current[mask].max()*1e3)]))
  steps.append(dict(hold_ns=hold,bit=bit,window_ns=[lo,hi],span_mean_v=float(np.mean(a[mask,43]-a[mask,44])),devices=devices))
# Confirm polarity normalization against external nodes over the scored interval.
mask=(a[:,0]>=70e-9)&(a[:,0]<=205.35e-9);node_errors={}
for rail,col in [('xhigh',43),('xlow',44)]:
 for dev in ('xout','xload'):
  expected=(3.3-a[:,col]) if (rail,dev) in [('xhigh','xout'),('xlow','xload')] else a[:,col]
  node_errors[rail+'.'+dev]=float(np.max(abs(vector(f'@m.xref.{rail}.{dev}.m0[vds]')[mask]-expected[mask])))
  assert node_errors[rail+'.'+dev]<1e-6
active=(a[:,0]>=60e-9)&(a[:,0]<=209.8e-9);active_devices=[]
for rail in ('xhigh','xlow'):
 for dev in ('xin','xip','xout','xload'):
  prefix=f'@m.xref.{rail}.{dev}.m0';margin=vector(prefix+'[vds]')-vector(prefix+'[vdsat]');current=vector(prefix+'[id]')
  active_devices.append(dict(rail=rail,device=dev,min_vds_minus_vdsat_v=float(margin[active].min()),id_range_ma=[float(current[active].min()*1e3),float(current[active].max()*1e3)]))
out=dict(active_window_ns=[60,209.8],active_device_envelope=active_devices,status='connected_reference_device_window_audit',original_vector_max_difference=errors,output_device_polarity_error_v=node_errors,steps=steps,run_record=raw,limitations=['VDS-VDSAT is a model operating-region diagnostic, not a complete gain/stability metric.', 'Saved model ID already includes multiplicity; it is not all displacement/leakage current at the output terminal.', 'Selected nominal comparator windows only; absence of a headroom failure there does not exclude an earlier overload.', 'Original-vector comparison uses interpolation and reports any numerical difference rather than concealing it.'])
(P/'evidence/reference-connected-headroom.json').write_text(json.dumps(out,indent=2)+'\n')
print('Max original-vector difference',max(errors.values()))
for rail in ('xhigh','xlow'):
 for dev in ('xin','xip','xout','xload'):
  values=[d for s in steps for d in s['devices'] if d['rail']==rail and d['device']==dev];print(rail,dev,min(x['min_vds_minus_vdsat_v'] for x in values))
