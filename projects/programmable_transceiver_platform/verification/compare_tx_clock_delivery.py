#!/usr/bin/env python3
"""Compare delivered waveforms, not phase noise or a complete causal attribution."""
import hashlib,json
from pathlib import Path
import numpy as np
from tx_cycle_metrics import cycle_amplitude
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for label,folder,name,start,stop in [('ideal_upstream','transceiver-tx-buffered-lo','nmos_c255',6,10),('actual_ring','transceiver-tx-ring-settling','settling',590,600)]:
 W=R/'scratch'/folder;r=json.loads((W/'result.json').read_text());c=next(c for c in r['cases'] if c['name']==name) if 'cases' in r else r
 assert c['returncode']==0 and not c['timed_out']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 assert a[-1,0]>=stop*1e-9
 t=np.r_[start*1e-9,a[(a[:,0]>start*1e-9)&(a[:,0]<stop*1e-9),0],stop*1e-9]
 def v(k):return np.interp(t,a[:,0],a[:,h.index(k)])
 lo=v('v(lo)');ix=np.where((lo[:-1]<1.65)&(lo[1:]>=1.65))[0];cross=t[ix]+(t[ix+1]-t[ix])*(1.65-lo[ix])/(lo[ix+1]-lo[ix]);amp=cycle_amplitude(t,v('v(rfp)')-v('v(rfn)'),cross)
 rows.append(dict(case=label,window_ns=[start,stop],complete_cycles=len(amp),lo_range_v=[float(lo.min()),float(lo.max())],lob_range_v=[float(v('v(lob)').min()),float(v('v(lob)').max())],buffer_input_range_v=[float(v('v(loin)').min()),float(v('v(loin)').max())],rf_fundamental_peak_range_v=[min(amp),max(amp)],artifacts_sha256=c['artifacts_sha256']))
out=dict(status='clock_delivery_comparison',cases=rows,limitations=['Same downstream NMOS topology, but source circuit, initialization and observation duration differ. No isolated waveform-mechanism attribution.', 'Per-cycle amplitude uses delivered LO crossing reference and linear phase; not a phase-noise or EVM measurement.', 'No timestep/PVT/mismatch or extracted validation.'])
(P/'evidence/tx-clock-delivery-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
