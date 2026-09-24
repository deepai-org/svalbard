#!/usr/bin/env python3
"""Direct sampler diagnostic; no complete ADC/baseband or sensitivity claim."""
import hashlib,json,math,subprocess
from pathlib import Path
from rf_measure import projection, interpolate, sampler_case
SRC=Path('/screen'); OUT=Path('/work')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
template=(SRC/'rx_branch_load_tb.spice.in').read_text()
cases=[]
for amplitude in (0,.001):
    name=f'a{amplitude:g}'
    deck=template.replace('@CORE@','/screen/rx_iq_buffered_core.spice').replace('@AMPLITUDE@',str(amplitude)).replace('@DATA@',f'/work/{name}.dat')
    deck=deck.replace('VDD VDD 0 3.3','VDD VDD 0 3.3\nVDDL VDDL 0 3.3')
    old='XDUT GATE MIX_RF SOURCE LOI LOIB LOQ LOQB IP IN QP QN 0 pt_rx_iq_core'
    assert deck.count(old)==1
    deck=deck.replace(old,'''RDQ VDD DRAIN_Q 300
RSOURCEQ SOURCE_Q 0 82
XDUT GATE MIX_RF SOURCE DRAIN_Q SOURCE_Q LOI LOIB LOQ LOQB IP IN QP QN VDDL 0 pt_rx_iq_buffered
.include /screen/iq_sampler.spice
VSC SC 0 PULSE(0 3.3 0 200p 200p 12.3n 25n)
VSCB SCB 0 PULSE(3.3 0 0 200p 200p 12.3n 25n)
XS IP IN QP QN HIP HIN HQP HQN SC SCB VDD 0 pt_iq_sampler''')
    deck=deck.replace('wrdata ', 'let ihold = v(HIP)-v(HIN)\nlet qhold = v(HQP)-v(HQN)\nwrdata ')
    deck=deck.replace('idiff qdiff v(MIX_RF) i(VDD)','idiff qdiff ihold qhold v(HIP) v(HIN) v(HQP) v(HQN) i(VDD) i(VDDL)')
    path=OUT/f'{name}.spice';path.write_text(deck)
    with (OUT/f'{name}.log').open('w') as log:
        run=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=900)
    assert run.returncode==0
    rows=[tuple(map(float,l.split())) for l in (OUT/f'{name}.dat').read_text().splitlines()[1:]]
    assert rows[0][0]<1e-12 and rows[-1][0]>300e-9
    assert all(len(r)==11 and all(map(math.isfinite,r)) for r in rows)
    samples=[[t,*[interpolate(rows,t,c) for c in (3,4)]] for t in [124e-9+k*25e-9 for k in range(8)]]
    ph=[[projection(rows,col,a,b,10e6) for col in (1,2)] for a,b in ((100e-9,200e-9),(200e-9,300e-9))]
    window=[r for r in rows if 200e-9<=r[0]<=300e-9]
    currents=[-sum((b[0]-a[0])*(a[col]+b[col])/2 for a,b in zip(window,window[1:]))/(window[-1][0]-window[0][0]) for col in (9,10)]
    cases.append(dict(**sampler_case(amplitude, samples, ph, window, currents), deck_sha256=digest(path)))
    print(name,currents,samples[-1],flush=True)
zero,signal=cases
signal_samples=[[a[0],a[1]-b[1],a[2]-b[2]] for a,b in zip(signal['samples'],zero['samples'])]
def sample_phasor(samples,col):
    return 2/len(samples)*sum(r[col]*complex(math.cos(-2*math.pi*10e6*r[0]),math.sin(-2*math.pi*10e6*r[0])) for r in samples)
held=[sample_phasor(signal_samples,c) for c in (1,2)]
base=[sample_phasor(zero['samples'],c) for c in (1,2)]
files=[Path(__file__),SRC/'rf_measure.py',SRC/'rx_branch_load_tb.spice.in',SRC/'iq_sampler.spice',SRC/'rx_iq_buffered_core.spice',SRC/'rx_iq_split_core.spice',SRC/'lo_buffer.spice',Path('/src/rf_lna/lna_cs_core.spice'),Path('/src/rf_switch_mixer/mixer.spice'),Path('/src/rf_if_transmission_gate/rf_if_transmission_gate.spice')]
result=dict(status='direct_sampling_diagnostic_not_adc_qualification',supply_v=3.3,temperature_c=27,process='typical',
            sample_rate_hz=40e6,hold_cap_per_leg_f=5e-12,cases=cases,baseline_subtracted_samples=signal_samples,
            held_tone_gain=[abs(z)/.001 for z in held],zero_input_sample_tone_peak_v=[abs(z) for z in base],
            ideal_differential_ktc_rms_v=math.sqrt(2*1.380649e-23*300.15/5e-12),
            image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
            source_sha256={str(p):digest(p) for p in files},
            limitations=['Only 8 settled samples, two tone periods; no sample-phase or frequency sweep.',
                         'External ideal coherent LO/reference and sampling clocks.',
                         '5pF ideal hold capacitors are a diagnostic assumption, not selected ADC sizing.',
                         'kT/C is an ideal calculation, not simulated receiver noise.',
                         'No baseband gain or anti-alias filter; original 1k/1pF mixer loads retained.',
                         'No ADC, mismatch, PEX, nonlinear/blocker or radio qualification.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print('held gains',result['held_tone_gain'],'kT/C',result['ideal_differential_ktc_rms_v'])
