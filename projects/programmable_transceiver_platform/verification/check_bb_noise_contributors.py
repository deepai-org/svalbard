#!/usr/bin/env python3
"""Attribute stationary noise power without double counting device subtotals."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-bb-noise-contributors';B=R/'scratch/transceiver-bb-noise'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());old=json.loads((B/'result.json').read_text())
assert r['source_sha256_before']==r['source_sha256_after']==old['source_sha256_before']==old['source_sha256_after']
assert sha(W/'model-noise-lines.json')==r['model_excerpts_sha256']
assert [c['name'] for c in r['cases']]==['resistor','filter_f0','filter_f1']
rows=[]
for c,o in zip(r['cases'],old['cases']):
 name=c['name'];assert c['returncode']==o['returncode']==0
 for work,case in ((W,c),(B,o)):
  for ext,h in case['artifacts_sha256'].items():assert sha(work/(name+ext))==h
 d=(W/(name+'.spice')).read_text()
 d=d.replace('dec 40 1k 100meg 1','dec 40 1k 100meg').replace(f'wrdata /work/{name}-contributors.dat all\n','')
 assert d==(B/(name+'.spice')).read_text()
 for ext in ('.dat','-integrated.dat'):
  new_values=np.loadtxt(W/(name+ext),skiprows=1);old_values=np.loadtxt(B/(name+ext),skiprows=1)
  # wrdata's implicit scalar scale changes with extra saved noise vectors.
  if ext=='-integrated.dat':
   with (W/(name+ext)).open() as f:assert f.readline().split()[-2:]==['onoise_total','inoise_total']
   new_values=new_values[1:];old_values=old_values[1:]
  assert np.array_equal(new_values,old_values)
 with (W/(name+'-contributors.dat')).open() as f:h=f.readline().split()
 a=np.loadtxt(W/(name+'-contributors.dat'),skiprows=1)
 assert a.shape==(201,len(h)) and np.isfinite(a).all()
 assert h[:2]==['frequency','frequency'] and np.array_equal(a[:,0],a[:,1])
 assert len(set(h[1:]))==len(h)-1
 def v(n):return a[:,h.index(n)]
 total=v('onoise_spectrum')**2
 # Include each MOS aggregate and each resistor aggregate once, excluding subcomponents.
 devices=[n for n in h if re.fullmatch(r'onoise\.m\..*\.m0',n) or (n.startswith('onoise_r') and not n.endswith(('_thermal','_1overf')))]
 assert len(devices)==(1 if name=='resistor' else 16)
 psd=sum(v(n)**2 for n in devices)
 closure=float(np.max(abs(psd/total-1)));assert closure<1e-10
 # Independently confirm reported MOS aggregate = sum of its detailed noise powers.
 for n in devices:
  if n.startswith('onoise.m.'):
   children=[q for q in h if q.startswith(n+'.')]
   assert children and np.allclose(sum(v(q)**2 for q in children),v(n)**2,rtol=1e-10,atol=1e-60)
 def integral(y):
  f=a[:,0];keep=(f>1e3)&(f<20e6);x=np.r_[1e3,f[keep],20e6]
  return float(np.trapezoid(np.interp(x,f,y),x))
 power=integral(total)
 groups={}
 for n in devices:
  if n in ('onoise_rp','onoise_rn'):group='external_source_resistors'
  elif n in ('onoise_r.xdut.rip','onoise_r.xdut.rin'):group='filter_input_resistors'
  elif n in ('onoise_r.xdut.rfp','onoise_r.xdut.rfn'):group='filter_feedback_resistors'
  elif n.startswith('onoise_r.xdut.'):group='filter_load_resistors'
  elif '.xa.' in n:group='first_stage_mos'
  elif '.xb.' in n:group='second_stage_mos'
  else:group='calibration_resistor'
  groups[group]=groups.get(group,0)+integral(v(n)**2)
 flicker=integral(sum((v(n)**2 for n in h if n.endswith('.1overf')),np.zeros(len(a))))
 rows.append(dict(name=name,sum_closure_max_relative_error=closure,total_output_rms_v=float(np.sqrt(power)),groups={k:dict(output_rms_v=float(np.sqrt(z)),noise_power_fraction=z/power) for k,z in sorted(groups.items(),key=lambda kv:-kv[1])},mos_flicker_noise_power_fraction=flicker/power,device_noise_power_fraction={n:integral(v(n)**2)/power for n in devices}))
out=dict(completed=True,band_hz=[1e3,20e6],unchanged_total_noise_verified=True,provenance=r,cases=rows,limitations=['Stationary symmetric nominal filter; noisy1kohm source legs; no switched mixer or receiver qualification.','Near-zero differential tail contribution depends on symmetry; not immunity to mismatch or common-mode noise.','RMS contributions add in quadrature; fractions are noise power, not voltage amplitude.','Flicker fraction overlaps MOS group fractions and must not be added to them.'])
(P/'evidence/bb-noise-contributors.json').write_text(json.dumps(out,indent=2)+'\n')
for c in rows:print(c['name'],json.dumps(c['groups']), 'MOS flicker fraction',c['mos_flicker_noise_power_fraction'])
