"""Predict floating-load clock motion from independent clamped charge and AC C."""
import hashlib,json
from pathlib import Path
import numpy as np
from cdac_prediction_fixture import compare_prediction, __file__ as comparison_source
P=Path(__file__).resolve().parents[1];R=P.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths={name:P/'evidence'/name for name in ['adc-kickback-fine-clamped.json','adc-cdac-kickback.json','adc-top-load-matrix.json','adc-top-load.json','fast-cdac-impedance.json']}
d={name:json.loads(p.read_text()) for name,p in paths.items()}
c=np.array(d['adc-top-load-matrix.json']['capacitance_matrix_ff'][0])*1e-15
rc=d['fast-cdac-impedance.json']['results']
ca=np.diag([r['low_frequency_series_capacitance_f'] for r in rc])
g=np.diag([1/r['low_frequency_series_resistance_ohm'] for r in rc])
ctinv=np.linalg.inv(c);cainv=np.linalg.inv(ca)
A=np.block([[-ctinv@g,ctinv@g],[cainv@g,-cainv@g]])
B=np.vstack([ctinv,np.zeros((2,2))])
def response(current,dt):
    left=np.eye(4)-dt*A/2
    transition=np.linalg.solve(left,np.eye(4)+dt*A/2)
    drive=np.linalg.solve(left,dt*B/2)
    state=np.zeros(4);out=np.zeros((len(current),2))
    for k in range(1,len(current)):
        state=transition@state+drive@(current[k-1]+current[k])
        out[k]=state[:2]
    return out
assert np.array_equal(response(np.zeros((10,2)),1e-13),np.zeros((10,2)))
assert np.all(np.linalg.eigvalsh(c)>0)
assert np.allclose(np.linalg.solve(np.diag([2.,4.]),[2.,8.]),[1.,2.])
rows=compare_prediction(d,R,response)
report=dict(status='independent_fixture_prediction_comparison',source_sha256={n:sha(p) for n,p in paths.items()},script_sha256=sha(Path(__file__)),results=rows,limitations=['No fitted voltage gain or time shift; current sign and timing use SPICE source conventions.', 'Reset input matrix plus one series RC per CDAC side; nonlinear switching and reference dynamics omitted.', 'Clamped and floating input trajectories differ, including sampler-induced initial bias.', 'Two nominal inputs with fixed-code127 transistor CDAC and ideal rails; not full SAR or new process conditions.'])
report['comparison_sha256']=sha(Path(comparison_source))
(P/'evidence/fast-cdac-kickback-prediction.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
