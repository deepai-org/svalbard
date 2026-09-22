#!/usr/bin/env python3
"""Conditional small-signal poles; not a substitute for transistor loop evidence."""
import json,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform'
tuning=json.loads((P/'evidence/vco-local-tuning.json').read_text());rows=[]
for kv in tuning['slopes_hz_per_v']:
 # Kpd=I/(2pi), Kv_rad=2pi*Kv_Hz; L=I*Kv_Hz*Z/(N*s).
 I=20e-6;N=128;R=1e4;Cz=50e-12;Cp=2e-12;K=I*kv/N
 poles=np.roots([R*Cp*Cz,Cp+Cz,K*R*Cz,K])
 rows.append(dict(kv_hz_per_v=kv,poles_rad_per_s=[[float(z.real),float(z.imag)] for z in poles],all_poles_left_half_plane=bool(np.all(poles.real<0)),four_time_constant_envelope_s=float(4/min(-poles.real))))
r=dict(status='conditional_linearized_loop_scenario_not_lock_evidence',cases=rows,assumptions=['Ideal averaged matched 20uA pump and ideal divide128.', 'Measured local VCO slopes treated constant; loop excursions can invalidate this.', 'Ideal R=10kohm, Cz=50pF, Cp=2pF; ignores VCO input admittance, delay, switching, offset, saturation and noise.', 'Negative real poles in this simplified model do not prove transistor-loop stability.'])
(P/'evidence/pll-linear-envelope.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
