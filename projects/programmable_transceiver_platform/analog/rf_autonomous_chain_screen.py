#!/usr/bin/env python3
"""Paired tone/zero test through oscillator, mixer, filter and sampling switch."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');base=(Path('/clock')/'v3.3.spice').read_text()
f=json.loads((Path('/clock')/'result.json').read_text())['cases'][0]['frequency_hz']
rows=[]; waves=[]
for amplitude in (0,.001):
 name=f'a{amplitude:g}'
 d=base.replace('SIN(0 0.001 2.51g)',f'SIN(0 {amplitude} {f+10e6})')
 d=d.replace('.control', '''.include /screen/bb_filter_section.spice
.include /wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice
VBB BB 0 2.25
XF IP INN FP FN BB VDDRF 0 pt_bb_filter RFB=20k C=20p
VSC SC 0 PULSE(0 3.3 0 200p 200p 12.3n 25n)
VSCB SCB 0 PULSE(3.3 0 0 200p 200p 12.3n 25n)
XS FP FN HP HN SC SCB VDDRF 0 wifi_if_transmission_gate
CHP HP 0 5p
CHN HN 0 5p
.control''')
 d=d.replace('tran 2p 81n 0 2p uic','tran 2p 301n 0 2p uic')
 start=d.index('wrdata ');end=d.index('\n',start)
 d=d[:start]+f'let filt=v(FP)-v(FN)\nlet held=v(HP)-v(HN)\nwrdata /work/{name}.dat diff bb filt held v(HP) v(HN) i(VDD) i(VRFS)'+d[end:]
 p=O/(name+'.spice');p.write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
 a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert a.shape[1]==9 and np.isfinite(a).all() and a[-1,0]>300e-9
 ts=np.arange(124e-9,301e-9,25e-9);samples=np.interp(ts,a[:,0],a[:,4]);waves.append(samples)
 w=a[a[:,0]>=100e-9];t=w[:,0]
 row=dict(amplitude_v=amplitude,sample_times_s=ts.tolist(),held_samples_v=samples.tolist(),hold_range_v=[float(w[:,5:7].min()),float(w[:,5:7].max())],vco_current_a=float(-np.trapezoid(w[:,7],t)/(t[-1]-t[0])),rf_filter_current_a=float(-np.trapezoid(w[:,8],t)/(t[-1]-t[0])),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')})
 rows.append(row);print(json.dumps(row),flush=True)
y=waves[1]-waves[0];ts=np.array(rows[0]['sample_times_s'])
x=np.column_stack([np.ones(len(ts)),np.sin(2*np.pi*10e6*ts),np.cos(2*np.pi*10e6*ts)])
c=np.linalg.lstsq(x,y,rcond=None)[0]
r=dict(status='single_branch_autonomous_lo_filtered_sampled_tone_not_complete_receiver',cases=rows,rf_hz=f+10e6,nominal_if_hz=10e6,baseline_subtracted_samples_v=y.tolist(),held_tone_gain=float(np.hypot(c[1],c[2])/.001),fit_residual_rms_v=float(np.sqrt(np.mean((y-x@c)**2))),runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),limitations=['One branch, no quadrature or ADC; ideal 40MS/s sampling clock and biases.', 'Seeded oscillator, no PLL, intrinsic phase noise, mismatch, PEX, package or pad model.', 'Eight held samples and paired zero subtraction are a diagnostic, not EVM/SNR/ENOB.', 'RF frequency selected using preceding clock measurement; not demonstrated channel tuning or acquisition.', 'Added filter loading may pull oscillator and alter frequency; fixed 10MHz fit is diagnostic.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
