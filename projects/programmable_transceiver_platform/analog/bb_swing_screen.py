#!/usr/bin/env python3
"""Loaded differential-cell common-mode/amplitude transient diagnostic."""
import hashlib,json,math,subprocess
from pathlib import Path
from rf_measure import projection
SRC=Path('/screen'); OUT=Path('/work')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cases=[]
for cm in (.9,1.177,1.624,2.0):
 for amplitude in (.001,.02,.1):
    name=f'cm{cm:g}_a{amplitude:g}'
    deck=f'''* Real differential swing, fixed external tail gate bias
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/bb_diff_gain.spice
.temp 27
VDD VDD 0 3.3
VB BIAS 0 1.05
VIP IP 0 SIN({cm} {amplitude/2} 10meg)
VIN IN 0 SIN({cm} {-amplitude/2} 10meg)
RP VDD OP 1k
RN VDD ON 1k
CP OP 0 5p
CN ON 0 5p
XDUT IP IN OP ON TAIL BIAS 0 pt_bb_diff_gain
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 100p 601n 0 100p
let differential=v(OP)-v(ON)
let common=(v(OP)+v(ON))/2
wrdata /work/{name}.dat differential common v(OP) v(ON) v(TAIL) i(VDD)
.endc
.end
'''
    path=OUT/f'{name}.spice';path.write_text(deck)
    with (OUT/f'{name}.log').open('w') as log:
        run=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=90)
    assert run.returncode==0,name
    rows=[tuple(map(float,l.split())) for l in (OUT/f'{name}.dat').read_text().splitlines()[1:]]
    assert all(len(row)==7 and all(map(math.isfinite,row)) for row in rows)
    assert rows[0][0]<1e-12 and rows[-1][0]>600e-9
    tones=[projection(rows,1,400e-9,600e-9,k*10e6) for k in range(1,6)]
    previous=projection(rows,1,200e-9,400e-9,10e6)
    window=[r for r in rows if 400e-9<=r[0]<=600e-9]
    def mean(col):return sum((b[0]-a[0])*(a[col]+b[col])/2 for a,b in zip(window,window[1:]))/(window[-1][0]-window[0][0])
    cases.append(dict(input_cm_v=cm,input_differential_peak_v=amplitude,gain_v_per_v=abs(tones[0])/amplitude,
        output_cm_mean_v=mean(2),output_cm_range_v=[min(r[2] for r in window),max(r[2] for r in window)],
        output_leg_range_v=[min(r[c] for r in window for c in (3,4)),max(r[c] for r in window for c in (3,4))],
        tail_range_v=[min(r[5] for r in window),max(r[5] for r in window)],supply_current_a=-mean(6),
        harmonics_peak_v=[abs(z) for z in tones],h2_to_h5_ratio=math.sqrt(sum(abs(z)**2 for z in tones[1:]))/abs(tones[0]),
        fundamental_window_change_relative=abs(tones[0]-previous)/abs(tones[0]),deck_sha256=digest(path)))
    print(name,cases[-1]['gain_v_per_v'],cases[-1]['output_cm_mean_v'],cases[-1]['h2_to_h5_ratio'],flush=True)
for row in cases:
    reference=next(c for c in cases if c['input_cm_v']==row['input_cm_v'] and c['input_differential_peak_v']==.001)
    row['gain_change_from_1mv_db']=20*math.log10(row['gain_v_per_v']/reference['gain_v_per_v'])
result=dict(status='common_mode_swing_diagnostic_not_filter_qualification',supply_v=3.3,temperature_c=27,process='typical',
    external_tail_bias_v=1.05,output_cap_per_leg_f=5e-12,load_per_leg_ohm=1000,cases=cases,
    source_sha256={str(p):digest(p) for p in (Path(__file__),SRC/'rf_measure.py',SRC/'bb_diff_gain.spice')},
    image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
    limitations=['One nominal transistor cell, not cascaded filter or actual receiver loading.',
                 'Ideal external bias, source and load passives; no CMFB or regulated current reference.',
                 'Only harmonics 2 through 5, finite timestep/windows; not noise or complete distortion qualification.',
                 'No process/mismatch, switched-load settling, extracted layout or blocker testing.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
