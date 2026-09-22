#!/usr/bin/env python3
"""Existing free-running CML VCO versus actual CMOS-buffer/mixer load."""
import hashlib,json,math,subprocess
from pathlib import Path
OUT=Path('/work');SRC=Path('/screen')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rising(rows,col,level=0):
 return [a[0]+(b[0]-a[0])*(level-a[col])/(b[col]-a[col]) for a,b in zip(rows,rows[1:]) if a[col]<level<=b[col]]
def frequency(rows,col,level=0):
 edges=rising(rows,col,level)
 return (len(edges)-1)/(edges[-1]-edges[0]) if len(edges)>3 else None
cases=[]
for loaded in (False,True):
 for control in (.88,1.08,1.30):
    name=f'{"loaded" if loaded else "reference"}_{control:g}'
    connection='''XBP CP LO VDDRF 0 pt_lo_buffer S=1
XBN CN LOB VDDRF 0 pt_lo_buffer S=1
VB BIAS 0 1.5
RB GATE BIAS 1meg
VRF RF_SRC 0 0
RS RF_SRC RF_PAD 50
CC RF_PAD GATE 20p
RD VDDRF DRAIN 300
RTAIL SOURCE 0 82
RIP IP 0 1k
RIN INN 0 1k
CIP IP 0 1p
CIN INN 0 1p
XLNA GATE DRAIN SOURCE 0 wifi_lna_cs_core
XMIX DRAIN LO LOB IP INN 0 wifi_rf_switch_mixer''' if loaded else 'RLO LO 0 1k\nRLOB LOB 0 1k'
    deck=f'''* Seeded CML VCO clock-boundary screen, not PLL or quadrature
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.include /vco/ring_vco.spice
.include /screen/lo_buffer.spice
.include /wifi/rf_lna/lna_cs_core.spice
.include /wifi/rf_switch_mixer/mixer.spice
.temp 27
VDD VDD 0 3.3
VRFS VDDRF 0 3.3
VCTRL CTRL 0 {control}
XVCO CTRL VDD 0 CP CN ring_vco LOAD_L=5.25u CAP_W=4u CAP_L=3u
CLOADP CP 0 25f
CLOADN CN 0 25f
{connection}
.ic v(XVCO.N0P)=1.718 v(XVCO.N0N)=1.714
.ic v(XVCO.N1P)=1.714 v(XVCO.N1N)=1.718
.ic v(XVCO.N2P)=1.718 v(XVCO.N2N)=1.714
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 2p 41n 0 2p uic
let diff=v(CP)-v(CN)
wrdata /work/{name}.dat diff v(CP) v(CN) v(LO) v(LOB) i(VDD) i(VRFS)
.endc
.end
'''
    path=OUT/f'{name}.spice';path.write_text(deck)
    with (OUT/f'{name}.log').open('w') as log:
        run=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=240)
    assert run.returncode==0,name
    rows=[tuple(map(float,l.split())) for l in (OUT/f'{name}.dat').read_text().splitlines()[1:]]
    assert all(len(r)==8 and all(map(math.isfinite,r)) for r in rows) and rows[-1][0]>40e-9
    early=[r for r in rows if 10e-9<=r[0]<=20e-9]
    late=[r for r in rows if 30e-9<=r[0]<=40e-9]
    def mean(c):return sum((b[0]-a[0])*(a[c]+b[c])/2 for a,b in zip(late,late[1:]))/(late[-1][0]-late[0][0])
    row=dict(loaded=loaded,control_v=control,early_frequency_hz=frequency(early,1),late_frequency_hz=frequency(late,1),
        cml_leg_range_v=[min(r[c] for r in late for c in (2,3)),max(r[c] for r in late for c in (2,3))],
        differential_range_v=[min(r[1] for r in late),max(r[1] for r in late)],
        lo_ranges_v=[[min(r[c] for r in late),max(r[c] for r in late)] for c in (4,5)],
        lo_frequency_hz=[frequency(late,c,1.65) for c in (4,5)],vco_current_a=-mean(6),rf_branch_current_a=-mean(7),deck_sha256=digest(path))
    cases.append(row);print(row,flush=True)
files=[Path(__file__),SRC/'lo_buffer.spice',Path('/vco/ring_vco.spice'),Path('/wifi/rf_lna/lna_cs_core.spice'),Path('/wifi/rf_switch_mixer/mixer.spice')]
result=dict(status='seeded_free_running_clock_boundary_screen_not_rf_clock_qualification',cases=cases,
    source_sha256={str(p):digest(p) for p in files},supply_v=3.3,temperature_c=27,process='typical',resistor_corner='res_typical',
    image='sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
    limitations=['Existing schematic ring reused; no extracted parasitics in this run.',
                 'Explicit initial-condition seed, ideal supplies/control: not unassisted startup.',
                 'One complementary pair, not quadrature. No PLL/frequency lock, phase noise or tuning coverage proof.',
                 'RF branch is zero-input one-mixer load, not full receiver.',
                 'Unloaded reference retains 25fF per output; loaded case adds real buffer gates.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
