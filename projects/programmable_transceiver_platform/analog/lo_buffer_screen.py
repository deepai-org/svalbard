#!/usr/bin/env python3
"""Short actual-mixer-load transient screen; ideal sources only before buffers."""
import hashlib,json,math,subprocess
from pathlib import Path
SRC=Path('/screen'); OUT=Path('/work')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def crossings(rows,col,level,rising):
    result=[]
    for a,b in zip(rows,rows[1:]):
        if (a[col]<level<=b[col]) if rising else (a[col]>level>=b[col]):
            result.append(a[0]+(b[0]-a[0])*(level-a[col])/(b[col]-a[col]))
    return result

def mean(rows,col):
    return sum((b[0]-a[0])*(a[col]+b[col])/2 for a,b in zip(rows,rows[1:]))/(rows[-1][0]-rows[0][0])

cases=[]
for scale in (.5,1,2):
    name=f's{scale:g}'
    p=1/2.4e9
    deck=f'''* LO buffer driving actual transistor mixer and LNA, nominal only
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /src/rf_rx_external_lo_parent/rf_rx_external_lo_parent.spice
.include /screen/lo_buffer.spice
.temp 27
VDD VDD 0 3.3
VDDL VDDL 0 3.3
VBIAS BIAS 0 1.5
RB GATE BIAS 1meg
VRF RF_SRC 0 0
RSIG RF_SRC RF_PAD 50
CCIN RF_PAD GATE 20p
RD VDD DRAIN 300
RSOURCE SOURCE 0 82
VI IN 0 PULSE(0 3.3 0 10p 10p {p/2-10e-12:.16g} {p:.16g})
VIB INB 0 PULSE(0 3.3 {p/2:.16g} 10p 10p {p/2-10e-12:.16g} {p:.16g})
XLO IN LO VDDL 0 pt_lo_buffer S={scale}
XLOB INB LOB VDDL 0 pt_lo_buffer S={scale}
RIP IP 0 1k
RIN INN 0 1k
CIP IP 0 1p
CIN INN 0 1p
XDUT GATE DRAIN SOURCE LO LOB IP INN 0 wifi_rx_external_lo_parent
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 1p 41n 0 1p
wrdata /work/{name}.dat v(IN) v(LO) v(LOB) i(VDDL) i(VDD)
.endc
.end
'''
    path=OUT/f'{name}.spice';path.write_text(deck)
    with (OUT/f'{name}.log').open('w') as log:
        run=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
    assert run.returncode==0
    rows=[tuple(map(float,l.split())) for l in (OUT/f'{name}.dat').read_text().splitlines()[1:]]
    assert rows[0][0]<1e-12 and rows[-1][0]>40e-9
    assert all(len(r)==6 and all(map(math.isfinite,r)) for r in rows)
    rows=[r for r in rows if 20e-9<=r[0]<=40e-9]
    metrics=[]
    for col in (2,3):
        timing={}
        for rising,label in ((True,'rise'),(False,'fall')):
            first=crossings(rows,col,.33 if rising else 2.97,rising)
            last=crossings(rows,col,2.97 if rising else .33,rising)
            durations=[next((t-a for t in last if t>a),math.nan) for a in first]
            durations=[t for t in durations if math.isfinite(t) and t<p]
            timing[label+'_10_90_ps_max']=max(durations)*1e12 if durations else None
            timing[label+'_full_swing_edges']=len(durations)
        rising=crossings(rows,col,1.65,True);falling=crossings(rows,col,1.65,False)
        high=[next((f-t for f in falling if f>t),math.nan) for t in rising]
        high=[t for t in high if math.isfinite(t) and t<p]
        timing.update(min_v=min(r[col] for r in rows),max_v=max(r[col] for r in rows),
                      rising_edges=len(rising),falling_edges=len(falling),
                      mean_high_fraction=sum(high)/len(high)/p if high else None)
        metrics.append(timing)
    input_edges=crossings(rows,1,1.65,True);output_edges=crossings(rows,2,1.65,True)
    delays=[next((b-a for b in output_edges if b>a),math.nan) for a in input_edges]
    delays=[t for t in delays if math.isfinite(t) and t<p]
    cases.append(dict(scale=scale,lo=metrics[0],lob=metrics[1],
                      mean_rising_delay_ps=sum(delays)/len(delays)*1e12 if delays else None,
                      driver_pair_current_a=-mean(rows,4),lna_mixer_current_a=-mean(rows,5),deck_sha256=digest(path)))
    print(cases[-1],flush=True)
files=[Path(__file__),SRC/'lo_buffer.spice',Path('/src/rf_rx_external_lo_parent/rf_rx_external_lo_parent.spice'),
       Path('/src/rf_lna/lna_cs_core.spice'),Path('/src/rf_switch_mixer/mixer.spice')]
result=dict(status='simulation_completed_not_clock_qualified',frequency_hz=2.4e9,supply_v=3.3,temperature_c=27,process='typical',
    cases=cases,image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
    source_sha256={str(p):digest(p) for p in files},
    limitations=['Ideal clocks at first-stage inputs; no oscillator or phase generator.',
                 'Actual mixer gate load at zero RF input with existing biased LNA and external IF passives.',
                 'No route/package parasitics, mismatch, PVT closure or phase-noise qualification.',
                 'Input driver power excluded; two buffer chains measured, four needed for I/Q.',
                 'No receiver conversion or output duty acceptance threshold in this short screen.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
