#!/usr/bin/env python3
"""Verify noise artifacts/calibration; quantify explicitly limited stationary scenarios."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-bb-noise'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text())
assert r['source_sha256_before']==r['source_sha256_after']
assert sha(W/'model-noise-lines.json')==r['model_excerpts_sha256']
assert [c['name'] for c in r['cases']]==['resistor','filter_f0','filter_f1']
rows=[];arrays={}
for c in r['cases']:
 name=c['name'];assert c['returncode']==0
 assert set(c['artifacts_sha256'])=={'.spice','.log','.dat','-integrated.dat'}
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 log=(W/(name+'.log')).read_text().lower()
 assert not any(x in log for x in ('error','aborted','unknown parameter'))
 with (W/(name+'.dat')).open() as f:assert f.readline().split()==['frequency','onoise_spectrum','inoise_spectrum']
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);arrays[name]=a
 assert a.shape==(201,3) and np.isfinite(a).all() and (a>0).all() and (np.diff(a[:,0])>0).all()
 assert np.isclose(a[0,0],1e3) and np.isclose(a[-1,0],1e8)
 total=np.loadtxt(W/(name+'-integrated.dat'),skiprows=1)
 assert total.shape==(3,) and np.isfinite(total).all() and (total>0).all()
 # Integrate PSD, not amplitude spectral density. Insert exact band endpoints.
 def band(column,high):
  f=a[:,0];keep=(f>1e3)&(f<high);x=np.r_[1e3,f[keep],high]
  psd=np.interp(x,f,a[:,column]**2)
  return float(np.sqrt(np.trapezoid(psd,x)))
 integrated=band(1,1e8)
 assert abs(integrated/total[1]-1)<.005
 rows.append(dict(name=name,fnoicor=c['fnoicor'],output_rms_v_1k_100meg=float(total[1]),input_referred_rms_v_1k_100meg=float(total[2]),output_rms_v_1k_20meg_trapezoid=band(1,20e6),input_referred_rms_v_1k_20meg_trapezoid=band(2,20e6),spot_asd_v_per_sqrt_hz={str(f):dict(output=float(np.interp(f,a[:,0],a[:,1])),input_referred=float(np.interp(f,a[:,0],a[:,2]))) for f in (1e3,1e6,20e6)}))
# Known 1kohm thermal-noise source at27C; tolerate simulator Boltzmann constant rounding.
expected=np.sqrt(4*1.380649e-23*300.15*1000)
control=arrays['resistor'];assert np.max(np.abs(control[:,1:]/expected-1))<.001
f0=(W/'filter_f0.spice').read_text();f1=(W/'filter_f1.spice').read_text()
assert f1.replace('.param fnoicor=1','.param fnoicor=0').replace('filter_f1','filter_f0')==f0
assert np.all(arrays['filter_f1'][:,1]>=arrays['filter_f0'][:,1])
out=dict(completed=True,provenance=r,resistor_expected_asd_v_per_sqrt_hz=float(expected),cases=rows,limitations=['Stationary DC-linearized filter with ideal differential source,1kohm noisy source resistance per leg,CM0.9V,external bias2.25V,TT27C3.3V.','Includes source-resistor and filter noise; not isolated intrinsic filter noise.','PDK fnoicor0/1 scenarios are not guaranteed bounds on fab behavior.','No periodically switched mixer noise folding, LNA noise, oscillator phase noise, bias-supply noise, ADC noise or receiver sensitivity qualification.','1kHz-20MHz is a diagnostic integration band, not proof of usable Wi-Fi bandwidth or EVM.'])
(P/'evidence/bb-noise.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(completed=True,cases=rows),indent=2))
