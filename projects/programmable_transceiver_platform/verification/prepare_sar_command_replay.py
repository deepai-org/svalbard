"""Prepare native-grid eight-command replay and matched shortened baseline."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-adc-sar8-reference-reservoir';O=R/'scratch/transceiver-sar-command-replay-prepared';O.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
evidence=P/'evidence/adc-sar8-reference-reservoir-screen.json';d=json.loads(evidence.read_text());case=next(c for c in d['cases'] if c['name']=='typical_first1')
for ext in ['.spice','.dat']:assert sha(B/('typical_first1'+ext))==case['artifacts_sha256'][ext]
original=(B/'typical_first1.spice').read_text();assert original.count('tran 5p 209.9n 0 5p')==1
baseline=original.replace('tran 5p 209.9n 0 5p','tran 5p 80n 0 5p').replace('/work/typical_first1.dat','/work/baseline.dat')
path=B/'typical_first1.dat'
with path.open() as f:header=f.readline().lower().split()
a=np.loadtxt(path,skiprows=1,usecols=[0]+[header.index(f'v(sd{k})') for k in range(8)]);t=a[:,0]
assert np.isfinite(a).all() and np.all(np.diff(t)>0) and t[0]<=1e-12 and t[-1]>=80e-9
# Explicit t=0 from first saved sample is an approximation, recorded for audit.
mask=(t>0)&(t<80e-9);grid=np.r_[0.,t[mask],80e-9]
values=np.column_stack([np.interp(grid,t,a[:,k+1]) for k in range(8)])
lines=['* Recorded SD commands; ideal replay boundary removes driver-input backloading.']
for k in range(8):
 lines.append(f'VREC{k} RSD{k} 0 PWL(')
 lines.extend(f'+ {tt:.17e} {vv:.17e}' for tt,vv in zip(grid,values[:,k]))
 lines.append('+ )')
(O/'commands.spice').write_text('\n'.join(lines)+'\n')
replay=baseline.replace('/work/baseline.dat','/work/replay.dat')
for k in range(8):
 needle=f'XDRV{k} SD{k} B{k} B{k}B';assert replay.count(needle)==1
 replay=replay.replace(needle,f'XDRV{k} RSD{k} B{k} B{k}B')
replay=replay.replace('.control','.include /prepared/commands.spice\n.control')
restored=replay.replace('.include /prepared/commands.spice\n','').replace('/work/replay.dat','/work/baseline.dat')
for k in range(8):restored=restored.replace(f'XDRV{k} RSD{k} B{k} B{k}B',f'XDRV{k} SD{k} B{k} B{k}B')
assert restored==baseline
(O/'baseline.spice').write_text(baseline);(O/'replay.spice').write_text(replay)
report=dict(status='prepared_not_simulated',source_evidence_sha256=sha(evidence),donor_artifacts_sha256=case['artifacts_sha256'],samples_per_command=len(grid),stop_ns=80,exact_reversal_verified=True,artifacts_sha256={name:sha(O/name) for name in ['baseline.spice','replay.spice','commands.spice']},qualification_plan=['Run shortened baseline and compare donor before using replay.', 'Compare replay held nodes, VH/VL, B7 and first two decisions against shortened baseline.', 'Do not infer hidden internal-state identity from output matches.'],limitations=['Native-grid linear command interpolation may change solver breakpoints and analog results.', 'Value at t=0 is extrapolated constantly from first saved sample.', 'Controller retained but driver-input backloading removed; this must be checked, not assumed harmless.', 'Original DC initialization retained; not cold-start evidence.'])
(O/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('Prepared',len(grid),'points per command; no simulation or reproduction claim')
