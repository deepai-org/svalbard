"""Characterize recorded mode1 isolation onset without changing quality gates."""
from pathlib import Path
import json,hashlib
import numpy as np
from chip_model import P
r=P/'evidence'
p=r/'connected-isolated-tx-wideband-mode1-mode1-traces.npz'
a=np.load(p);t=a['time_s'];x=a['ideal_tx'];y=a['actual_tx'];g=a['actual_pad_transfer']
assert len(t)==len(g) and np.all(np.isfinite(g)) and np.all(g>0)
changed=np.flatnonzero(g>.001+1e-8);assert len(changed)
start=max(0,changed[0]-1)
late=np.arange(len(t))>=len(t)//4
gain=np.vdot(x[late],y[late])/np.vdot(x[late],x[late])
rows=[]
for width in (100e-9,200e-9,1e-6):
 mask=(np.arange(len(t))>=start)&(t<=t[start]+width)
 power=float(np.vdot(x[mask],x[mask]).real)
 assert power>0
 ungated=y[mask]/g[mask]
 rows.append(dict(window_s=width,samples=int(mask.sum()),
  raw_relative_rms=float(np.linalg.norm(y[mask]-x[mask])/np.sqrt(power)),
  late_gain_referenced_relative_rms=float(np.linalg.norm(y[mask]-gain*x[mask])/(abs(gain)*np.sqrt(power))),
  isolation_only_increment_relative_rms=float(np.linalg.norm(y[mask]-ungated)/np.sqrt(power))))
report=dict(status='characterized',trace_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),first_observed_transition_time=float(t[start]),
 min_transfer=float(g.min()),max_transfer=float(g.max()),windows=rows,
 limitations=['Descriptive onset windows; no new pass threshold or protocol compliance claim.',
 'Gain is fitted on later samples for diagnosis, not available causal startup calibration.',
 'Dividing by known gate transfer is a frozen-state counterfactual, not an independent analog simulation.',
 'Observation grid may miss instantaneous peaks and the exact switching boundary.'])
(r/'connected-isolated-tx-onset-mode1.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
