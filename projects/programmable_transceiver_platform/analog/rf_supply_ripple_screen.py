#!/usr/bin/env python3
"""Deterministic supply-to-timing transfer, not intrinsic random jitter."""
from pathlib import Path
import argparse,json,hashlib,subprocess
parser=argparse.ArgumentParser();parser.add_argument("--step-ps",type=float,default=2);args=parser.parse_args()
import numpy as np
O=Path('/work');B=Path('/clock')
d=(B/'v3.3.spice').read_text().replace('VDD VDD 0 3.3','VDD VDD 0 SIN(3.3 0.01 100meg)').replace('/work/v3.3.dat','/work/ripple.dat')
d=d.replace('tran 2p 81n 0 2p uic',f'tran {args.step_ps}p 81n 0 {args.step_ps}p uic')
p=O/'ripple.spice';p.write_text(d)
with (O/'ripple.log').open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
def fit(path):
 a=np.loadtxt(path,skiprows=1);assert np.isfinite(a).all() and a[-1,0]>80e-9
 a=a[a[:,0]>=40e-9];t=a[:,0];ix=np.where((a[:-1,2]<1.65)&(a[1:,2]>=1.65))[0]
 e=t[ix]+(t[ix+1]-t[ix])*(1.65-a[ix,2])/(a[ix+1,2]-a[ix,2]);n=np.arange(len(e));assert len(e)>90
 x=np.column_stack([np.ones(len(e)),n,np.sin(2*np.pi*100e6*e),np.cos(2*np.pi*100e6*e)])
 c=np.linalg.lstsq(x,e,rcond=None)[0]
 return dict(edges=len(e),fit_timing_sin_s=float(c[2]),fit_timing_cos_s=float(c[3]),fitted_period_s=float(c[1]),residual_rms_s=float(np.sqrt(np.mean((e-x@c)**2))))
b=fit(B/'v3.3.dat');r=fit(O/'ripple.dat');amp=float(np.hypot(r['fit_timing_sin_s']-b['fit_timing_sin_s'],r['fit_timing_cos_s']-b['fit_timing_cos_s']))
j=dict(status='deterministic_100MHz_supply_ripple_transfer_not_phase_noise',maximum_timestep_ps=args.step_ps,ripple_peak_v=.01,ripple_hz=100e6,reference=b,ripple=r,baseline_subtracted_timing_peak_s=amp,timing_peak_s_per_supply_peak_v=amp/.01,artifacts_sha256={s:hashlib.sha256((O/('ripple'+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')},reference_wave_sha256=hashlib.sha256((B/'v3.3.dat').read_bytes()).hexdigest(),limitations=['Four late ripple cycles; compare recorded timestep variants for numerical sensitivity.', 'Oscillator rail only, ideal RF buffer rail and tuning bias.', 'Deterministic supply-induced timing; not device phase noise, total jitter or PLL rejection.'])
(O/'result.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j,indent=2))
