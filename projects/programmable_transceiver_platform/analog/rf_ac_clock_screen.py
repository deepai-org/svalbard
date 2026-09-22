#!/usr/bin/env python3
"""Autonomous AC-coupled LO boundary and supply-pushing experiment."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work')
rows=[]
for supply in (3.3,3.29,3.31):
 name=f'v{supply:g}'
 deck=f'''* Schematic seeded clock, real mixer load; no stochastic noise
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical
.include /vco/ring_vco.spice
.include /screen/lo_buffer.spice
.include /wifi/rf_lna/lna_cs_core.spice
.include /wifi/rf_switch_mixer/mixer.spice
.temp 27
VDD VDD 0 {supply}
VRFS VDDRF 0 3.3
VCTRL CTRL 0 1.08
XVCO CTRL VDD 0 CP CN ring_vco LOAD_L=5.25u CAP_W=4u CAP_L=3u
CLOADP CP 0 25f
CLOADN CN 0 25f
* AC coupling plus inverter feedback establishes its own switching bias.
CCP CP BP 200f
CCN CN BN 200f
RFBP BP XBP.MID 100k
RFBN BN XBN.MID 100k
XBP BP LO VDDRF 0 pt_lo_buffer S=1
XBN BN LOB VDDRF 0 pt_lo_buffer S=1
VB BIAS 0 1.5
RB GATE BIAS 1meg
VRF RF_SRC 0 SIN(0 0.001 2.51g)
RS RF_SRC RF_PAD 50
CC RF_PAD GATE 20p
RD VDDRF DRAIN 300
RTAIL SOURCE 0 82
RIP IP 0 1k
RIN INN 0 1k
CIP IP 0 1p
CIN INN 0 1p
XLNA GATE DRAIN SOURCE 0 wifi_lna_cs_core
XMIX DRAIN LO LOB IP INN 0 wifi_rf_switch_mixer
.ic v(XVCO.N0P)=1.718 v(XVCO.N0N)=1.714
.ic v(XVCO.N1P)=1.714 v(XVCO.N1N)=1.718
.ic v(XVCO.N2P)=1.718 v(XVCO.N2N)=1.714
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 2p 81n 0 2p uic
let diff=v(CP)-v(CN)
let bb=v(IP)-v(INN)
wrdata /work/{name}.dat diff v(LO) v(LOB) bb i(VDD) i(VRFS) v(BP) v(BN)
.endc
.end
'''
 p=O/(name+'.spice');p.write_text(deck)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
 a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and a[-1,0]>80e-9
 a=a[a[:,0]>=40e-9];t=a[:,0]
 def edges(c,level):
  ix=np.where((a[:-1,c]<level)&(a[1:,c]>=level))[0]
  return t[ix]+(t[ix+1]-t[ix])*(level-a[ix,c])/(a[ix+1,c]-a[ix,c])
 e=edges(1,0);f=(len(e)-1)/(e[-1]-e[0]);lo=edges(2,1.65);lob=edges(3,1.65)
 beat=abs(2.51e9-f)
 # Deterministic tone fit, not noise or ENOB; short window includes nuisance DC/trend.
 x=np.column_stack([np.ones(len(t)),t-t.mean(),np.sin(2*np.pi*beat*t),np.cos(2*np.pi*beat*t)])
 coef=np.linalg.lstsq(x,a[:,4],rcond=None)[0]
 row=dict(vco_supply_v=supply,frequency_hz=f,lo_crossings=len(lo),lob_crossings=len(lob),lo_range_v=[float(a[:,2].min()),float(a[:,2].max())],lob_range_v=[float(a[:,3].min()),float(a[:,3].max())],vco_current_a=float(-np.trapezoid(a[:,5],t)/(t[-1]-t[0])),rf_current_a=float(-np.trapezoid(a[:,6],t)/(t[-1]-t[0])),beat_hz=beat,beat_fit_amplitude_v=float(np.hypot(coef[2],coef[3])),beat_cycles_observed=float(beat*(t[-1]-t[0])),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')})
 rows.append(row);print(json.dumps(row),flush=True)
r=dict(status='seeded_schematic_ac_coupled_clock_and_single_mixer_screen',cases=rows,supply_pushing_hz_per_v=(rows[2]['frequency_hz']-rows[1]['frequency_hz'])/.02,limitations=['No PLL, quadrature, stochastic phase noise, unassisted startup, PEX or package.', 'Only VCO supply perturbed, ideal control and RF supply.', 'Single LNA/mixer and RC load; no converter or complete radio.', 'Short deterministic beat fit is not SNR, noise figure, EVM or target-band qualification.'],runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
