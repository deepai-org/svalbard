#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-pll-pfd'
r=json.loads((W/'result.json').read_text())
assert len(r['cases'])==3
for c in r['cases']:
 name=f"phase{c['feedback_delay_ns']}"
 for s,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+s)).read_bytes()).hexdigest()==h
 assert c['reset_output_max_v']<.1
 expected=c['feedback_delay_ns']*1e-9*7
 assert abs(c['up_minus_down_s']-expected)<.5e-9
 c['equivalent_net_pulse_per_cycle_s']=c['up_minus_down_s']/7
r['phase_and_reset_checks_pass']=True
(ROOT/'projects/programmable_transceiver_platform/evidence/pll-pfd-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print('Three transistor PFD phase-direction/reset scenarios pass; not a PLL qualification.')
