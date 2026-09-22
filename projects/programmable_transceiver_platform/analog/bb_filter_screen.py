#!/usr/bin/env python3
"""Actual two-stage closed-loop filter: loaded AC and nominal transient step."""
import hashlib,json,math,re,subprocess
from pathlib import Path
SRC=Path('/screen');OUT=Path('/work')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,deck):
    path=OUT/f'{name}.spice';path.write_text(deck)
    log=OUT/f'{name}.log'
    with log.open('w') as f:
        result=subprocess.run(['ngspice','-b',str(path)],stdout=f,stderr=subprocess.STDOUT,timeout=90)
    assert result.returncode==0,name
    return path,log

def base(rfb,cap,stim):
    return f'''* Finite-gain transistor filter section
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/bb_filter_section.spice
.temp 27
VDD VDD 0 3.3
VB BIAS 0 2.25
{stim}
XDUT IP IN OP ON BIAS VDD 0 pt_bb_filter RFB={rfb} C={cap}p
'''
cases=[]
for rfb in (10000,20000,50000):
 for cap in (15,20,25):
    name=f'r{rfb}_c{cap}'
    deck=base(rfb,cap,'VIP IP 0 DC 1.177 AC 0.5\nVIN IN 0 DC 1.177 AC 0.5 180')+f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
op
let outcm=(v(OP)+v(ON))/2
let supply=-i(VDD)
print outcm supply
ac dec 100 100k 1gig
let gain=mag(v(OP)-v(ON))
let phase=180/PI*cph(v(OP)-v(ON))
meas ac gain_1m find gain at=1meg
meas ac gain_10m find gain at=10meg
meas ac gain_30m find gain at=30meg
wrdata /work/{name}.dat gain phase
.endc
.end
'''
    path,log=run(name,deck)
    measures={}
    for key in ('outcm','supply','gain_1m','gain_10m','gain_30m'):
        values=re.findall(r'^'+key+r'\s*=\s*([-+\d.eE]+)',log.read_text(),re.M)
        assert values,(name,key)
        measures[key]=float(values[-1]);assert math.isfinite(measures[key])
    rows=[list(map(float,l.split())) for l in (OUT/f'{name}.dat').read_text().splitlines()[1:]]
    peak=max(rows,key=lambda r:r[1])
    cases.append(dict(rfb_ohm=rfb,cap_per_node_pf=cap,measures=measures,
        gain_peak_v_per_v=peak[1],gain_peak_hz=peak[0],
        edge_change_from_1mhz_db=20*math.log10(measures['gain_10m']/measures['gain_1m']),
        relative_10_to_30_rejection_db=20*math.log10(measures['gain_10m']/measures['gain_30m']),deck_sha256=digest(path)))
    print(name,cases[-1],flush=True)
# Middle design point: 1 mV differential pulse, finite 1 ns input edges.
deck=base(20000,20,'VIP IP 0 PULSE(1.177 1.1775 100n 1n 1n 499n 2u)\nVIN IN 0 PULSE(1.177 1.1765 100n 1n 1n 499n 2u)')+'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 100p 1001n 0 100p
let differential=v(OP)-v(ON)
let common=(v(OP)+v(ON))/2
wrdata /work/step.dat differential common i(VDD)
.endc
.end
'''
path,log=run('step',deck)
rows=[list(map(float,l.split())) for l in (OUT/'step.dat').read_text().splitlines()[1:]]
assert rows[-1][0]>1000e-9 and all(all(map(math.isfinite,r)) for r in rows)
plateau=[r[1] for r in rows if 400e-9<r[0]<550e-9]
final=sum(plateau)/len(plateau)
peak=max(r[1] for r in rows if 100e-9<r[0]<600e-9)
late=[r[1] for r in rows if 900e-9<r[0]<1000e-9]
step=dict(rfb_ohm=20000,cap_per_node_pf=20,input_differential_step_v=.001,output_plateau_v=final,
          overshoot_relative=peak/final-1,plateau_peak_to_peak_v=max(plateau)-min(plateau),
          after_return_max_abs_v=max(map(abs,late)),deck_sha256=digest(path))
result=dict(status='nominal_filter_section_screen_not_stability_or_receiver_signoff',cases=cases,step=step,
    supply_v=3.3,temperature_c=27,process='typical',bias_v=2.25,input_cm_v=1.177,
    image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
    source_sha256={str(p):digest(p) for p in (Path(__file__),SRC/'bb_filter_section.spice',SRC/'bb_pmos_gain.spice')},
    limitations=['Ideal passives and bias; no switching banks or tuner implemented.',
                 'No additional sampler/receiver load; included capacitors are section elements.',
                 'Step response at one point is not loop-margin or all-corner stability proof.',
                 'No noise, mismatch, extracted layout, large-signal blocker or full-band qualification.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print('step',step)
