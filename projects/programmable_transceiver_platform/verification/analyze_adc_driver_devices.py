#!/usr/bin/env python3
"""I-path transistor-state diagnostics, only after observation replay validation."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-receiver-driver-probe'
e=json.loads((P/'evidence/adc-receiver-driver-probe.json').read_text());assert e['completed'] and e['original_vectors_bit_identical']
r=json.loads((W/'result.json').read_text())
for ext,h in r['artifacts_sha256'].items():assert hashlib.sha256((W/('frames'+ext)).read_bytes()).hexdigest()==h
with (W/'frames.dat').open() as f:h=f.readline().lower().split()
a=np.loadtxt(W/'frames.dat',skiprows=1);rows=[]
for driver,output,input_node in (('xbpdrv','ip','gp'),('xbndrv','in','gn')):
 for lo,hi in ((59,59.9),(60.1,62),(65,69.85),(69.7,69.85)):
  w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=w[:,0]
  def v(n):return w[:,h.index(n)]
  def mean(y):return float(np.trapezoid(y,t)/(t[-1]-t[0]))
  def span(y):return [float(y.min()),float(y.max())]
  def probe(dev,key):return v(f'@m.{driver}.{dev}.m0[{key}]')
  # Check conventions against named physical terminals in this fixture.
  for dev,physical in (('xt',v(f'v({driver}.t)')),('xout',v(f'v({output})')),('xload',3.3-v(f'v({output})')),('xin',v(f'v({driver}.x)')-v(f'v({driver}.t)'))):
   assert np.max(abs(probe(dev,'vds')-physical))<1e-8
  devices={}
  for dev in ('xt','xip','xin','xout','xload'):
   head=probe(dev,'vds')-probe(dev,'vdsat');ids=probe(dev,'id')
   devices[dev]=dict(model_headroom_range_v=span(head),fraction_elapsed_below_model_vdsat=mean((head<0).astype(float)),reported_id_mean_a=mean(ids),reported_id_range_a=span(ids))
  rows.append(dict(driver=driver,window_ns=[lo,hi],output_minus_input_mean_v=mean(v(f'v({output})')-v(f'v({input_node})')),output_range_v=span(v(f'v({output})')),tail_node_range_v=span(v(f'v({driver}.t)')),devices=devices))
out=dict(status='validated_observation_device_diagnostic',cases=rows,artifact_sha256=r['artifacts_sha256'],limitations=['Headroom correlation alone does not identify dominant pole, slew limit or causal repair.','Reported id is model current, not a terminal-current/KCL audit.','I driver pair only; nominal fixture, ideal source/bias and finite loading history.'])
(P/'evidence/adc-driver-devices.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row['driver'],row['window_ns'],row['output_minus_input_mean_v'],row['devices']['xt'])
