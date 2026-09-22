#!/usr/bin/env python3
"""Audit connected segmented transient and compare identical binary metrics."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-segmented-dynamic';B=R/'scratch/transceiver-dac-segmented-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'segmented.spice')==m['baseline_deck_sha256']
original=(B/'segmented.spice').read_text().split('.control')[0];stripped=re.sub(r'^BD\d+ .+\n','',original,flags=re.M).replace('VCODE CODE 0 0\n','')
for path,h in m['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
static_record=json.loads((B/'result.json').read_text());assert sha(B/'segmented.dat')==static_record['artifacts_sha256']['.dat']
s=np.loadtxt(B/'segmented.dat',skiprows=1);targets={k:float(s[k,2]-s[k,1]) for k in (127,128)};lsb=float((s[-1,2]-s[-1,1]-s[0,2]+s[0,1])/255)
complete=(W/'result.json').exists();path=W/('result.json' if complete else 'progress.json');raw=json.loads(path.read_text()) if path.exists() else {'cases':[]};rows=[]
for c in raw['cases']:
 name=c['name'];d=(W/(name+'.spice')).read_text()
 assert d.split('.include /screen/reference/reservoir_mim.spice')[0]==stripped
 assert f"XCP OP 0 pt_ref_reservoir_{c['load_units']}\nXCN ON 0 pt_ref_reservoir_{c['load_units']}" in d
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 row=dict(name=name,returncode=c['returncode'],timed_out=c['timed_out'],completed=False)
 wave=W/(name+'.dat')
 if not wave.exists():rows.append(row);continue
 with wave.open() as f:assert f.readline().lower().split()==['time']+[v.lower() for v in m['vectors']]
 a=np.loadtxt(wave,skiprows=1);assert a.shape[1]==len(m['vectors'])+1 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 row['actual_stop_ns']=float(a[-1,0]*1e9)
 row['completed']=bool(c['returncode']==0 and not c['timed_out'] and a[-1,0]>=79.9e-9 and 'aborted' not in (W/(name+'.log')).read_text().lower())
 if not row['completed']:rows.append(row);continue
 t=a[:,0]*1e9;v=a[:,2]-a[:,1]
 for i in range(8):
  shift=c['msb_skew_ns'] if i==7 else 0;first=3.3 if i<7 else 0
  assert np.max(abs(a[:,5+i]-np.interp(t,[0,30+shift,30.1+shift,55+shift,55.1+shift],[first,first,3.3-first,3.3-first,first])))<1e-6
 for lo,hi,code in ((20,25,127),(45,50,128),(70,75,127)):
  mask=(t>=lo)&(t<=hi);assert mask.any()
  assert np.max(abs(a[mask,13:28]-3.3*((code//16)>=np.arange(1,16))))<.33
 events=[]
 for edge,old,new in ((30,127,128),(55,128,127)):
  w=(t>=edge-.5)&(t<=edge+10);error=v[w]-np.where(t[w]<edge+.05,targets[old],targets[new]);late=(t>=edge+15)&(t<=edge+20)
  events.append(dict(edge_ns=edge,peak_error_mv=float(np.max(abs(error))*1e3),absolute_error_area_mv_ns=float(np.trapezoid(abs(error),a[w,0])*1e12),late_half_lsb_band_pass=bool(np.all(abs(v[late]-targets[new])<=lsb/2))))
 row.update(transitions=events,decoder_and_driver_peak_current_ma=float(np.max(-a[:,4])*1e3),source_node_range_v=[float(a[:,-19:].min()),float(a[:,-19:].max())]);rows.append(row)
if complete:assert raw['source_sha256_before']==raw['source_sha256_after']==m['source_sha256_before'] and {c['name'] for c in rows}==set(m['planned_cases'])
r=dict(status='complete_segmented_dynamic_diagnostic' if complete else 'partial_segmented_dynamic_diagnostic',cases=rows,manifest=m,limitations=['Selected major carry and nominal matched models, not full transfer dynamic quality.', 'Ideal supplies/bias/commands/termination; no RF reconstruction or noise/mismatch.', '5ps step; large changes require numerical sensitivity checking.'])
(P/'evidence/dac-segmented8-dynamic.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
