"""Subtract independent reset input load; diagnose fixed-code CDAC series RC."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
paths=[P/'evidence'/n for n in ['adc-cdac-load-matrix.json','adc-top-load-matrix.json']]
a,b=[json.loads(p.read_text()) for p in paths]
assert a['frequencies_hz']==b['frequencies_hz']
f=np.array(a['frequencies_hz']);omega=2*np.pi*f
c=(np.array(a['capacitance_matrix_ff'])-b['capacitance_matrix_ff'])*1e-15
g=np.array(a['conductance_matrix_s'])-b['conductance_matrix_s']
rows=[]
for port in [0,1]:
 y=g[:,port,port]+1j*omega*c[:,port,port];z=1/y
 resistance=float(z[0].real);capacitance=float(-1/(omega[0]*z[0].imag))
 assert resistance>0 and capacitance>0
 predicted=1/(resistance+1/(1j*omega*capacitance))
 rows.append(dict(port=port,low_frequency_series_resistance_ohm=resistance,low_frequency_series_capacitance_f=capacitance,frequencies_hz=f.tolist(),relative_admittance_error=(abs(predicted-y)/abs(y)).tolist(),effective_capacitance_f=c[:,port,port].tolist()))
report=dict(status='fixed_code_linear_impedance_diagnostic',sources_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},results=rows,limitations=['Subtracting independent load assumes unchanged AC bias; only fixed-code ideal-rail fixture tested.', 'Single RC identified at first frequency; high-frequency discrepancy remains explicit.', 'No claim that this RC predicts switching charge, nonlinear conduction or reference feedback.'])
(P/'evidence/fast-cdac-impedance.json').write_text(json.dumps(report,indent=2)+'\n')
print('1GHz relative admittance error', [r['relative_admittance_error'][-1] for r in rows])
