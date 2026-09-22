#!/usr/bin/env python3
"""Retain paired-run signal, settling and clock observations without EVM claims."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-rf-autonomous-chain'
r=json.loads((W/'result.json').read_text());waves=[]
for c in r['cases']:
 name=f"a{c['amplitude_v']:g}"
 for s,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+s)).read_bytes()).hexdigest()==h
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert np.isfinite(a).all();waves.append(a)
 late=a[a[:,0]>=100e-9];t=late[:,0];v=late[:,1];i=np.where((v[:-1]<0)&(v[1:]>=0))[0];edges=t[i]+(t[i+1]-t[i])*(-v[i])/(v[i+1]-v[i])
 c['measured_late_vco_frequency_hz']=(len(edges)-1)/(edges[-1]-edges[0])
 c['measured_if_hz']=r['rf_hz']-c['measured_late_vco_frequency_hz']
ts=np.array(r['cases'][0]['sample_times_s']);y=np.array(r['baseline_subtracted_samples_v'])
blocks=[]
for sl in (slice(0,4),slice(4,8)):
 t=ts[sl];x=np.column_stack([np.ones(len(t)),np.sin(2*np.pi*1e7*t),np.cos(2*np.pi*1e7*t)]);c=np.linalg.lstsq(x,y[sl],rcond=None)[0]
 blocks.append(dict(mean_v=float(c[0]),tone_gain=float(np.hypot(c[1],c[2])/.001),sin_v=float(c[1]),cos_v=float(c[2])))
r['four_sample_block_diagnostics']=blocks
a,b=waves;b=b[b[:,0]>=100e-9];t=b[:,0];weights=np.sqrt(np.gradient(t))
x=np.column_stack([np.ones(len(t)),np.sin(2*np.pi*1e7*t),np.cos(2*np.pi*1e7*t)])
r['baseline_subtracted_stage_tone_gain']={}
for label,col in [('mixer_output',2),('filter_output',3)]:
 y=b[:,col]-np.interp(t,a[:,0],a[:,col]);c=np.linalg.lstsq(x*weights[:,None],y*weights,rcond=None)[0]
 r['baseline_subtracted_stage_tone_gain'][label]=float(np.hypot(c[1],c[2])/.001)

r['dependency_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'projects/programmable_transceiver_platform/analog'/f for f in ('bb_filter_section.spice','bb_pmos_gain.spice','lo_buffer.spice')]+[ROOT/'ip/blocks/analog/wifi_80211b/rf_if_transmission_gate/rf_if_transmission_gate.spice']}
(ROOT/'projects/programmable_transceiver_platform/evidence/rf-autonomous-chain-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(gain=r['held_tone_gain'],residual_v=r['fit_residual_rms_v'],blocks=blocks,currents=[c['rf_filter_current_a'] for c in r['cases']],ifs=[c['measured_if_hz'] for c in r['cases']]),indent=2))
