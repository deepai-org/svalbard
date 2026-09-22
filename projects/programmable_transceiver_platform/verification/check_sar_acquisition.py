#!/usr/bin/env python3
"""Separate changing-input acquisition error from nominal sampler turnoff error."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';W=ROOT/'scratch/transceiver-adc-sar-acquisition';B=ROOT/'scratch/transceiver-adc-sar8-buffered'
r=json.loads((W/'result.json').read_text())
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
assert len(r['cases'])==12
for c in r['cases']:
 base=(B/f"vin{c['input_difference_v']:g}.spice").read_text()
 assert hashlib.sha256(base.encode()).hexdigest()==c['baseline_deck_sha256']
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(c['name']+suffix)).read_bytes()).hexdigest()==digest
 expected=base.replace('RIP SP IP 1k',f"RIP SP IP {c['resistance_ohm']}").replace('RIN SN IN 1k',f"RIN SN IN {c['resistance_ohm']}").replace('tran 10p 274n 0 10p','tran 10p 65n 0 10p').replace(f"/work/vin{c['input_difference_v']:g}.dat",f"/work/{c['name']}.dat")
 if c['changing']:
  for source,node,sign in (('VIP','SP',1),('VIN','SN',-1)):
   final=1.65+sign*c['input_difference_v']/2;initial=1.65-sign*c['input_difference_v']/2
   expected=expected.replace(f'{source} {node} 0 {final}',f'{source} {node} 0 PWL(0 {initial} 50n {initial} 50.1n {final})')
 assert (W/(c['name']+'.spice')).read_text()==expected

def read(c):
 a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1);assert a.shape[1]==28 and np.isfinite(a).all() and a[-1,0]>=65e-9
 assert np.max(abs(a[:,5]))<1e-12,'Comparator must not evaluate during acquisition measurement'
 return a
pairs=[]
for c in r['cases']:
 if not c['changing']:continue
 control=next(x for x in r['cases'] if not x['changing'] and x['input_difference_v']==c['input_difference_v'] and x['resistance_ohm']==c['resistance_ohm'])
 a,b=read(c),read(control);t=a[:,0];d=a[:,1]-a[:,2];reference=np.interp(t,b[:,0],b[:,1]-b[:,2])
 held=(t>=64e-9)&(t<=64.8e-9);tracked=(t>=59.8e-9)&(t<=59.9e-9)
 error=float(np.mean(d[held]-reference[held]))
 pairs.append(dict(input_difference_v=c['input_difference_v'],resistance_ohm=c['resistance_ohm'],paired_acquisition_error_v=error,paired_error_in_ideal_2v_8bit_lsb=error/(2/256),tracked_error_before_open_v=float(np.mean(d[tracked]-reference[tracked])),constant_input_held_value_v=float(np.mean(reference[held])),stepped_input_held_value_v=float(np.mean(d[held]))))
r['paired_metrics']=pairs;r['controlled_input_and_resistance_changes_checked']=True;r['sample_rate_qualified']=False
(P/'evidence/adc-sar-acquisition-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(pairs,indent=2))
