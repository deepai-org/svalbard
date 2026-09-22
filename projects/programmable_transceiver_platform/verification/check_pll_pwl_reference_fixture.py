#!/usr/bin/env python3
"""Verify a fixture change without asserting anything about pending PLL behavior."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-closed-loop-pwl-reference';B=R/'scratch/transceiver-closed-loop-gear'
d=(W/'closed.spice').read_text();base=(B/'closed.spice').read_text()
new=next(x for x in d.splitlines() if x.startswith('VREF '));old=next(x for x in base.splitlines() if x.startswith('VREF '))
assert old=='VREF REF 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)'
assert d.replace(new,old)==base
values=re.fullmatch(r'VREF REF 0 PWL\((.*)\)',new).group(1).split()
t=np.array([int(x.removesuffix('p')) for x in values[::2]],dtype=float)*1e-12
v=np.array([float(x) for x in values[1::2]])
assert np.all(np.diff(t)>0) and v[-1]==0
assert t[-4]+51.2e-9>3201e-9 # next rising edge lies beyond the run
# Check the entire time span, with additional probes around every breakpoint.
probe=np.unique(np.concatenate([np.linspace(0,3201e-9,100001),t,t-1e-14,t+1e-14]));probe=probe[(probe>=0)&(probe<=3201e-9)]
phase=np.remainder(probe-100e-9,51.2e-9)
expected=np.where(phase<100e-12,3.3*phase/100e-12,np.where(phase<25.6e-9,3.3,np.where(phase<25.7e-9,3.3*(25.7e-9-phase)/100e-12,0)))
expected[probe<100e-9]=0
error=float(np.max(abs(np.interp(probe,t,v)-expected)));assert error<1e-8
# Compare with the original simulator's actual reference vector, too.
a=np.loadtxt(B/'closed.dat',skiprows=1,usecols=(0,17))
measured_error=float(np.max(abs(np.interp(a[:,0],t,v)-a[:,1])));assert measured_error<1e-7
r=dict(status='reference_fixture_equivalence_checked_only',probe_count=len(probe),analytical_max_error_v=error,original_simulated_reference_max_error_v=measured_error,only_reference_representation_changed=True,pending_PLL_behavior_verified=False,artifacts_sha256={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (W/'closed.spice',B/'closed.spice',B/'closed.dat')})
(P/'evidence/closed-loop-pwl-reference-fixture.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
