#!/usr/bin/env python3
import hashlib,json,sys
HALF="--half" in sys.argv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-quadrature-interface-half' if HALF else 'scratch/transceiver-quadrature-interface-current');B=R/'scratch/transceiver-quadrature-lna-final'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert m.get('half_width',False)==HALF;baseline=json.loads((B/'result.json').read_text())
out=dict(status='pending',completed=False,cases=[],limitations=['Zero-volt observation sensor; positive current into combined mixer input.','Waveform reproduction must be assessed before interpreting loading.','Periodic-port RF voltage/current ratio is conditional on LO and terminations, not a broadband scalar resistor or power gain.'])
record=W/('result.json' if (W/'result.json').exists() else 'progress.json')
if record.exists():
 r=json.loads(record.read_text());terminal=record.name=='result.json'
 if terminal:assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 out.update(status='terminal' if terminal else 'partial_case_record',provenance=r)
 assert [c['name'] for c in r['cases']]==['zero','tone'][:len(r['cases'])]
 for c in r['cases']:
  name=c['name'];old=next(x for x in baseline['cases'] if x['name']==name)
  assert sha(B/(name+'.spice'))==old['artifacts_sha256']['.spice']==m['baseline_deck_sha256'][name]
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
  d=(W/(name+'.spice')).read_text();assert sha(W/(name+'.spice'))==c['deck_sha256_before']
  if HALF:
   model=R/'ip/blocks/analog/wifi_80211b/rf_switch_mixer/mixer.spice';assert sha(model)==m['source_sha256_before']['/wifi/rf_switch_mixer/mixer.spice']
   cell=model.read_text();assert cell.count('w=4u l=0.28u')==16
   variant=cell.replace('w=4u l=0.28u','w=2u l=0.28u');assert d.count(variant)==1;d=d.replace(variant,'.include /wifi/rf_switch_mixer/mixer.spice\n')
  assert d.replace('XMI MIXRF OIP','XMI RF OIP').replace('XMQ MIXRF OQP','XMQ RF OQP').replace('VSENSE RF MIXRF 0\n','').replace(' v(MIXRF) i(VSENSE)','')==(B/(name+'.spice')).read_text()
  row=dict(name=name,completed=False)
  if (W/(name+'.dat')).exists():
   with (W/(name+'.dat')).open() as f:header=f.readline().lower().split()
   with (B/(name+'.dat')).open() as f:oldheader=f.readline().lower().split()
   assert header==oldheader+['v(mixrf)','i(vsense)']
   a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==32 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
   assert sha(B/(name+'.dat'))==old['artifacts_sha256']['.dat'];b=np.loadtxt(B/(name+'.dat'),skiprows=1)
   row.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=201e-9 and 'aborted' not in (W/(name+'.log')).read_text().lower()),original_vectors_bit_identical=bool(np.array_equal(a[:,:30],b)))
   active=(a[:,0]>=120e-9)&(a[:,0]<=200e-9);w=a[active];t=w[:,0];current=w[:,-1]
   if len(t)>1:
    row.update(sensor_voltage_max_abs_v=float(np.max(abs(w[:,header.index('v(rf)')]-w[:,-2]))),current_mean_a=float(np.trapezoid(current,t)/(t[-1]-t[0])),current_range_a=[float(current.min()),float(current.max())])
    row['supply_power_w']={s:float(np.trapezoid(-3.3*w[:,header.index('i('+s+')')],t)/(t[-1]-t[0])) for s in ('vbuf','vpll','vlna')}
    row['interpolated_baseline_max_difference_v']={node:float(np.max(abs(w[:,header.index(node)]-np.interp(t,b[:,0],b[:,oldheader.index(node)])))) for node in ('v(rf)','v(oip)','v(oqp)','v(mip)','v(min)','v(mqp)','v(mqn)')}
  out['cases'].append(row)
 out['completed']=terminal and len(out['cases'])==2 and all(c['completed'] for c in out['cases'])
if HALF:out['limitations'][0]='Half-width mixer candidate with input-current sensor; changes from original waveforms are intentional, not observation-only reproduction.'
(P/('evidence/quadrature-interface-half.json' if HALF else 'evidence/quadrature-interface-current.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed']);print(out['cases'])
