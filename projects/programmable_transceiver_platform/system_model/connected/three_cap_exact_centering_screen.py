"""Compare exact centering states, phase integral and loss against Radau."""
import json,time
import numpy as np
from chip_model import P
from three_cap_centering import ThreeCapCenteringFilter
from three_cap_exact_centering import ExactCenteringFilter
from three_cap_retuning_clock import BALANCED_FILTER

rows=[]
for initial in ([.8,-.7,.6],[-.9,-.2,.4],[.2,.2,.2]):
    slow=ThreeCapCenteringFilter(**BALANCED_FILTER);fast=ExactCenteringFilter(**BALANCED_FILTER)
    for f in (slow,fast):f.state[:3]=initial;f.center_enabled=True
    for end in (1e-9,100e-9,4.8e-6):
        start=time.perf_counter();slow.advance(end,0);slow_s=time.perf_counter()-start
        start=time.perf_counter();fast.advance(end,0);fast_s=time.perf_counter()-start
        error=abs(slow.state-fast.state)
        assert max(error[:3])<1e-10 and error[3]<1e-16 and max(error[4:])<1e-19
        rows.append(dict(initial=initial,time_s=end,node_error_v=float(max(error[:3])),
            integral_error_vs=float(error[3]),loss_error_j=float(error[6]),radau_s=slow_s,exact_s=fast_s))
report=dict(status='passed_local_equivalence',cases=rows,limitations=[
    'Only passive centering accelerated; active compliant pump still uses Radau.',
    'Clock lifecycle and full-chip equivalence require separate tests.'])
(P/'evidence/three-cap-exact-centering-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print('Cases',len(rows),'max node error',max(r['node_error_v'] for r in rows))
