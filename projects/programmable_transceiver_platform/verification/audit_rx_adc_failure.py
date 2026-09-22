#!/usr/bin/env python3
"""Inspect a terminal partial waveform; never promote it to completed evidence."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-rx-adc-loading/loaded'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['returncode']!=0 and r['sources_before']==r['sources_after']
for ext,h in r['artifacts_sha256'].items():assert sha(W/('connected'+ext))==h
log=(W/'connected.log').read_text();match=re.search(r'Timestep too small; time = ([\deE.+-]+).*?trouble with node "([^"]+)"',log);assert match
failure=float(match.group(1));events=[]
for line in (W/'connected.spice').read_text().splitlines():
 if 'PWL(' not in line:continue
 pairs=re.search(r'PWL\(([^)]*)\)',line).group(1).split()
 for i in range(0,len(pairs),2):
  assert pairs[i].endswith('n');ns=float(pairs[i][:-1])
  if abs(ns-failure*1e9)<.11:events.append(dict(source=line.split()[0],time_ns=ns,voltage_v=float(pairs[i+1])))
with (W/'connected.dat').open() as f:h=f.readline().lower().split()
a=np.loadtxt(W/'connected.dat',skiprows=1);t=a[:,0];assert a.shape[1]==len(h) and np.isfinite(a).all();dt=np.diff(t);assert not np.any(dt<0)
windows=[]
for lo,hi in [(350,400),(420,450),(450,469),(470.2,470.35),(475.2,475.35),(478.3,478.5)]:
 mask=(t>=lo*1e-9)&(t<=hi*1e-9);assert mask.any();stats={}
 for n in ['v(xadc.bn)','v(xadc.bp)','v(xadc.rbn)','v(xadc.rbp)','v(xadc.vh)','v(xadc.vl)','v(fip)','v(fin)','v(fqp)','v(fqn)','v(xadc.ip)','v(xadc.in)','v(xadc.hp)','v(xadc.hn)','v(xadc.q_ip)','v(xadc.q_in)','v(xadc.q_hp)','v(xadc.q_hn)']:
  y=a[mask,h.index(n)];stats[n]=dict(min_v=float(y.min()),max_v=float(y.max()),end_minus_start_v=float(y[-1]-y[0]))
 reference={}
 for node,target in [('v(xadc.vh)',2.15),('v(xadc.vl)',1.15)]:
  y=a[mask,h.index(node)];reference[node]=dict(target_v=target,max_target_error_v=float(abs(y-target).max()))
 span=a[mask,h.index('v(xadc.vh)')]-a[mask,h.index('v(xadc.vl)')]
 windows.append(dict(window_ns=[lo,hi],nodes=stats,reference_accuracy=reference,reference_span_min_v=float(span.min()),reference_span_max_v=float(span.max())))
out=dict(status='failed_partial_diagnostic',completed=False,artifacts_sha256=r['artifacts_sha256'],failure_time_ns=failure*1e9,failure_node=match.group(2),actual_stop_ns=float(t[-1]*1e9),rows=len(a),repeated_exported_timestamps=int((dt==0).sum()),nearby_source_knots=events,preceding_windows=windows,limitations=['Partial run cannot qualify three conversions, loaded/unloaded response or stable startup.','Coincident source events are numerical suspects, not an established cause.','Bias min/max windows do not establish transistor headroom or intrinsic noise.','No time derivatives/interpolation at repeated timestamps used.'])
(P/'evidence/rx-adc-loading-failure.json').write_text(json.dumps(out,indent=2)+'\n');print(out['failure_time_ns'],out['failure_node'],events)
for w in windows[:3]:print(w['window_ns'],{n:(v['max_v']-v['min_v'],v['end_minus_start_v']) for n,v in w['nodes'].items() if n in ['v(xadc.bn)','v(xadc.rbn)','v(xadc.vh)','v(xadc.vl)']})
