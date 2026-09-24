#!/usr/bin/env python3
"""Nominal quadrature loading, sideband polarity and timestep experiment."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

OUT = Path('/work')
from rf_measure import projection

# Independent analytic amplitude/phase check, with DC and large LO leakage.
points = [(i*1e-12, .2+.001*math.cos(2*math.pi*10e6*i*1e-12+.3)
           +.3*math.sin(2*math.pi*2.4e9*i*1e-12)) for i in range(301001)]
expected = .001*complex(math.cos(.3), math.sin(.3))
assert abs(projection(points,1,200e-9,300e-9,10e6)-expected) < 1e-9
del points

cases = []
for name, amplitude, rf, step in (
    ('zero',0,2.41e9,2e-12), ('upper',.001,2.41e9,2e-12),
    ('lower',.001,2.39e9,2e-12), ('upper_fine',.001,2.41e9,1e-12)):
    period = 1/2.4e9
    sources = ''
    for label, phase in (('I',0),('IB',.5),('Q',.25),('QB',.75)):
        sources += f'V{label} {label}DRV 0 PULSE(0 3.3 {phase*period:.16g} 10p 10p {period/2-10e-12:.16g} {period:.16g})\n'
        sources += f'R{label} {label}DRV LO{label} 10\n'
    loads = ''.join(f'R{x} {x} 0 1k\nC{x} {x} 0 1p\n' for x in ('IP','IN','QP','QN'))
    deck = f"""* Shared-LNA I/Q low-frequency conversion experiment
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/rx_iq_core.spice
.temp 27
VDD VDD 0 3.3
VBIAS BIAS 0 1.5
RB GATE BIAS 1meg
VRF RF_SRC 0 SIN(0 {amplitude} {rf})
RSIG RF_SRC RF_PAD 50
CCIN RF_PAD GATE 20p
RD VDD MIX_RF 300
RSOURCE SOURCE 0 82
{sources}{loads}
XDUT GATE MIX_RF SOURCE LOI LOIB LOQ LOQB IP IN QP QN 0 pt_rx_iq_core
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran {step} 301n 0 {step}
let idiff = v(IP)-v(IN)
let qdiff = v(QP)-v(QN)
wrdata /work/{name}.dat idiff qdiff v(MIX_RF) i(VDD)
.endc
.end
"""
    path = OUT/f'{name}.spice'
    path.write_text(deck)
    with (OUT/f'{name}.log').open('w') as log:
        result = subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=600)
    assert result.returncode == 0, name
    points = [tuple(map(float,line.split())) for line in (OUT/f'{name}.dat').read_text().splitlines()[1:]]
    assert all(len(p)==5 and all(map(math.isfinite,p)) for p in points)
    assert points[0][0] < 1e-12 and points[-1][0] > 300e-9
    ph = [[projection(points,col,start,stop,10e6) for col in (1,2)]
          for start,stop in ((100e-9,200e-9),(200e-9,300e-9))]
    window=[p for p in points if 200e-9<=p[0]<=300e-9]
    current=-sum((b[0]-a[0])*(a[4]+b[4])/2 for a,b in zip(window,window[1:]))/(window[-1][0]-window[0][0])
    row=dict(name=name,rf_hz=rf,input_peak_v=amplitude,max_step_s=step,
             phasors_v=[[[v.real,v.imag] for v in pair] for pair in ph],
             drain_range_v=[min(p[3] for p in window),max(p[3] for p in window)],
             average_vdd_current_a=current,deck_sha256=hashlib.sha256(deck.encode()).hexdigest())
    cases.append(row)
    print(name, 'I/Q peaks',*[abs(z) for z in ph[-1]],flush=True)

baseline=[complex(*v) for v in cases[0]['phasors_v'][-1]]
for row in cases[1:]:
    i,q=[complex(*v)-b for v,b in zip(row['phasors_v'][-1],baseline)]
    row['gain_i_v_per_v']=abs(i)/row['input_peak_v']
    row['gain_q_v_per_v']=abs(q)/row['input_peak_v']
    row['q_relative_to_i_deg']=math.degrees(math.atan2((q/i).imag,(q/i).real))
    row['amplitude_imbalance_db']=20*math.log10(abs(q/i))
    row['window_change_relative']=max(abs(complex(*new)-complex(*old))/abs(complex(*new)-b)
        for new,old,b in zip(row['phasors_v'][-1],row['phasors_v'][-2],baseline))
    positive,negative=abs(i+1j*q),abs(i-1j*q)
    row['sideband_ratio_db']=20*math.log10(max(positive,negative)/min(positive,negative))
    row['dominant_combination']='I+jQ' if positive>negative else 'I-jQ'
coarse,fine=cases[1],cases[3]
step_error=max(abs(complex(*a)-complex(*b))/abs(complex(*b)-z)
               for a,b,z in zip(coarse['phasors_v'][-1],fine['phasors_v'][-1],baseline))
files=[Path(__file__),Path(__file__).with_name('rf_measure.py'),Path('/screen/rx_iq_core.spice'),Path('/src/rf_lna/lna_cs_core.spice'),Path('/src/rf_switch_mixer/mixer.spice')]
result=dict(status='simulation_completed_not_receiver_qualified',process='typical',supply_v=3.3,
            temperature_c=27,lo_hz=2.4e9,if_hz=10e6,cases=cases,
            timestep_phasor_relative_change=step_error,
            image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
            limitations=['external ideal LO and bias','external ideal 1k/1pF output loads',
                         'no transistor mismatch or PEX','no physical LO driver power',
                         'single-ended RF experimental core, not final differential interface',
                         'no noise/model qualification or ADC/filter proof',
                         'fine timestep uses coarse zero-input baseline'],
            source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
