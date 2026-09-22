"""Test binary-unit rail weighting using endpoint AC data only."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
def read(code):
 name='adc-cdac-load-matrix-wide'+('' if code==127 else f'-code{code}')+'.json'
 path=P/'evidence'/name;d=json.loads(path.read_text());f=np.array(d['frequencies_hz'])
 y=np.array(d['conductance_matrix_s'])+2j*np.pi*f[:,None,None]*np.array(d['capacitance_matrix_ff'])*1e-15
 return path,f,y
p0,f,y0=read(0);p255,f255,y255=read(255);assert np.array_equal(f,f255)
paths=[p0,p255];rows=[]
for code in [85,127,128,170]:
 p,ff,actual=read(code);paths.append(p);assert np.array_equal(f,ff)
 # Every binary group scales switch multiplicity and unit count together.
 # Constant sampler/comparator and dummy contributions survive this interpolation.
 predicted=y0+(code/255)*(y255-y0)
 error=np.linalg.norm(predicted-actual,axis=(1,2))/np.linalg.norm(actual,axis=(1,2))
 rows.append(dict(code=code,maximum_relative_matrix_error=float(max(error)),worst_frequency_hz=float(f[np.argmax(error)]),relative_error=error.tolist()))
assert np.array_equal(y0+0*(y255-y0),y0)
assert np.allclose(y0+(y255-y0),y255,rtol=1e-14,atol=1e-18)
report=dict(status='fixed_code_rail_weighting_check',sources_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},results=rows,limitations=['Only endpoint0/255 AC data define predictions; intermediate codes are comparisons.', 'Ideal rail voltages and fixed bias permit parallel admittance addition; reference impedance can couple branches.', 'Does not define conserved capacitor states or nonlinear charge injection when code changes.', 'Selected codes and nominal process only; not full ADC transfer qualification.'])
(P/'evidence/fast-cdac-rail-weighting.json').write_text(json.dumps(report,indent=2)+'\n')
print([(r['code'],r['maximum_relative_matrix_error']) for r in rows])
