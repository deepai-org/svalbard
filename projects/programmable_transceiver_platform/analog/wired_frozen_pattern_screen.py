#!/usr/bin/env python3
"""Independent longer data screen with previously frozen sampling and alignment."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import numpy as np
BASE=Path('/case'); OUT=Path('/work'); SRC=Path('/src')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((BASE/'result.json').read_text())
assert sha(BASE/'changing.spice')==r['source_sha256']['deck']
plan_path=Path('/evidence/wired-hold-window-analysis.json')
plan=json.loads(plan_path.read_text())['fixed_next_test']
assert plan['sample_offset_after_capture_fall_ps']==400
assert plan['first_scored_even_bit']==11 and plan['first_scored_odd_bit']==12
assert plan['bit_increment_per_branch']==2 and plan['capture_fall_window_start_ns']==6
for k,p in dict(pulse=Path('/baseline/pex/clock_pulse_generator.pex.spice'),bridge=SRC/'capture_clock_bridge/capture_clock_bridge.pex.spice',lane=SRC/'lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice').items():
    assert sha(p)==r['macro_sha256'][k]
# Explicit seven-stage recurrence; verify a full nonzero 127-state period.
state=0x5b; states=[]; period_bits=[]
while state not in states:
    states.append(state); period_bits.append((state>>6)&1)
    state=((state<<1)&127)|(((state>>6)^(state>>5))&1)
assert len(states)==127 and state==0x5b and 0 not in states
bits=period_bits[:80]
def pwl(sign):
    points=[(0,0),(.5e-9,1.65+sign*.1*(2*bits[0]-1))]
    for i in range(1,len(bits)):
        time=.8e-9+i*400e-12
        points.extend([(time-10e-12,1.65+sign*.1*(2*bits[i-1]-1)),(time+10e-12,1.65+sign*.1*(2*bits[i]-1))])
    return 'PWL('+' '.join(f'{t:.12g} {v:.8g}' for t,v in points)+')'
deck=(BASE/'changing.spice').read_text()
for name,sign in [('VRXP',1),('VRXN',-1)]:
    deck,count=re.subn(rf'^{name} (\S+) 0 PWL\(.*?\)$',lambda m:f'{name} {m[1]} 0 '+pwl(sign),deck,flags=re.M)
    assert count==1
assert 'tran 2p 17n uic' in deck
deck=deck.replace('tran 2p 17n uic','tran 2p 33n uic')
(OUT/'changing.spice').write_text(deck)
# Preserve commitments before simulation; analysis never searches a delay.
(OUT/'stimulus.json').write_text(json.dumps(dict(bits=bits,seed=0x5b,verified_period=127,plan=plan),indent=2)+'\n')
with (OUT/'changing.log').open('w') as log:
    subprocess.run(['ngspice','-b',str(OUT/'changing.spice')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1500)
x=np.loadtxt(OUT/'changing.dat',skiprows=1); t=x[:,0]
assert x.shape[1]==24 and t[-1]>=32.999e-9 and np.isfinite(x).all()
branches={}; stream=[]
for branch,c,q,first in [('even',5,7,11),('odd',6,8,12)]:
    clock=x[:,c]; ix=np.where((clock[:-1]>=1.65)&(clock[1:]<1.65))[0]
    falls=[float(t[i]+(1.65-clock[i])*(t[i+1]-t[i])/(clock[i+1]-clock[i])) for i in ix]
    falls=[f for f in falls if 6e-9<f<32e-9]
    samples=[]
    for ordinal,fall in enumerate(falls):
        bit=first+2*ordinal; assert bit<len(bits)
        value=float(np.interp(fall+400e-12,t,x[:,q])); signed=value*(2*bits[bit]-1)
        stream.append((fall,bit))
        samples.append(dict(bit=bit,expected=bits[bit],capture_fall_s=fall,output_diff_v=value,signed_v=signed))
    branches[branch]=dict(samples=samples,wrong_polarity=sum(s['signed_v']<=0 for s in samples),
                          below_500mv=sum(s['signed_v']<.5 for s in samples),minimum_signed_v=min(s['signed_v'] for s in samples))
ordered=[i for _,i in sorted(stream)]
consecutive=all(b==a+1 for a,b in zip(ordered,ordered[1:]))
count_ok=len(branches['even']['samples'])==33 and len(branches['odd']['samples'])==32
m=t>=6e-9
result=dict(status='independent_pattern_screen_not_lane_qualification',environment=r['environment'],
    circuit_change='None relative to BOOST-disabled case; only input pattern and transient length changed.',
    bits=bits,stimulus_seed=0x5b,verified_lfsr_period=127,frozen_plan=plan,branches=branches,
    consecutive=consecutive,expected_sample_count_met=count_ok,total_samples=len(stream),
    screen_pass=consecutive and count_ok and all(d['below_500mv']==0 for d in branches.values()),
    current_a=float(np.trapezoid(x[m,13],t[m])/(t[-1]-t[m][0])),
    source_sha256=dict(runner=sha(Path(__file__)),prior_record=sha(BASE/'result.json'),prior_deck=sha(BASE/'changing.spice'),plan=sha(plan_path),deck=sha(OUT/'changing.spice'),waveform=sha(OUT/'changing.dat')),
    macro_sha256=r['macro_sha256'],limitations=['One 80-bit pattern at nominal process/supply/temperature.',
    'Ideal upstream clock, input pin stimulus and DC biases; no channel, TX or CDR.',
    '400 ps observation is not an implemented retiming clock. Six-ns scoring start is not qualified acquisition.',
    'BOOST hard-disabled; no programmable gating circuit or changed-parent physical signoff.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(screen_pass=result['screen_pass'],samples=result['total_samples'],current_a=result['current_a'],branches={k:{q:v for q,v in d.items() if q!='samples'} for k,d in branches.items()}),indent=2))
