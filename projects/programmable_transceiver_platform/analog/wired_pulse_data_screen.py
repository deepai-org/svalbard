#!/usr/bin/env python3
"""Actual pulse/bridge/RX capture under static and changing ideal pin data."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import numpy as np

SRC = Path('/src')
OUT = Path('/work')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = {
    'pulse': (OUT/'pex/clock_pulse_generator.pex.spice', OUT/'pulse-physical.json'),
    'bridge': (SRC/'capture_clock_bridge/capture_clock_bridge.pex.spice', SRC/'capture_clock_bridge/physical_result.json'),
    'lane': (SRC/'lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice', SRC/'lane_rx_regenerative_capture/physical_result.json')}
for name, (pex, physical) in inputs.items():
    record = json.loads(physical.read_text())
    assert record['result'] == 'pass' and record['pex_sha256'] == sha(pex), name
base = SRC/'pulse_bridge_lane/pulse_bridge_lane_tb.spice.in'
template = base.read_text()
# ngspice meas assigns its result into the named vector: never overwrite
# the waveform subsequently exported by wrdata.
template = template.replace('meas tran e_q_diff find', 'meas tran e_q_scalar find')
template = template.replace('meas tran o_q_diff find', 'meas tran o_q_scalar find')
values = dict(MOS_CORNER='typical', RES_CORNER='res_typical', VDD_V='3.3',
              TEMP_C='27', VMID='1.65', RXP_V='1.75', RXN_V='1.55', RX_BIAS_V='1.3',
              **{f'{k.upper()}_PEX': str(v[0]) for k,v in inputs.items()})
for k,v in values.items():
    template = template.replace('@'+k+'@',v)
assert not re.search(r'@[A-Z0-9_]+@', template)
# Fixed reproducible nonperiodic prefix; no search over the pattern.
bits = [1,0,1,1,0,0,1,0,1,1,1,0,0,1,0,1,0,0,1,1,0,1,1,0,1,0,0,0,1,1,0,1,1,0,1,0,0,1,1,1]

def stimulus(sign):
    points = [(0,0),(.5e-9,1.65+sign*.1*(2*bits[0]-1))]
    for i in range(1,len(bits)):
        t=1e-9+i*400e-12
        points += [(t-10e-12,1.65+sign*.1*(2*bits[i-1]-1)),
                   (t+10e-12,1.65+sign*.1*(2*bits[i]-1))]
    return 'PWL('+ ' '.join(f'{t:.12g} {v:.8g}' for t,v in points)+')'

cases=[]
for name in ('static_positive','static_negative','changing'):
    deck=template.replace('tran 2p 8n uic','tran 2p 17n uic')
    if name == 'static_negative':
        deck=deck.replace('500p 1.75','500p 1.55').replace('VRXN RXN_SRC 0 PWL(0 0 500p 1.55)','VRXN RXN_SRC 0 PWL(0 0 500p 1.75)')
    if name == 'changing':
        deck=re.sub(r'^VRXP .*$', 'VRXP RXP_SRC 0 '+stimulus(1),deck,flags=re.M)
        deck=re.sub(r'^VRXN .*$', 'VRXN RXN_SRC 0 '+stimulus(-1),deck,flags=re.M)
    wave=OUT/f'{name}.dat'
    deck=deck.replace('quit',f'''set wr_singlescale
set wr_vecnames
wrdata {wave} v(RXP) v(RXN) v(E_SENSE_CLK) v(O_SENSE_CLK) v(E_CAPTURE_CLK) v(O_CAPTURE_CLK) e_q_diff o_q_diff v(FE_E_P) v(FE_E_N) v(FE_O_P) v(FE_O_N) isupply
quit''')
    path=OUT/f'{name}.spice'; path.write_text(deck)
    with (OUT/f'{name}.log').open('w') as log:
        subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
    data=np.loadtxt(wave,skiprows=1); t=data[:,0]
    assert t[-1]>=17e-9*.999 and np.isfinite(data).all()
    branches={}
    for branch,col,qcol in [('even',5,7),('odd',6,8)]:
        clock=data[:,col]
        idx=np.where((clock[:-1]>=1.65)&(clock[1:]<1.65))[0]
        falls=[float(t[i]+(1.65-clock[i])*(t[i+1]-t[i])/(clock[i+1]-clock[i])) for i in idx]
        times=[f+100e-12 for f in falls if 6e-9<f<16e-9]
        samples=[float(np.interp(s,t,data[:,qcol])) for s in times]
        branches[branch]=dict(sample_times_s=times, differential_output_v=samples,
            minimum_absolute_output_v=min(map(abs,samples)) if samples else None,
            note='Samples 100 ps after each actual capture falling edge; latency not calibrated.')
    row=dict(id=name,deck_sha256=sha(path),waveform_sha256=sha(wave),branches=branches,
             current_a=float(np.trapezoid(data[t>=6e-9,13],t[t>=6e-9])/(t[-1]-t[t>=6e-9][0])))
    cases.append(row)
    print(json.dumps(row),flush=True)
result=dict(status='diagnostic_not_lane_qualification',pulse_physical_qualified=True,environment=['typical','res_typical',3.3,27],
    stimulus_bits=bits,bit_period_s=400e-12,first_bit_end_s=1.4e-9,
    ideal_boundaries=['upstream 1.25 GHz complementary rail clocks','200 mV differential ideal RX pin drive through 1 ohm per leg','DC biases and supplies'],
    limitations=['No channel or TX','Unrouted inter-macro wires','No CDR','Output polarity/latency and aperture require assessment; no BER claim'],
    source_sha256={'runner':sha(Path(__file__)),'template':sha(base),**{k:sha(v[0]) for k,v in inputs.items()}},cases=cases)
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
