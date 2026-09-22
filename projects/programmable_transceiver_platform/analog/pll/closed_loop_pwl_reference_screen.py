"""Numerical diagnostic: represent the same ideal reference pulse with explicit PWL."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'closed.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
d=src.read_text();old='VREF REF 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)'
assert d.count(old)==1
# Integer picoseconds avoid cumulative floating-point construction errors.
points=[(0,0)]
for start in range(100000,3201001,51200):
 points += [(start,0),(start+100,3.3),(start+25600,3.3),(start+25700,0)]
new='VREF REF 0 PWL('+' '.join(f'{t}p {v:g}' for t,v in points)+')'
d=d.replace(old,new);assert d.replace(new,old)==src.read_text()
(O/'closed.spice').write_text(d)
manifest=dict(status='running_reference_representation_diagnostic',baseline_deck_sha256=sha(src),reference_points_ps=points,limitations=['Same nominal ideal reference waveform; alternate breakpoint representation, not an implemented oscillator/reference.', 'Seeded/prebiased circuit; no lock, startup or jitter qualification.'])
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with (O/'closed.log').open('w') as log:
 result=subprocess.run(['ngspice','-b',str(O/'closed.spice')],stdout=log,stderr=subprocess.STDOUT,timeout=14400)
manifest['status']='simulator_returned_unverified';manifest['returncode']=result.returncode
manifest['artifacts_sha256']={s:sha(O/('closed'+s)) for s in ('.spice','.log','.dat') if (O/('closed'+s)).exists()}
(O/'result.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Simulator returned',result.returncode,flush=True)
raise SystemExit(result.returncode)
