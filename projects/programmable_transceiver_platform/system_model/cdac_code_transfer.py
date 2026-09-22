"""Evaluate code127 AC fit at other codes without refitting."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
fitpath=P/'evidence/fast-cdac-passive-fit.json';fit=json.loads(fitpath.read_text())
transform=np.array([[1.,1.],[1.,-1.]])/np.sqrt(2)
rows=[];hashes={fitpath.name:hashlib.sha256(fitpath.read_bytes()).hexdigest()}
for code in [0,128,255]:
 path=P/'evidence'/f'adc-cdac-load-matrix-wide-code{code}.json';d=json.loads(path.read_text());hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
 f=np.array(d['frequencies_hz']);s=2j*np.pi*f
 actual=np.array(d['conductance_matrix_s'])+s[:,None,None]*np.array(d['capacitance_matrix_ff'])*1e-15
 modal=np.zeros_like(actual)
 for k,model in enumerate(fit['results']):
  y=model['shunt_conductance_s']+s*model['shunt_capacitance_f']
  for branch in model['branches']:y+=s*branch['capacitance_f']/(1+s*branch['tau_s'])
  modal[:,k,k]=y
 predicted=transform@modal@transform.T
 relative=np.linalg.norm(predicted-actual,axis=(1,2))/np.linalg.norm(actual,axis=(1,2))
 rows.append(dict(code=code,maximum_relative_matrix_error=float(max(relative)),worst_frequency_hz=float(f[np.argmax(relative)]),relative_error=relative.tolist()))
report=dict(status='frozen_model_code_transfer',sources_sha256=hashes,results=rows,limitations=['Fixed-code static AC only; no switching event, reference impedance or dynamic comparator state.', 'Model remains fitted to code127; no data from these codes used to adjust it.', 'Selected endpoints and complementary midpoint are not exhaustive code qualification.'])
(P/'evidence/fast-cdac-code-transfer.json').write_text(json.dumps(report,indent=2)+'\n')
print([(r['code'],r['maximum_relative_matrix_error'],r['worst_frequency_hz']) for r in rows])
