"""Resolve reset/first-clock overlap with a controlled short actual-circuit test."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'pulse_skew-10.spice';base=src.read_text();rows=[]
for release in (90,80):
 name=f'reset{release}';d=base.split('.control')[0]
 assert 'VRN RN 0 PWL(0 0 90n 0 90.1n 3.3)' in d
 d=d.replace('VRN RN 0 PWL(0 0 90n 0 90.1n 3.3)',f'VRN RN 0 PWL(0 0 {release}n 0 {release+.1:g}n 3.3)')
 d+=f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save v(REF) v(FB) v(RN) v(UP) v(DN) v(CTRL) i(VSENSE) v(XFILT.Z)
tran 2p 321n 0 2p uic
wrdata /work/{name}.dat v(REF) v(FB) v(RN) v(UP) v(DN) v(CTRL) i(VSENSE) v(XFILT.Z)
.endc
.end
'''
 (O/(name+'.spice')).write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 rows.append(dict(name=name,reset_release_ns=release,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}));print('Completed '+name,flush=True)
sources=[Path('/screen/pll')/n for n in ('pfd.spice','charge_pump.spice','loop_filter.spice')]
(O/'result.json').write_text(json.dumps(dict(status='reset_phase_comparison_unverified',cases=rows,baseline_deck_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
