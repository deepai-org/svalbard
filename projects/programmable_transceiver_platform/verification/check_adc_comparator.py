#!/usr/bin/env python3
"""Preserve both passing and failing nominal comparator cases."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]; P=ROOT/'projects/programmable_transceiver_platform'; W=ROOT/'scratch/transceiver-adc-comparator'
r=json.loads((W/'result.json').read_text())
assert hashlib.sha256((P/'analog/adc/comparator.spice').read_bytes()).hexdigest()==r['source_sha256']
assert len(r['cases'])==12
for case in r['cases']:
 name=case['name']
 for suffix,digest in case['artifacts_sha256'].items():
  assert hashlib.sha256((W/(name+suffix)).read_bytes()).hexdigest()==digest
 a=np.loadtxt(W/(name+'.dat'),skiprows=1)
 assert a.shape[1]==9 and np.isfinite(a).all() and a[-1,0]>=51e-9
 assert len(case['cycles'])==8
 signs=[]; decision_delays=[]
 for cycle in case['cycles']:
  start=cycle['start_ns']; mask=(a[:,0]>=(start+1.9)*1e-9)&(a[:,0]<=(start+2.3)*1e-9);w=a[mask]
  sign=float(np.sign(np.mean(w[:,7]-w[:,8]))); signs.append(sign)
  hi,lo=(2,3) if sign>0 else (3,2)
  correct=bool(w[:,hi].min()>2.97 and w[:,lo].max()<.33)
  assert cycle['input_sign']==sign and cycle['correct_rails']==correct
  assert np.isclose(cycle['high_min_v'],w[:,hi].min()) and np.isclose(cycle['low_max_v'],w[:,lo].max())
  reset=a[(a[:,0]>=(start+4.5)*1e-9)&(a[:,0]<=(start+4.9)*1e-9)]
  assert np.isclose(cycle['reset_min_v'],reset[:,2:4].min())
  evalw=a[(a[:,0]>=(start+.05)*1e-9)&(a[:,0]<=(start+2.3)*1e-9)]
  good=(evalw[:,hi]>2.97)&(evalw[:,lo]<.33)
  # Earliest sampled time after which output rails stay valid through eval window.
  valid=np.flatnonzero(np.logical_and.accumulate(good[::-1])[::-1])
  decision_delays.append(float((evalw[valid[0],0]-(start+.05)*1e-9)*1e9) if len(valid) else None)
 assert all(signs[i]==-signs[i-1] for i in range(1,len(signs)))
 case['decision_delays_from_clock_midpoint_ns']=decision_delays
 case['all_decisions_correct']=all(c['correct_rails'] for c in case['cycles'])
 case['all_resets_above_90_percent']=all(c['reset_min_v']>2.97 for c in case['cycles'])
 case['peak_differential_source_error_v']=float(np.max(np.abs((a[:,4]-a[:,5])-(a[:,7]-a[:,8]))))
 # Includes intentional finite-R input settling, not a pure kickback metric.
r['passing_case_count']=sum(c['all_decisions_correct'] for c in r['cases'])
r['failing_case_count']=len(r['cases'])-r['passing_case_count']
r['adc_implementation_complete']=False
r['limitations'].append('Source-error metric includes commanded input settling as well as comparator disturbance; it is not isolated kickback.')
(P/'evidence/adc-comparator-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print('Verified',len(r['cases']),'cases:',r['passing_case_count'],'pass,',r['failing_case_count'],'fail nominal decision-window requirement; no ADC precision claim.')
