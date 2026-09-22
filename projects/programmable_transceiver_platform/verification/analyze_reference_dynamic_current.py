#!/usr/bin/env python3
"""Time-aligned channel and compensation currents; not complete terminal KCL."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-connected-headroom'
r=json.loads((W/'result.json').read_text());c=next(c for c in r['cases'] if c['name']=='connected')
for name,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/name).read_bytes()).hexdigest()==h
with (W/'devices.dat').open() as f:header=f.readline().lower().split()
p=np.loadtxt(W/'devices.dat',skiprows=1);a=np.loadtxt(W/'typical_first-1.dat',skiprows=1);assert np.array_equal(a[:,0],p[:,0]);cols={s:i for i,s in enumerate(header)}
def v(name):return p[:,cols[name.lower()]]
t=a[:,0];active=(t>=60e-9)&(t<=209.8e-9);rows=[]
for rail,outcol in [('xhigh',43),('xlow',44)]:
 output=v(f'@m.xref.{rail}.xout.m0[id]');load=v(f'@m.xref.{rail}.xload.m0[id]')
 channel=output-load if rail=='xhigh' else load-output
 # RC X Z, capacitor Z OUT. Positive resistor current flows toward capacitor/output.
 compensation=(v(f'v(XREF.{rail}.X)')-v(f'v(XREF.{rail}.Z)'))/500
 estimate=channel+compensation;steps=[]
 for hold in (70,120,170):
  for bit in range(7,-1,-1):
   lo=hold+.2+5*(7-bit);hi=hold+.35+5*(7-bit);mask=(t>=lo*1e-9)&(t<=hi*1e-9);tw=t[mask]
   def average(x):return float(np.trapezoid(x[mask],tw)/(tw[-1]-tw[0]))
   steps.append(dict(hold_ns=hold,bit=bit,window_ns=[lo,hi],reference_mean_v=average(a[:,outcol]),net_channel_mean_ma=average(channel)*1e3,compensation_mean_ma=average(compensation)*1e3,estimated_delivered_mean_ma=average(estimate)*1e3,reference_endpoint_change_mv=float((a[mask,outcol][-1]-a[mask,outcol][0])*1e3)))
 i=np.flatnonzero(active);mn=i[np.argmin(estimate[active])];mx=i[np.argmax(estimate[active])]
 rows.append(dict(rail=rail,net_channel_range_ma=[float(channel[active].min()*1e3),float(channel[active].max()*1e3)],compensation_range_ma=[float(compensation[active].min()*1e3),float(compensation[active].max()*1e3)],estimated_delivered_range_ma=[float(estimate[mn]*1e3),float(estimate[mx]*1e3)],extreme_times_ns=[float(t[mn]*1e9),float(t[mx]*1e9)],steps=steps))
out=dict(status='time_aligned_reference_current_diagnostic',active_window_ns=[60,209.8],cases=rows,artifacts_sha256=c['artifacts_sha256'],limitations=['Positive estimated delivered current flows from amplifier toward reference rail.', 'Model ID already includes multiplicity; estimate omits output-FET displacement/junction currents and input-feedback gate currents.', 'Compensation current follows resistor KCL at its internal node; this does not recover complete ADC load current.', 'No demand/capacity bound, slew-limit claim or causal attribution solely from this current record.'])
(P/'evidence/reference-dynamic-current.json').write_text(json.dumps(out,indent=2)+'\n')
for x in rows:print(x['rail'],x['net_channel_range_ma'],x['compensation_range_ma'],x['estimated_delivered_range_ma'])
