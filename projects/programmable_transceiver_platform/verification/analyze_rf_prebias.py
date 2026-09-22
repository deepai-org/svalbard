#!/usr/bin/env python3
"""Compare paired signal/zero runs without treating fit residuals as noise."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
rows=[]
for label,folder in [('baseline_1pf','transceiver-rf-ideal-lo'),('prebiased','transceiver-rf-ideal-lo-prebias')]:
 w=ROOT/'scratch'/folder;r=json.loads((w/'result.json').read_text());waves=[]
 for case in r['cases']:
  name=f"a{case['amplitude_v']:g}"
  for s,h in case['artifacts_sha256'].items():assert hashlib.sha256((w/(name+s)).read_bytes()).hexdigest()==h
  if label=='prebiased':
   deck=(w/(name+'.spice')).read_text()
   normalized=deck.replace('.ic v(GATE)=1.5\n','')
   assert normalized==(ROOT/'scratch/transceiver-rf-ideal-lo'/(name+'.spice')).read_text(), 'Unintended fixture change'
  a=np.loadtxt(w/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and a[-1,0]>300e-9;waves.append(a)
 a,b=waves;b=b[b[:,0]>=100e-9];t=b[:,0];weight=np.sqrt(np.gradient(t));x=np.column_stack([np.ones(len(t)),np.sin(2*np.pi*1e7*t),np.cos(2*np.pi*1e7*t)])
 gains={}
 for stage,col in [('mixer',2),('filter',3)]:
  y=b[:,col]-np.interp(t,a[:,0],a[:,col]);c=np.linalg.lstsq(x*weight[:,None],y*weight,rcond=None)[0];gains[stage]=float(np.hypot(c[1],c[2])/.001)
 gains['held']=r['held_tone_gain']
 ts=np.array(r['cases'][0]['sample_times_s']);y=np.array(r['baseline_subtracted_samples_v']);blocks=[]
 for start in (0,4):
  tb=ts[start:start+4];yb=y[start:start+4];xb=np.column_stack([np.ones(4),np.sin(2*np.pi*1e7*tb),np.cos(2*np.pi*1e7*tb)]);cb=np.linalg.lstsq(xb,yb,rcond=None)[0];blocks.append(float(np.hypot(cb[1],cb[2])/.001))
 r['four_sample_held_gains']=blocks
 r['late_zero_input_sample_rms_about_mean_v']=float(np.std(np.array(r['cases'][0]['held_samples_v'])[-4:]))
 rows.append(dict(case=label,gains_v_per_v=gains,raw_result=r))
r=dict(status='prebiased_ideal_lo_comparison_not_startup_or_radio_qualification',cases=rows,limitations=['Ideal sources disconnect real mixer gate load from oscillator buffers; no equal-power or equal-loading clock comparison.', 'Fixed receive topology, input tone and sample timing; ideal LO phase differs from autonomous clock, compare tone magnitudes.', 'Only gate initial condition changes. Prebias is not a implemented startup solution; internal bias still needs waveform checks.', 'No intrinsic noise, ADC, quadrature, process, mismatch, PEX, EVM or blocker qualification.'])
r['held_gain_ratios_to_underbiased']={row['case']:row['gains_v_per_v']['held']/rows[0]['gains_v_per_v']['held'] for row in rows[1:]}
(ROOT/'projects/programmable_transceiver_platform/evidence/rf-prebias-comparison.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([dict(case=row['case'],gains=row['gains_v_per_v']) for row in rows],indent=2))
