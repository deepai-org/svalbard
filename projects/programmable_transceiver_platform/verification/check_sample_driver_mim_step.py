#!/usr/bin/env python3
"""Measure errors over time windows; never select compensation by one crossing."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-driver-mim-step';B=R/'scratch/transceiver-adc-driver-mim-ac'
base=json.loads((B/'result.json').read_text());rows=[];pending=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for c in base['cases']:
 name=c['name'];log=W/(name+'.log');file=W/(name+'.dat')
 if not file.exists() or not log.exists() or 'Note: Simulation executed from .control section' not in log.read_text():pending.append(name);continue
 original=(B/(name+'.spice')).read_text();assert sha(B/(name+'.spice'))==c['artifacts_sha256']['.spice']
 d=(W/(name+'.spice')).read_text();restored=d.replace('VP GP 0 PWL(0 1.45 20n 1.45 20.1n 1.85 60n 1.85 60.1n 1.45)','VP GP 0 DC 1.65 AC .5').replace('VN GN 0 PWL(0 1.85 20n 1.85 20.1n 1.45 60n 1.45 60.1n 1.85)','VN GN 0 DC 1.65 AC -.5')
 assert restored.split('.control')[0]==original.split('.control')[0]
 assert 'tran 5p 100n 0 5p' in d
 a=np.loadtxt(file,skiprows=1);assert a.shape[1]==8 and np.isfinite(a).all() and a[-1,0]>=100e-9
 t=a[:,0]*1e9;v=a[:,1]-a[:,2];transitions=[]
 for edge,target in ((20,.4),(60,-.4)):
  late=(t>=edge+35)&(t<=edge+39);steady=float(np.mean(v[late]));last_swing=float(np.ptp(v[late]));assert late.sum()>10
  windows=[]
  for lo,hi in ((9,10),(10,12),(15,20),(25,30)):
   w=(t>=edge+lo)&(t<=edge+hi);assert w.sum()>10
   windows.append(dict(after_edge_ns=[lo,hi],max_absolute_error_v=float(np.max(abs(v[w]-target))),max_dynamic_error_from_late_value_v=float(np.max(abs(v[w]-steady))),peak_to_peak_v=float(np.ptp(v[w]))))
  transitions.append(dict(edge_ns=edge,target_v=target,late_value_v=steady,late_static_error_v=steady-target,late_window_peak_to_peak_v=last_swing,windows=windows))
 rows.append(dict(name=name,compensation_pf=c['compensation_pf'],corner=c['corner'],transitions=transitions,supply_peak_current_a=float(np.max(-a[:,7])),artifacts_sha256={s:sha(W/(name+s)) for s in ('.spice','.dat','.log')}))
r=dict(status='partial_isolated_large_signal_audit' if pending else 'completed_isolated_large_signal_audit',cases=rows,pending=pending,qualified_adc=False,limitations=['All load bottoms grounded, sampler always on; finite references/CDAC switching and turnoff absent.', 'Late value is a finite-window estimate, not independently proven DC asymptote.', 'FET typical only; compensation ideal. No noise/mismatch/phase-margin qualification.'])
(P/'evidence/adc-driver-mim-step.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(completed=[dict(name=c['name'],max_10_to_12ns_error_mv=max(f['windows'][1]['max_absolute_error_v'] for f in c['transitions'])*1e3,late_error_mv=[f['late_static_error_v']*1e3 for f in c['transitions']]) for c in rows],pending=pending),indent=2))
