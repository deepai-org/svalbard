#!/usr/bin/env python3
"""Observe internal nodes without changing the pass-121 circuit or stimulus."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');R=Path('/reference');base=(R/'a0.001.spice').read_text()
old='wrdata /work/a0.001.dat diff bb filt held v(HP) v(HN) i(VDD) i(VRFS)'
assert base.count(old)==1
d=base.replace(old,old.replace('/work/a0.001.dat','/work/internal.dat')+' v(GATE) v(DRAIN) v(SOURCE) v(IP) v(INN) v(TESTLO) v(TESTLOB) v(XF.GP) v(XF.GN)')
p=O/'internal.spice';p.write_text(d)
with (O/'internal.log').open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
a=np.loadtxt(O/'internal.dat',skiprows=1);b=np.loadtxt(R/'a0.001.dat',skiprows=1)
assert a.shape[1]==18 and np.isfinite(a).all() and np.array_equal(a[:,:9],b), 'Observation changed original waveforms'
w=a[a[:,0]>=200e-9];t=w[:,0]
summary={label:dict(min_v=float(w[:,col].min()),max_v=float(w[:,col].max()),mean_v=float(np.trapezoid(w[:,col],t)/(t[-1]-t[0]))) for col,label in enumerate(['gate','drain','source','ip','inn','lo','lob','filter_gp','filter_gn'],9)}
r=dict(status='internal_observation_no_circuit_change',original_waveforms_bitwise_identical=True,node_statistics_200_to_301ns=summary,artifacts_sha256={s:hashlib.sha256((O/('internal'+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')},reference_wave_sha256=hashlib.sha256((R/'a0.001.dat').read_bytes()).hexdigest(),limitations=['One nominal ideal-LO signal run; no autonomous clock or noise.', 'Statistics include RF/LO ripple, not only wanted signal.', 'No ADC, process, mismatch, extraction or package validation.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
