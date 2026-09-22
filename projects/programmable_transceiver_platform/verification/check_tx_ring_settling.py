#!/usr/bin/env python3
"""Preserve partial failures; score only complete late windows, not nominal end time."""
import hashlib,json,re
from pathlib import Path
import numpy as np
from tx_cycle_metrics import cycle_amplitude
from tx_load_power import delivered_currents
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-ring-settling';B=R/'scratch/transceiver-tx-startup-state'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());src=B/'ring_probe.spice';assert sha(src)==m['baseline_deck_sha256']
d=(W/'settling.spice').read_text();assert d.replace('tran 2p 600n 0 2p uic','tran 2p 40n 0 2p uic').replace('/work/settling.dat','/work/ring_probe.dat')==src.read_text();assert sha(W/'settling.spice')==m['deck_sha256_before']
for line in ['VTERM TERM 0 2.15','RP TERM OP 100','RN TERM ON 100','VCM CM 0 1.89','RLP CM RFP 50','RLN CM RFN 50','VDD VDD 0 3.3','VDRV VDRV 0 3.3']:
 assert line in d.splitlines()
out=dict(status='pending',completed=False,declared_extension_verified=True,windows=[])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert m['source_sha256_before']==r['source_sha256_before']==r['source_sha256_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('settling'+ext))==h
 log=(W/'settling.log').read_text().lower();failure=re.search(r'timestep too small; time = ([0-9.e+-]+)',log);out.update(status='terminal',provenance=r,failure_time_s=float(failure.group(1)) if failure else None)
 if (W/'settling.dat').exists():
  with (W/'settling.dat').open() as f:h=f.readline().lower().split()
  assert h==['time']+next(l for l in d.splitlines() if l.startswith('save ')).lower().split()[1:]
  a=np.loadtxt(W/'settling.dat',skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  out.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(r['returncode']==0 and not r['timed_out'] and 'aborted' not in log and a[-1,0]>=600e-9))
  for start,stop in [(30,40),(390,400),(490,500),(590,600)]:
   if a[-1,0]<stop*1e-9:continue
   t=np.r_[start*1e-9,a[(a[:,0]>start*1e-9)&(a[:,0]<stop*1e-9),0],stop*1e-9]
   def v(k):return np.interp(t,a[:,0],a[:,h.index(k)])
   def avg(y):return float(np.trapezoid(y,t)/(t[-1]-t[0]))
   y=v('v(cp)')-v('v(cn)');ix=np.where((y[:-1]<0)&(y[1:]>=0))[0];cross=t[ix]-(t[ix+1]-t[ix])*y[ix]/(y[ix+1]-y[ix]);freq=float((len(cross)-1)/(cross[-1]-cross[0])) if len(cross)>1 else None
   amps=cycle_amplitude(t,v('v(rfp)')-v('v(rfn)'),cross)
   # Source-to-load sign convention follows verified resistor endpoints.
   term_current,cm_current=delivered_currents(v('v(op)'),v('v(on)'),v('v(rfp)'),v('v(rfn)'))
   source_power=dict(ring=-3.3*avg(v('i(vpll)')),buffers=-3.3*avg(v('i(vlobuf)')),dac_logic=-3.3*avg(v('i(vdrv)')),reference_feed=-3.3*avg(v('i(vdd)')),dac_termination=2.15*avg(term_current),rf_load_bias=1.89*avg(cm_current))
   resistor_heat=avg(((2.15-v('v(op)'))**2+(2.15-v('v(on)'))**2)/100+((1.89-v('v(rfp)'))**2+(1.89-v('v(rfn)'))**2)/50)
   out['windows'].append(dict(window_ns=[start,stop],signed_source_power_w=source_power,accounted_source_power_sum_w=sum(source_power.values()),four_load_resistors_dissipation_w=resistor_heat,complete_carrier_cycles=len(amps),rf_cycle_fundamental_peak_range_v=[min(amps),max(amps)] if amps else None,bias_range_v=[float(v('v(bn)').min()),float(v('v(bn)').max())],bias_mean_v=avg(v('v(bn)')),dac_differential_mean_v=avg(v('v(op)')-v('v(on)')),rf_peak_to_peak_v=float(np.ptp(v('v(rfp)')-v('v(rfn)'))),ring_frequency_hz=freq,ring_average_power_w=-3.3*avg(v('i(vpll)')),buffer_average_power_w=-3.3*avg(v('i(vlobuf)'))))
out['limitations']=['Seeded ring, ideal biases/supplies; no cold oscillator startup, PLL lock or phase-noise claim.', 'Fullscale NMOS TX only; no quadrature, modulated spectrum or noise/mismatch qualification.', 'Late windows diagnose evolution, not a complete settling proof or allocated RF accuracy test.', 'Power sum excludes unsaved CTRL/REGEN bias-source currents and startup energy; signed ideal-source delivery is not a complete chip dissipation estimate. Resistor dissipation is a separate subset, not added twice.']
(P/'evidence/tx-ring-settling.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='provenance'},indent=2))
