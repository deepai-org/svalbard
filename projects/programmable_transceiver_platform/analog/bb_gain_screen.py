#!/usr/bin/env python3
"""DC and loaded AC characterization of an actual baseband differential cell."""
import hashlib,json,math,re,subprocess
from pathlib import Path
SRC=Path('/screen');OUT=Path('/work')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cases=[]
for bias in (.85,.95,1.05):
 for cap_pf in (1,5,20):
    name=f'b{bias:g}_c{cap_pf:g}'
    deck=f'''* Baseband cell, differential 1 V AC normalization (not large-signal stimulus)
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/bb_diff_gain.spice
.temp 27
VDD VDD 0 3.3
VB BIAS 0 {bias}
VIP IP 0 DC 1.177 AC 0.5
VIN IN 0 DC 1.177 AC 0.5 180
RP VDD OP 1k
RN VDD ON 1k
CP OP 0 {cap_pf}p
CN ON 0 {cap_pf}p
XDUT IP IN OP ON TAIL BIAS 0 pt_bb_diff_gain
.control
op
let outcm=(v(OP)+v(ON))/2
let taildc=v(TAIL)
let supply=-i(VDD)
print outcm taildc supply
ac dec 60 100k 1gig
let gain=mag(v(OP)-v(ON))
let phase=180/PI*cph(v(OP)-v(ON))
meas ac gain_1m find gain at=1meg
meas ac gain_10m find gain at=10meg
meas ac gain_30m find gain at=30meg
meas ac gain_100m find gain at=100meg
meas ac phase_10m find phase at=10meg
wrdata /work/{name}.dat gain phase
.endc
.end
'''
    path=OUT/f'{name}.spice';path.write_text(deck)
    log=OUT/f'{name}.log'
    with log.open('w') as handle:
        run=subprocess.run(['ngspice','-b',str(path)],stdout=handle,stderr=subprocess.STDOUT,timeout=90)
    assert run.returncode==0,(name,run.returncode)
    measures={}
    for key in ('outcm','taildc','supply','gain_1m','gain_10m','gain_30m','gain_100m','phase_10m'):
        found=re.findall(r'^'+key+r'\s*=\s*([-+\d.eE]+)',log.read_text(),re.M)
        assert found,(name,key)
        measures[key]=float(found[-1]);assert math.isfinite(measures[key])
    cases.append(dict(bias_v=bias,cap_per_leg_pf=cap_pf,measures=measures,deck_sha256=digest(path)))
    print(name,measures,flush=True)
result=dict(status='dc_ac_primitive_screen_not_filter_qualification',supply_v=3.3,temperature_c=27,process='typical',
    input_common_mode_v=1.177,load_resistor_per_leg_ohm=1000,cases=cases,
    source_sha256={str(p):digest(p) for p in (Path(__file__),SRC/'bb_diff_gain.spice')},
    image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
    limitations=['Ideal external gate bias and resistor/capacitor models.',
                 'Input common mode chosen from filtered receiver observation, not a tolerance bound.',
                 'AC=1 V differential is linearized normalization, not demonstrated input swing.',
                 'No CMFB, noise, mismatch, linearity, switched-load settling or physical implementation.',
                 'Cell output common mode and finite output impedance must be handled before cascading.',
                 'No higher-order filter or receiver integration claimed.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
