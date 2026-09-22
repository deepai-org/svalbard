#!/usr/bin/env python3
"""Isolate shared-drain mixer loading with matched transient experiments."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
from rf_measure import projection

OUT=Path('/work')
SRC=Path('/screen')
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# Reference test exercises actual integration routine used below.
points=[(i*1e-12,.2+.001*math.cos(2*math.pi*10e6*i*1e-12+.3)
         +.3*math.sin(2*math.pi*2.4e9*i*1e-12)) for i in range(301001)]
expected=.001*complex(math.cos(.3),math.sin(.3))
measurement_error=abs(projection(points,1,200e-9,300e-9,10e6)-expected)/abs(expected)
assert measurement_error<1e-6

template=(SRC/'rx_branch_load_tb.spice.in').read_text()
core=(SRC/'rx_iq_core.spice').read_text()
q_instance='XQMIX MIX_RF LOQ LOQB QP QN VSS wifi_rf_switch_mixer\n'
assert core.count(q_instance)==1
single=core.replace(q_instance,'* Q mixer omitted for matched load control.\n')
(OUT/'single.spice').write_text(single)
cases=[]
for branches,corepath in ((1,OUT/'single.spice'),(2,SRC/'rx_iq_core.spice')):
    for amplitude in (0,.001):
        name=f'b{branches}_{amplitude:g}'
        data=OUT/f'{name}.dat'
        deck=template.replace('@CORE@',str(corepath)).replace('@AMPLITUDE@',str(amplitude)).replace('@DATA@',str(data))
        assert '@' not in deck
        path=OUT/f'{name}.spice'
        path.write_text(deck)
        with (OUT/f'{name}.log').open('w') as log:
            run=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=600)
        assert run.returncode==0,name
        points=[tuple(map(float,line.split())) for line in data.read_text().splitlines()[1:]]
        assert all(len(p)==5 and all(map(math.isfinite,p)) for p in points)
        assert points[0][0]<1e-12 and points[-1][0]>300e-9
        ph=[projection(points,1,a,b,10e6) for a,b in ((100e-9,200e-9),(200e-9,300e-9))]
        window=[p for p in points if 200e-9<=p[0]<=300e-9]
        current=-sum((b[0]-a[0])*(a[4]+b[4])/2 for a,b in zip(window,window[1:]))/(window[-1][0]-window[0][0])
        cases.append(dict(branches=branches,input_peak_v=amplitude,phasors_v=[[z.real,z.imag] for z in ph],
                          drain_range_v=[min(p[3] for p in window),max(p[3] for p in window)],
                          average_vdd_current_a=current,deck_sha256=digest(path),core_sha256=digest(corepath)))
        print(name,abs(ph[-1]),current,flush=True)
summaries=[]
for branches in (1,2):
    zero,signal=[r for r in cases if r['branches']==branches]
    baseline=complex(*zero['phasors_v'][-1])
    value=complex(*signal['phasors_v'][-1])-baseline
    summaries.append(dict(branches=branches,baseline_if_peak_v=abs(baseline),
                          gain_i_v_per_v=abs(value)/.001,
                          window_change_relative=abs(complex(*signal['phasors_v'][0])-complex(*signal['phasors_v'][1]))/abs(value)))
ratio=summaries[1]['gain_i_v_per_v']/summaries[0]['gain_i_v_per_v']
files=[Path(__file__),SRC/'rf_measure.py',SRC/'rx_branch_load_tb.spice.in',SRC/'rx_iq_core.spice',
       Path('/src/rf_lna/lna_cs_core.spice'),Path('/src/rf_switch_mixer/mixer.spice')]
result=dict(status='simulation_completed_not_receiver_qualified',process='typical',temperature_c=27,supply_v=3.3,
            rf_hz=2.41e9,lo_hz=2.4e9,if_hz=10e6,max_step_s=2e-12,
            changed_element='Only Q mixer instance removed; Q external loads and LO sources retained.',
            cases=cases,summaries=summaries,two_to_one_gain_ratio=ratio,two_to_one_gain_change_db=20*math.log10(ratio),
            analytic_projection_relative_error=measurement_error,
            image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
            source_sha256={str(p):digest(p) for p in files},
            limitations=['Schematic compact-model experiment with ideal external bias, passives and LO.',
                         'No mismatch, PEX, noise qualification, RF differential front end or ADC.',
                         'VDD current excludes external LO and bias power.',
                         'Magnitude change includes bias and periodic loading; not a capacitance-only effect.',
                         'No receiver acceptance threshold or tapeout claim.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(summaries,indent=2))
print('two/one gain dB',result['two_to_one_gain_change_db'])
