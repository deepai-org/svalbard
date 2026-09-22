#!/usr/bin/env python3
"""One-factor data phase experiment using the exact pass-109 extraction stack."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--shift-ps', type=int, choices=(-100,-200,-300), default=-100)
args=parser.parse_args()
BASE=Path('/baseline'); OUT=Path('/work'); SRC=Path('/src')
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((BASE/'result.json').read_text())
old=next(c for c in base['cases'] if c['id']=='changing')
assert sha(BASE/'changing.spice')==old['deck_sha256']
assert sha(BASE/'changing.dat')==old['waveform_sha256']
for name,p in dict(pulse=BASE/'pex/clock_pulse_generator.pex.spice',
                   bridge=SRC/'capture_clock_bridge/capture_clock_bridge.pex.spice',
                   lane=SRC/'lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice').items():
    assert sha(p)==base['source_sha256'][name]
    physical=(BASE/'pulse-physical.json' if name=='pulse' else p.parent/'physical_result.json')
    record=json.loads(physical.read_text())
    assert record['result']=='pass' and record['pex_sha256']==sha(p)
shift=args.shift_ps*1e-12
text=(BASE/'changing.spice').read_text()
for source in ('VRXP','VRXN'):
    pattern=rf'^{source} (.*?) PWL\((.*?)\)$'
    found=re.search(pattern,text,re.M); assert found
    nums=list(map(float,found[2].split())); assert len(nums)%2==0
    pts=[(t+shift if t>1e-9 else t,v) for t,v in zip(nums[::2],nums[1::2])]
    assert all(pts[i][0]<pts[i+1][0] for i in range(len(pts)-1))
    line=source+' '+found[1]+' PWL('+' '.join(f'{t:.12g} {v:.8g}' for t,v in pts)+')'
    text=text[:found.start()]+line+text[found.end():]
text=text.replace('/work/pex/clock_pulse_generator.pex.spice','/baseline/pex/clock_pulse_generator.pex.spice')
# Append diagnostics without moving any existing waveform columns.
text=text.replace(' isupply\nquit', ' isupply v(RXOP) v(RXON)\nquit')
assert 'isupply v(RXOP) v(RXON)' in text
# The new /work mount preserves the original output path name in the deck.
deck=OUT/'changing.spice'; deck.write_text(text)
with (OUT/'changing.log').open('w') as log:
    subprocess.run(['ngspice','-b',str(deck)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)

def measure(path,phase):
    x=np.loadtxt(path,skiprows=1); t=x[:,0]
    assert t[-1]>=16.999e-9 and np.isfinite(x).all()
    branches={}
    for b,c,q in [('even',5,7),('odd',6,8)]:
        indices=np.where((x[:-1,c]>=1.65)&(x[1:,c]<1.65))[0]
        falls=[float(t[i]+(1.65-x[i,c])*(t[i+1]-t[i])/(x[i+1,c]-x[i,c])) for i in indices]
        times=[f+100e-12 for f in falls if 6e-9<f<16e-9]
        assert len(times)>=10
        branches[b]=dict(sample_times_s=times,differential_output_v=[float(np.interp(s,t,x[:,q])) for s in times])
    rows=[]
    for delay_ps in range(0,2401,25):
        margins=[]; detail={}
        for b,d in branches.items():
            ids=[int(np.floor((s-delay_ps*1e-12-1e-9-phase)/400e-12)) for s in d['sample_times_s']]
            assert all(0<=i<len(base['stimulus_bits']) for i in ids)
            signed=[v*(2*base['stimulus_bits'][i]-1) for v,i in zip(d['differential_output_v'],ids)]
            detail[b]=dict(bit_indices=ids,wrong_polarity=sum(v<=0 for v in signed),below_500mv=sum(v<.5 for v in signed),minimum_signed_v=min(signed))
            margins.extend(signed)
        rows.append(dict(delay_ps=delay_ps,wrong_polarity=sum(v<=0 for v in margins),below_500mv=sum(v<.5 for v in margins),minimum_signed_v=min(margins),branches=detail))
    best=min(rows,key=lambda r:(r['below_500mv'],r['wrong_polarity'],-r['minimum_signed_v']))
    m=t>=6e-9
    return dict(data_phase_ps=phase*1e12,branches=branches,latency_scan=rows,best=best,
                current_a=float(np.trapezoid(x[m,13],t[m])/(t[-1]-t[m][0])),
                waveform_sha256=sha(path))
result=dict(status='diagnostic_not_lane_qualification',environment=base['environment'],
    baseline=measure(BASE/'changing.dat',0),shifted=measure(OUT/'changing.dat',shift),
    source_sha256=dict(runner=sha(Path(__file__)),baseline_result=sha(BASE/'result.json'),
                       baseline_deck=sha(BASE/'changing.spice'),shifted_deck=sha(deck),
                       **{k:base['source_sha256'][k] for k in ('pulse','bridge','lane')}),
    limitation='One fixed pattern, nominal environment, ideal upstream clock and RX pin source. Common latency fitted retrospectively; no acquisition, BER or aperture-width claim.',
    raw_rx_waveform_columns=[14,15],
    container_image_id='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305')
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k]['best'] for k in ('baseline','shifted')},indent=2))
