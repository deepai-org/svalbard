#!/usr/bin/env python3
"""Compare high-reference resistor candidate with identical measured-load baseline."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';C=R/'scratch/transceiver-reference-high-rz';B=R/'scratch/transceiver-reference-load-startup-full'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((C/'manifest.json').read_text());prep=m['preparation'];assert prep['candidate_exact_reversal'] and sha(B/'load.spice')==prep['candidate_baseline_deck_sha256']
cell=(P/'analog/reference/adc_reference_pair_tuned.spice').read_text();changed=cell.replace('S=4 CC=2p RZ=2000\nXLOW','S=4 CC=2p RZ=4000\nXLOW')
assert changed!=cell and (C/'load.spice').read_text().replace(changed,'.include /screen/reference/adc_reference_pair_tuned.spice')==(B/'load.spice').read_text()
assert prep['demand_sha256']==json.loads((B/'manifest.json').read_text())['preparation']['demand_sha256']
assert sha(C/'load.spice')==m['deck_sha256_before']==prep['deck_sha256']
for prepared in ['transceiver-reference-high-rz-prepared','transceiver-reference-load-startup-prepared']:
 assert sha(R/('scratch/'+prepared+'/demand.spice'))==prep['demand_sha256']
out=dict(status='pending',cases=[])
if (C/'result.json').exists():
 for label,w in [('baseline',B),('candidate',C)]:
  r=json.loads((w/'result.json').read_text());manifest=json.loads((w/'manifest.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==manifest['source_sha256_before']
  for ext,h in r['artifacts_sha256'].items():assert sha(w/('load'+ext))==h
  with (w/'load.dat').open() as f:h=f.readline().lower().split()
  assert h==['time']+next(l for l in (w/'load.spice').read_text().splitlines() if l.startswith('wrdata ')).lower().split()[2:]
  a=np.loadtxt(w/'load.dat',skiprows=1);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
  done=r['returncode']==0 and not r['timed_out'] and t[-1]+1e-21>=209.9e-9 and 'aborted' not in (w/'load.log').read_text().lower()
  row=dict(case=label,completed=bool(done),provenance=r,decisions=[])
  if done:
   active=t>=60e-9;row['reference_supply_mean_power_w']=float(-3.3*np.trapezoid(a[active,h.index('i(vrefsup)')],t[active])/(t[active][-1]-t[active][0]))
   for hold in (70,120,170):
    for k in range(8):
     lo=hold+5*k+.2;hi=lo+.15;mask=(t>=lo*1e-9)&(t<=hi*1e-9);vt=t[mask];assert len(vt)>2
     rails={}
     for rail,target in [('h',2.15),('l',1.15)]:
      y=a[mask,h.index('v(v'+rail+')')];rails[rail]=dict(max_error_v=float(abs(y-target).max()),mean_error_v=float(np.trapezoid(y-target,vt)/(vt[-1]-vt[0])),motion_v=float(np.ptp(y)))
     row['decisions'].append(dict(hold_ns=hold,bit=7-k,rails=rails))
   row['summary']={rail:dict(worst_decision_error_v=max(x['rails'][rail]['max_error_v'] for x in row['decisions']),worst_decision_motion_v=max(x['rails'][rail]['motion_v'] for x in row['decisions']),active_voltage_range_v=[float(a[active,h.index('v(v'+rail+')')].min()),float(a[active,h.index('v(v'+rail+')')].max())]) for rail in ['h','l']}
  out['cases'].append(row)
 out['status']='completed_diagnostic_comparison' if all(x['completed'] for x in out['cases']) else 'incomplete_candidate_comparison'
 if all(x['completed'] for x in out['cases']):
  base,candidate=out['cases'];changes=[]
  for b,c in zip(base['decisions'],candidate['decisions']):
   assert (b['hold_ns'],b['bit'])==(c['hold_ns'],c['bit'])
   changes.append(dict(hold_ns=b['hold_ns'],bit=b['bit'],high_error_change_v=c['rails']['h']['max_error_v']-b['rails']['h']['max_error_v'],low_error_change_v=c['rails']['l']['max_error_v']-b['rails']['l']['max_error_v']))
  out['decision_changes']=changes
  out['supply_power_change_w']=candidate['reference_supply_mean_power_w']-base['reference_supply_mean_power_w']
out['limitations']=['Frozen measured demand may change after fullADC reintegration.','Resistor remains ideal; no layout/PVT/noise qualification.','Scores diagnostic metrics without inventing acceptance limits.']
(P/'evidence/reference-high-rz.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'])
