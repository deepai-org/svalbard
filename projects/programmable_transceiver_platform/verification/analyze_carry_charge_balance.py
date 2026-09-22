"""Reservoir/load charge balance; residual includes all non-reservoir circuitry."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-carry-rail-probes'
source=P/'evidence/carry-rail-probes.json';unitpath=P/'evidence/adc-top-load.json'
d=json.loads(source.read_text());unit=json.loads(unitpath.read_text())['unit_capacitance_ff']*1e-15
cap=2048*unit;rows=[]
# Sign control: isolated capacitor withdrawal has zero inferred external replenishment.
assert abs(2e-12+1e-10*(-.02))<1e-27
for case in d['cases']:
 assert case['voltage_reproduction_pass'];p=W/(case['name']+'.dat')
 assert hashlib.sha256(p.read_bytes()).hexdigest()==case['artifacts_sha256']['.dat'];a=np.loadtxt(p,skiprows=1)
 for stop_ns in [2.1,2.2,2.3615,4.4]:
  lo=2e-9;hi=stop_ns*1e-9;t=np.r_[lo,a[(a[:,0]>lo)&(a[:,0]<hi),0],hi];rails={}
  for rail,vcol,icol in [('high',6,9),('low',7,10)]:
   current=np.interp(t,a[:,0],a[:,icol]);charge=float(np.trapezoid(current,t))
   delta=float(np.interp(hi,a[:,0],a[:,vcol])-np.interp(lo,a[:,0],a[:,vcol]))
   reservoir=cap*delta;other=charge+reservoir
   rails[rail]=dict(cdac_charge_into_load_c=charge,reservoir_charge_change_c=reservoir,inferred_nonreservoir_charge_into_rail_c=other,rail_voltage_change_v=delta)
  rows.append(dict(name=case['name'],window_ns=[2,stop_ns],rails=rails))
report=dict(status='approximate_reservoir_charge_balance',source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,unitpath]},reservoir_capacitance_f=cap,results=rows,limitations=['C delta V uses independently measured nominal MIM unit capacitance; voltage dependence not independently bounded here.', 'Residual includes reference driver, compensation and parasitic storage; not isolated output-transistor delivered charge.', 'No direct driver-current probe or independent KCL closure; this is a diagnostic inference.', 'Finite windows, ideal gate controls and selected prebiased fixture only.'])
(P/'evidence/carry-charge-balance.json').write_text(json.dumps(report,indent=2)+'\n')
for r in rows[:4]:print(r['window_ns'],{k:{n:round(v*1e12,3) for n,v in values.items() if n.endswith('_c')} for k,values in r['rails'].items()})
