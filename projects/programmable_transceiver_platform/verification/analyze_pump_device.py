#!/usr/bin/env python3
"""Compare model voltage conventions with physical terminals before headroom claims."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pump-device'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ap=P/'evidence/pump-device.json';audit=json.loads(ap.read_text());assert audit['completed'] and audit['original_vectors_identical']
for ext,h in audit['provenance']['artifacts_sha256'].items():assert sha(W/('early'+ext))==h
with (W/'early.dat').open() as f:header=f.readline().lower().split()
a=np.loadtxt(W/'early.dat',skiprows=1);a=a[(a[:,0]>=200e-9)&(a[:,0]<=790e-9)];t=a[:,0]
def v(n):return a[:,header.index(n)]
# Named drain, gate, source values from the actual subcircuit, in volts.
terminals={'xps':(v('v(xcp.ps)'),v('v(bpcp)'),np.full(len(t),3.3)),
 'xpu':(v('v(ctrl)'),v('v(xcp.upb)'),v('v(xcp.ps)')),
 'xnd':(v('v(ctrl)'),v('v(dn)'),v('v(xcp.ns)')),
 'xns':(v('v(xcp.ns)'),v('v(bncp)'),np.zeros(len(t)))}
rows=[]
for name,(drain,gate,source) in terminals.items():
 probe=lambda q:v(f'@m.xcp.{name}.m0[{q}]')
 vd,vg=probe('vds'),probe('vgs');physical_vd=drain-source;physical_vg=gate-source
 errors={str(sign):dict(vds_max_error_v=float(np.max(abs(vd-sign*physical_vd))),vgs_max_error_v=float(np.max(abs(vg-sign*physical_vg)))) for sign in (1,-1)}
 # Do not silently select a convention if probes and terminals disagree.
 sign=next((sign for sign in (1,-1) if max(errors[str(sign)].values())<1e-6),None)
 row=dict(device=name,model_voltage_vs_physical_terminal_errors=errors,verified_voltage_sign=sign,id_range_a=[float(probe('id').min()),float(probe('id').max())])
 if sign is not None:
  forward=vd>=0;inversion=vg>probe('vth');eligible=forward&inversion;bad=eligible&(vd<probe('vdsat'))
  row.update(model_forward_inversion_time_fraction=float(np.trapezoid(eligible.astype(float),t)/(t[-1]-t[0])),model_below_vdsat_time_fraction=float(np.trapezoid(bad.astype(float),t)/(t[-1]-t[0])),minimum_vds_minus_vdsat_when_forward_inversion_v=float((vd-probe('vdsat'))[eligible].min()) if eligible.any() else None)
 rows.append(row)
y=v('v(ref)')-1.65;k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));edges=t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k]
start,stop=edges[0],edges[-1];x=np.r_[start,t[(t>start)&(t<stop)],stop];count=len(edges)-1
integral=lambda wave:float(np.trapezoid(np.interp(x,t,wave),x))/count
charges={name:integral(v(f'@m.xcp.{name}.m0[id]')) for name in terminals}
observed=integral(v('i(vsense)'))
charge_diagnostic=dict(reference_cycles=count,reported_id_integral_per_cycle_c=charges,pmos_minus_nmos_switch_id_integral_c=charges['xpu']-charges['xnd'],measured_pump_charge_per_cycle_c=observed,difference_c=observed-(charges['xpu']-charges['xnd']))
out=dict(completed=True,audit_sha256=sha(ap),cases=rows,charge_diagnostic=charge_diagnostic,limitations=['Named-terminal voltage convention verified against waveform; model inversion/saturation flags are diagnostics, not silicon compliance guarantees.','id includes the model reported channel-current convention and is not summed as displacement-inclusive output current.','Threshold crossing duty uses sampled-state trapezoidal weighting; no precise timing limit claimed.','Only nominal clamped-output history; no acquisition, mismatch or intrinsic noise qualification.'])
(P/'evidence/pump-device-analysis.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
