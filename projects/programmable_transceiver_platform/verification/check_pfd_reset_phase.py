#!/usr/bin/env python3
"""Compare actual PFD outputs and pump charge, without presuming phase branch."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pfd-reset-phase';B=R/'scratch/transceiver-pfd-pump-breakpoint'
r=json.loads((W/'result.json').read_text());original=B/'pulse_skew-10.spice';assert hashlib.sha256(original.read_bytes()).hexdigest()==r['baseline_deck_sha256'];assert {c['reset_release_ns'] for c in r['cases']}=={80,90}
for path,digest in r['source_sha256'].items():assert hashlib.sha256((P/'analog'/path.removeprefix('/screen/')).read_bytes()).hexdigest()==digest
for c in r['cases']:
 name=c['name'];release=c['reset_release_ns']
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text();restored=d.split('.control')[0].replace(f'VRN RN 0 PWL(0 0 {release}n 0 {release+.1:g}n 3.3)','VRN RN 0 PWL(0 0 90n 0 90.1n 3.3)');assert restored==original.read_text().split('.control')[0]
 assert 'tran 2p 321n 0 2p uic' in d
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==9 and np.isfinite(a).all() and a[-1,0]>=321e-9
 w=a[(a[:,0]>=203e-9)&(a[:,0]<=305.4e-9)];t=w[:,0];assert np.all(w[:,3]>2.97)
 ref_edges=[];fb_edges=[]
 for col,edges in ((1,ref_edges),(2,fb_edges)):
  indices=np.flatnonzero((a[:-1,col]<1.65)&(a[1:,col]>=1.65));edges.extend((a[indices,0]+(1.65-a[indices,col])*(a[indices+1,0]-a[indices,0])/(a[indices+1,col]-a[indices,col]))*1e9)
 assert abs(ref_edges[0]-100.05)<.001 and abs(fb_edges[0]-90.05)<.001
 c.update(measurement_window_ns=[203,305.4],reference_rising_edges_ns=ref_edges,feedback_rising_edges_ns=fb_edges,up_high_time_ns=float(np.trapezoid((w[:,4]>1.65).astype(float),t)*1e9),dn_high_time_ns=float(np.trapezoid((w[:,5]>1.65).astype(float),t)*1e9),pump_charge_fc=float(np.trapezoid(w[:,7],t)*1e15),control_change_v=float(w[-1,6]-w[0,6]),final_control_v=float(a[-1,6]))
r['status']='controlled_reset_phase_waveforms_audited';r['limitations']=['Ideal feedback/reference clocks, seeded filter and ideal bias sources; not autonomous lock or startup qualification.', 'Two deterministic reset timings do not characterize metastability or recovery/removal margins.', 'Measured branch and pump direction concern this fixture, not arbitrary loop acquisition behavior.']
(P/'evidence/pfd-reset-phase-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps([{k:c[k] for k in ('name','up_high_time_ns','dn_high_time_ns','pump_charge_fc','control_change_v','final_control_v')} for c in r['cases']],indent=2))
