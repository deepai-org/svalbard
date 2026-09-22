#!/usr/bin/env python3
"""Bind phase experiment and localize the two original missed zeros."""
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'scratch/transceiver-wired-phase'
BASE=ROOT/'scratch/transceiver-wired-pulse-data-gf180'
r=json.loads((WORK/'result.json').read_text())
for name,folder in [('baseline',BASE),('shifted',WORK)]:
    p=folder/'changing.dat'
    assert hashlib.sha256(p.read_bytes()).hexdigest()==r[name]['waveform_sha256']
    x=np.loadtxt(p,skiprows=1); t=x[:,0]; shift=r[name]['data_phase_ps']*1e-12
    rows=[]
    for bit in (20,30):
        start=1e-9+bit*400e-12+shift
        windows={}
        for label,a,b in [('zero_bit_interior',start+20e-12,start+380e-12),
                          ('bit_start_to_1p3ns_later',start,start+1.3e-9)]:
            m=(t>=a)&(t<=b); assert m.sum()>100
            pin=(x[:,1]-x[:,2])[m]; fe=(x[:,9]-x[:,10])[m]
            windows[label]=dict(start_s=a,end_s=b,pin_min_v=float(pin.min()),pin_max_v=float(pin.max()),
                                even_converter_min_v=float(fe.min()),even_converter_max_v=float(fe.max()))
        clock=x[:,5]
        edges=np.where((clock[:-1]<1.65)&(clock[1:]>=1.65))[0]
        rises=[float(t[i]+(1.65-clock[i])*(t[i+1]-t[i])/(clock[i+1]-clock[i])) for i in edges]
        rise=next(s for s in rises if s>=start)
        rows.append(dict(input_bit_index=bit,expected_bit=0,windows=windows,
                         first_even_capture_rise_after_bit_start_s=rise,
                         even_converter_at_capture_rise_v=float(np.interp(rise,t,x[:,9]-x[:,10]))))
    r[name]['original_missed_zero_windows']=rows
r['analysis_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
r['reproduction']='make transceiver-wired-phase; python3 projects/programmable_transceiver_platform/verification/analyze_wired_phase.py'
out=ROOT/'projects/programmable_transceiver_platform/evidence/wired-phase-screen.json'
out.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({k:dict(best=r[k]['best'],current_a=r[k]['current_a'],zero_windows=r[k]['original_missed_zero_windows']) for k in ('baseline','shifted')},indent=2))
