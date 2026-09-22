#!/usr/bin/env python3
"""Inspect decoded and driven transient states; threshold counts are not currents."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-segmented-dynamic'
e=json.loads((P/'evidence/dac-segmented8-dynamic.json').read_text());m=json.loads((W/'manifest.json').read_text())
record=W/('result.json' if (W/'result.json').exists() else 'progress.json');raw=json.loads(record.read_text());rows=[]
for case in e['cases']:
 if not case['completed']:continue
 name=case['name'];c=next(c for c in raw['cases'] if c['name']==name)
 wave=W/(name+'.dat');assert hashlib.sha256(wave.read_bytes()).hexdigest()==c['artifacts_sha256']['.dat']
 with wave.open() as f:assert f.readline().lower().split()==['time']+[v.lower() for v in m['vectors']]
 a=np.loadtxt(wave,skiprows=1);t=a[:,0]*1e9;events=[]
 for edge in (30,55):
  select=(t>=edge-.5)&(t<=edge+3);w=a[select];tw=w[:,0]
  input_high=(w[:,9:13]>1.65)@np.array([1,2,4,8])
  therm=w[:,13:28]>1.65;count=therm.sum(axis=1)
  # Non-monotonic thermometer pattern is separate from a valid but unintended count.
  bubbles=np.any(therm[:,1:] & ~therm[:,:-1],axis=1)
  low=w[:,28:36:2]>1.65;high=w[:,36:66:2]>1.65
  effective=low@np.array([1,2,4,8])+16*high.sum(axis=1)
  events.append(dict(edge_ns=edge,input_upper_code_range=[int(input_high.min()),int(input_high.max())],decoded_high_count_range=[int(count.min()),int(count.max())],decoded_outside_7_8_duration_ps=float(np.trapezoid(((count<7)|(count>8)).astype(float),tw)*1e12),nonmonotonic_thermometer_duration_ps=float(np.trapezoid(bubbles.astype(float),tw)*1e12),true_gate_weighted_code_range=[int(effective.min()),int(effective.max())]))
 rows.append(dict(name=name,events=events))
r=dict(status='decoder_transient_threshold_diagnostic',cases=rows,limitations=['1.65V classifications and trapezoidal duration estimates; not channel-current measurements.', 'Weighted true gates ignore complement overlap and source-node movement.', 'Input skew produces real intermediate codes; not every transient decoded change is an internal logic hazard.', 'Only audited completed waveforms included; matrix completeness is in primary evidence.'])
(P/'evidence/dac-segmented-decoder-hazards.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
