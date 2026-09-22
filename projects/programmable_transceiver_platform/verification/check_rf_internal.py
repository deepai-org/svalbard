#!/usr/bin/env python3
"""Validate unchanged waveforms and independently crosscheck IF measurement."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-rf-internal';R=ROOT/'scratch/transceiver-rf-ideal-lo'
r=json.loads((W/'result.json').read_text())
for s,h in r['artifacts_sha256'].items():assert hashlib.sha256((W/('internal'+s)).read_bytes()).hexdigest()==h
internal=np.loadtxt(W/'internal.dat',skiprows=1);signal=np.loadtxt(R/'a0.001.dat',skiprows=1);zero=np.loadtxt(R/'a0.dat',skiprows=1)
assert np.array_equal(internal[:,:9],signal)
t=np.arange(200e-9,300e-9,10e-12);y=np.interp(t,signal[:,0],signal[:,2])-np.interp(t,zero[:,0],zero[:,2]);f=np.fft.rfftfreq(len(t),10e-12);z=2*np.abs(np.fft.rfft(y))/len(t)
r['independent_late_uniform_fft_if_gain']=float(z[np.argmin(abs(f-1e7))]/.001)
# Local RF amplitude estimate includes nuisance DC and LO fundamentals/harmonics.
w=internal[(internal[:,0]>=200e-9)&(internal[:,0]<=300e-9)];t=w[:,0];rf=2510416392.628496;lo=rf-1e7
cols=[np.ones(len(t))]
for freq in (rf,lo,2*lo,3*lo,1e7):cols.extend([np.sin(2*np.pi*freq*t),np.cos(2*np.pi*freq*t)])
x=np.column_stack(cols);weight=np.sqrt(np.gradient(t));metrics={}
for name,col in [('gate',9),('drain',10),('source',11)]:
 c=np.linalg.lstsq(x*weight[:,None],w[:,col]*weight,rcond=None)[0];metrics[name]=float(np.hypot(c[1],c[2]))
r['single_run_rf_tone_fit_peak_v']=metrics
r['limitations'].append('Internal RF phasors from one signal run with nuisance-tone fit, not paired subtraction; nearby spurs can bias them.')
(ROOT/'projects/programmable_transceiver_platform/evidence/rf-internal-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(nodes=r['node_statistics_200_to_301ns'],rf_tones=metrics,if_gain=r['independent_late_uniform_fft_if_gain']),indent=2))
