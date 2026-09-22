#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-closed-loop-pwl-reference'
r=json.loads((W/'result.json').read_text());assert r['returncode']!=0
for ext,digest in r['artifacts_sha256'].items():assert hashlib.sha256((W/('closed'+ext)).read_bytes()).hexdigest()==digest
log=(W/'closed.log').read_text();assert 'Timestep too small' in log and 'tran simulation(s) aborted' in log
failure_time=float(re.search(r'Timestep too small; time = ([0-9.e+-]+)',log).group(1))
a=np.loadtxt(W/'closed.dat',skiprows=1,usecols=(0,14));assert np.isfinite(a).all() and abs(a[-1,0]-failure_time)<1e-12
assert abs(failure_time-637.7e-9)<1e-12
fixture=json.loads((P/'evidence/closed-loop-pwl-reference-fixture.json').read_text());assert fixture['artifacts_sha256']['scratch/transceiver-closed-loop-pwl-reference/closed.spice']==r['artifacts_sha256']['.spice']
r.update(status='aborted_equivalent_reference_diagnostic',actual_stop_ns=float(a[-1,0]*1e9),failure='timestep too small at vsense#branch',edge_coincidence='Reference falling edge ends at 100ns + 10*51.2ns + 25.7ns = 637.7ns',pll_lock_established=False,interpretation='Changing reference breakpoint representation moves failure to an earlier edge; numerical sensitivity observed, physical cause unproven.')
(P/'evidence/closed-loop-pwl-reference-aborted.json').write_text(json.dumps(r,indent=2)+'\n');print(r['interpretation'])
