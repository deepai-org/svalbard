#!/usr/bin/env python3
"""Summarize observed internal precharge and evaluation state near missed zeros."""
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'scratch/transceiver-wired-internal'
r=json.loads((WORK/'result.json').read_text())
wave=WORK/'changing.dat'
assert hashlib.sha256(wave.read_bytes()).hexdigest()==r['source_sha256']['waveform']
x=np.loadtxt(wave,skiprows=1); t=x[:,0]; sense=x[:,22]
assert x.shape[1]==24 and np.isfinite(x).all()
def crossing(level,rising,start,end):
    m=((sense[:-1]<level)&(sense[1:]>=level) if rising else
       (sense[:-1]>=level)&(sense[1:]<level))
    edges=[float(t[i]+(level-sense[i])*(t[i+1]-t[i])/(sense[i+1]-sense[i])) for i in np.where(m)[0]]
    found=[s for s in edges if start<s<end]; assert len(found)==1,(level,found)
    return found[0]
def state(time):
    at=lambda col:float(np.interp(time,t,x[:,col]))
    return dict(time_s=time,pin_diff_v=at(1)-at(2),raw_rx_diff_v=at(14)-at(15),
        converter_diff_v=at(9)-at(10),sense_gate_v=at(22),boost_gate_v=at(23),
        xp_v=at(17),xn_v=at(18),nip_v=at(19),nin_v=at(20),ntail_v=at(21),
        capture_clock_v=at(5),output_diff_v=at(7))
rows=[]
for bit in (20,30):
    start=1e-9+bit*400e-12-200e-12
    m=(t>start)&(t<start+800e-12)
    indices=np.where(m)[0]; minimum=indices[np.argmin(sense[m])]
    fall=crossing(.8,False,start,start+800e-12)
    rise=crossing(.8,True,start,start+800e-12)
    low=(t>=fall)&(t<=rise)
    lowids=np.where(low)[0]
    common=np.minimum(x[:,17],x[:,18])
    best=lowids[np.argmax(common[low])]
    rows.append(dict(bit=bit,minimum_sense=state(t[minimum]),
        best_lower_dynamic_node_during_sense_below_0p8=state(t[best]),
        sense_below_0p8_ps=(rise-fall)*1e12,
        boost_gate_min_during_sense_below_0p8=float(x[low,23].min()),
        boost_gate_max_during_sense_below_0p8=float(x[low,23].max()),
        rising_crossings=[dict(observation_level_v=level,**state(crossing(level,True,start,start+800e-12))) for level in (.5,.8,1.65)]))
r['observations']=rows
r['analysis_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
r['limitations']=['Named local PEX node observations; not all segments of the parasitic network.',
                  'Voltage observation levels are not characterized decision thresholds.',
                  'No circuit modification, new passing data point, or process/noise qualification.']
out=ROOT/'projects/programmable_transceiver_platform/evidence/wired-internal-screen.json'
out.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(rows,indent=2))
