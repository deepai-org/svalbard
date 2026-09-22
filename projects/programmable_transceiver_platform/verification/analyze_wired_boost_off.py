#!/usr/bin/env python3
"""Compare hard-disabled BOOST to baseline with consecutive signed bit scoring."""
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
PROJECT=ROOT/'projects/programmable_transceiver_platform'
BASE=ROOT/'scratch/transceiver-wired-internal'
WORK=ROOT/'scratch/transceiver-wired-boost-off'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((WORK/'result.json').read_text())
baseline=json.loads((BASE/'result.json').read_text())
bits=json.loads((ROOT/'scratch/transceiver-wired-pulse-data-gf180/result.json').read_text())['stimulus_bits']
def measure(folder,expected_hash):
    wave=folder/'changing.dat'; assert sha(wave)==expected_hash
    x=np.loadtxt(wave,skiprows=1); t=x[:,0]
    branches={}
    for b,col,q in [('even',5,7),('odd',6,8)]:
        c=x[:,col]; ids=np.where((c[:-1]>=1.65)&(c[1:]<1.65))[0]
        falls=[float(t[i]+(1.65-c[i])*(t[i+1]-t[i])/(c[i+1]-c[i])) for i in ids]
        times=[f+100e-12 for f in falls if 6e-9<f<16e-9]
        branches[b]=dict(times_s=times,output_diff_v=[float(np.interp(s,t,x[:,q])) for s in times])
    candidates=[]
    for delay in range(0,2401,25):
        stream=[]; margins=[]; detail={}
        for b,d in branches.items():
            ids=[int(np.floor((s-delay*1e-12-1e-9+200e-12)/400e-12)) for s in d['times_s']]
            assert all(0<=i<len(bits) for i in ids)
            signed=[v*(2*bits[i]-1) for v,i in zip(d['output_diff_v'],ids)]
            detail[b]=dict(bit_indices=ids,wrong_polarity=sum(v<=0 for v in signed),minimum_signed_v=min(signed) if signed else None)
            stream.extend(zip(d['times_s'],ids)); margins+=signed
        ordered=[i for _,i in sorted(stream)]
        if len(ordered)>=20 and all(b==a+1 for a,b in zip(ordered,ordered[1:])):
            candidates.append(dict(delay_ps=delay,wrong_polarity=sum(v<=0 for v in margins),below_500mv=sum(v<.5 for v in margins),minimum_signed_v=min(margins),branches=detail))
    best=min(candidates,key=lambda c:(c['below_500mv'],c['wrong_polarity'],-c['minimum_signed_v'])) if candidates else None
    m=t>=6e-9
    reset=[]
    for bit in (20,30):
        start=1e-9+bit*400e-12-200e-12
        mask=(t>start)&(t<start+800e-12)
        ids=np.where(mask)[0]; j=ids[np.argmin(x[mask,22])]
        low=mask&(x[:,22]<.8)
        loids=np.where(low)[0]
        k=loids[np.argmax(np.minimum(x[low,17],x[low,18]))] if len(loids) else j
        reset.append(dict(bit=bit,min_sense_v=float(x[j,22]),boost_at_min_sense_v=float(x[j,23]),
            xp_at_min_sense_v=float(x[j,17]),xn_at_min_sense_v=float(x[j,18]),
            best_lower_dynamic_node_below_0p8_v=float(min(x[k,17],x[k,18])),
            dynamic_difference_at_best_v=float(x[k,17]-x[k,18]),
            input_nodes_at_best_v=[float(x[k,19]),float(x[k,20])]))
    return dict(branches=branches,best=best,valid_latency_candidates=candidates,
        sample_count=sum(len(d['times_s']) for d in branches.values()),
        current_a=float(np.trapezoid(x[m,13],t[m])/(t[-1]-t[m][0])),reset=reset)
r['baseline']=measure(BASE,baseline['source_sha256']['waveform'])
r['boost_off']=measure(WORK,r['source_sha256']['waveform'])
r['capture_fall_shift_ps']={}
for branch in ('even','odd'):
    a=r['baseline']['branches'][branch]['times_s']
    b=r['boost_off']['branches'][branch]['times_s']
    assert len(a)==len(b)
    differences=[(v-u)*1e12 for u,v in zip(a,b)]
    r['capture_fall_shift_ps'][branch]=dict(min=min(differences),max=max(differences))
r['analysis_sha256']=sha(Path(__file__))
r['reproduction']='make transceiver-wired-boost-off; python3 projects/programmable_transceiver_platform/verification/analyze_wired_boost_off.py'
(PROJECT/'evidence/wired-boost-off-screen.json').write_text(json.dumps(r,indent=2)+'\n')
for name in ('baseline','boost_off'):
 d=r[name]; print(name,json.dumps(dict(best=d['best'],samples=d['sample_count'],current=d['current_a'],reset=d['reset']),indent=2))
