#!/usr/bin/env python3
"""Check activation and repeatability, never statistical coverage or RF accuracy."""
import hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; WORK=ROOT/'scratch/transceiver-model-behavior'
r=json.loads((WORK/'result.json').read_text()); c=r['cases']
assert len(c)==16 and all(v['complete'] for v in c)
for v in c:
 p=WORK/(v['id']+'.spice'); assert hashlib.sha256(p.read_bytes()).hexdigest()==v['deck_sha256']
nominal=[v for v in c if v['global_switch']==v['mismatch_switch']==v['flicker_corner']==0]
assert all(v['observed']==nominal[0]['observed'] for v in nominal)
global_only=[v for v in c if v['global_switch']==1 and v['mismatch_switch']==0]
assert all(v['pair_current_difference_a']==0 for v in global_only)
assert len({v['observed']['i(v1)'] for v in global_only})==3
mismatch_only=[v for v in c if v['global_switch']==0 and v['mismatch_switch']==1]
assert all(v['pair_current_difference_a']>1e-9 for v in mismatch_only)
assert c[11]['observed']==c[14]['observed'] and c[11]['input_noise_v_per_sqrt_hz']==c[14]['input_noise_v_per_sqrt_hz']
assert c[15]['observed']==c[0]['observed']
ratios={f:20*math.log10(c[15]['input_noise_v_per_sqrt_hz'][f]/c[0]['input_noise_v_per_sqrt_hz'][f]) for f in c[0]['input_noise_v_per_sqrt_hz']}
assert ratios['1000.0']>0 and ratios['1000.0']>ratios['2400000000.0']
r['behavior_checks_pass']=True
r['flicker_corner_input_noise_increase_db']=ratios
r['checker_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(ROOT/'projects/programmable_transceiver_platform/evidence/model-behavior-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(checks=True,flicker_corner_db=ratios),indent=2))
