#!/usr/bin/env python3
"""Prepare three discriminating cases without editing the active hashed runner."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-pump-follower';O=R/'scratch/transceiver-pump-range-followup-prepared';O.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out']
assert sha(B/'follower.spice')==r['artifacts_sha256']['.spice'];base=(B/'follower.spice').read_text();rows=[]
for control,phase,delay in ((.98,'late600','100.6n'),(1.3,'early','99.7n'),(1.3,'late','100.3n')):
 n=f'v{control:g}_{phase}'
 changes={'VCLAMP CTRL 0 1.08':f'VCLAMP CTRL 0 {control:g}', '.ic v(CTRL)=1.08 v(XFILT.Z)=1.08':f'.ic v(CTRL)={control:g} v(XFILT.Z)={control:g}', '.ic v(DUMMY)=1.08':f'.ic v(DUMMY)={control:g}', 'VFB FB 0 PULSE(0 3.3 99.999n':f'VFB FB 0 PULSE(0 3.3 {delay}', '/work/follower.dat':f'/work/{n}.dat'}
 d=base
 for old,new in changes.items():assert d.count(old)==1;d=d.replace(old,new)
 restored=d
 for old,new in changes.items():assert restored.count(new)==1;restored=restored.replace(new,old)
 assert restored==base
 (O/(n+'.spice')).write_text(d)
 rows.append(dict(name=n,control_v=control,delay=delay,phase=phase,changes=changes,deck_sha256=sha(O/(n+'.spice'))))
out=dict(status='prepared_not_simulated',baseline_sha256=sha(B/'follower.spice'),cases=rows,limitations=['Exact fixture substitutions only; models must be verified by execution runner.','600ps lag tests low-control recovery;1.30V covers historical upper excursion diagnostically, not process bounds.','Ideal clocks, output clamp, precharge and bias currents remain.'])
(O/'manifest.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],len(rows),'exact-reversal cases')
