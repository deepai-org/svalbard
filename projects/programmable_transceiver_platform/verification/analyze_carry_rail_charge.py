"""Signed CDAC rail demand only after matched probe reproduction passes."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-carry-rail-probes';source=P/'evidence/carry-rail-probes.json';d=json.loads(source.read_text());rows=[]
for c in d['cases']:
 assert c['voltage_reproduction_pass'];p=W/(c['name']+'.dat');assert hashlib.sha256(p.read_bytes()).hexdigest()==c['artifacts_sha256']['.dat'];a=np.loadtxt(p,skiprows=1)
 t=np.r_[2e-9,a[(a[:,0]>2e-9)&(a[:,0]<4.4e-9),0],4.4e-9];rails={}
 for label,col in [('high',9),('low',10)]:
  current=np.interp(t,a[:,0],a[:,col]);rails[label]=dict(net_charge_into_cdac_c=float(np.trapezoid(current,t)),peak_current_into_cdac_a=float(max(current)),peak_current_returned_to_rail_a=float(max(-current)))
 rows.append(dict(name=c['name'],window_ns=[2,4.4],rails=rails))
report=dict(status='signed_rail_demand_diagnostic',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),results=rows,limitations=['Integrated total rail current, no branch/path attribution or baseline DC subtraction.', 'Finite window ends before complete recovery; not full-cycle energy or charge balance.', 'Ideal gate controls, one CDAC and prebiased reference fixture.'])
(P/'evidence/carry-rail-charge.json').write_text(json.dumps(report,indent=2)+'\n');print(rows)
