#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-driver-mim-ac'
r=json.loads((W/'result.json').read_text());assert {(c['corner'],c['compensation_pf']) for c in r['cases']}=={(k,v) for k in ('typical','ss','ff') for v in (.5,1,2)}
for c in r['cases']:
 name=c['name']
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text()
 assert len([line for line in d.splitlines() if line.startswith('XC')])==512
 assert 'XS IP IN HP HN VDD 0 VDD 0 wifi_if_transmission_gate' in d
 assert 'VP GP 0 DC 1.65 AC .5' in d and 'VN GN 0 DC 1.65 AC -.5' in d
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==5 and np.isfinite(a).all() and a[0,0]<=1e3 and a[-1,0]>=1e10
 gain=np.hypot(a[:,1],a[:,2]);peak=int(np.argmax(gain));assert gain[0]>.5
 c.update(dc_approx_gain=float(gain[0]),peak_gain=float(gain[peak]),peak_frequency_hz=float(a[peak,0]),peaking_db=float(20*np.log10(gain[peak]/gain[0])))
r['status']='isolated_track_mode_closed_loop_response_checked';r['phase_margin_verified']=False
(P/'evidence/adc-driver-mim-ac.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:c[k] for k in ('name','dc_approx_gain','peak_gain','peak_frequency_hz','peaking_db')} for c in r['cases']],indent=2))
