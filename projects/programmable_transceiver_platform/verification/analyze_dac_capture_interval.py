#!/usr/bin/env python3
"""Measure rail-band settling before DAC capture; not a DFF setup-time model."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';rows=[]
for suffix,evidence in [('registered','dac-segmented8-registered.json'),('coverage','dac-segmented8-coverage.json')]:
 W=R/f'scratch/transceiver-dac-segmented-{suffix}'
 e=json.loads((P/'evidence'/evidence).read_text());m=json.loads((W/'manifest.json').read_text());base=json.loads((R/'scratch/transceiver-dac-segmented-dynamic/manifest.json').read_text());vectors=base['vectors']+m['extra_vectors'];cols={v.lower():i+1 for i,v in enumerate(vectors)}
 record=W/('result.json' if (W/'result.json').exists() else 'progress.json');raw=json.loads(record.read_text())
 for case in e['cases']:
  if not case['completed']:continue
  name=case['name'];c=next(c for c in raw['cases'] if c['name']==name);file=W/(name+'.dat');assert hashlib.sha256(file.read_bytes()).hexdigest()==c['artifacts_sha256']['.dat']
  with file.open() as f:assert f.readline().lower().split()==['time']+[v.lower() for v in vectors]
  a=np.loadtxt(file,skiprows=1);t=a[:,0]*1e9;inputs=[cols[f'v(d{i})'] for i in range(4)]+[cols[f'v(xd.t{k})'] for k in range(1,16)];events=[]
  for ev,new in zip(case['events'],(128,127)):
   command=ev['command_ns'];clock=ev['buffered_clock_edge_ns'];mask=(t>=command-.5)&(t<clock);idx=np.flatnonzero(mask)
   expected=np.array([(new>>i)&1 for i in range(4)]+[int(new//16>=k) for k in range(1,16)])
   bad=np.any(abs(a[idx][:,inputs]-3.3*expected)>.33,axis=1);fail=np.flatnonzero(bad)
   # Start at the sample after the last violation, conservatively discarding the crossing interval.
   first=int(fail[-1]+1) if len(fail) else 0
   clean=float(clock-t[idx[first]]) if first<len(idx) else 0.
   events.append(dict(command_ns=command,buffered_clock_ns=clock,all_register_inputs_10percent_rail_band_before_capture_ns=clean,last_bad_sample_ns=float(t[idx[fail[-1]]]) if len(fail) else None))
  rows.append(dict(name=name,source_group=suffix,events=events,waveform_sha256=c['artifacts_sha256']['.dat']))
out=dict(status='observed_nominal_capture_interval',cases=rows,limitations=['10percent rail band is a diagnostic convention, not a characterized setup requirement.', 'Only completed existing fixtures; actual DFF setup/hold aperture, clock variation and mismatch remain unmeasured.', 'Measured interval depends on register-loaded decoder behavior and this code transition; not a worst-case logic delay bound.'])
(P/'evidence/dac-capture-interval.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
