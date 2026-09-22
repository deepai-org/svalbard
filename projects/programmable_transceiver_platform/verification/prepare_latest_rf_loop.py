#!/usr/bin/env python3
"""Compose latest RX and actual loop; structural preparation, no simulation."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-bb-connected-bypass';L=R/'scratch/transceiver-closed-loop-follower-prepared';O=R/'scratch/transceiver-latest-rf-loop-prepared';O.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());c=next(c for c in r['cases'] if c['name']=='zero');assert sha(B/'zero.spice')==c['artifacts_sha256']['.spice'] and c['returncode']==0
m=json.loads((L/'manifest.json').read_text());assert sha(L/'closed.spice')==m['prepared_deck_sha256']
base=(B/'zero.spice').read_text();loop=(L/'closed.spice').read_text();block=loop[loop.index('.include /vco/divider.spice'):loop.index('.control')]
block=block.replace('XD1 XRX.CP XRX.CN','XD1 P N')
# Latest RF already owns regeneration, MIM library selection and reservoir cell
# definitions through rc_split.spice. Preserve its original choices.
for line in ('VREGEN REGEN 0 1.08\n','.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical\n','.include /screen/reference/reservoir_mim.spice\n'):
 assert block.count(line)==1;block=block.replace(line,'')
assert base.count('VCTRL CTRL 0 1.08\n')==1
extra=' v(CTRL) v(FB) v(REF) v(UP) v(DN) v(XFILT.Z) i(VSENSE) i(VDIV) v(DUMMY) i(VDRV) i(VDUMMY) v(Q7P) v(Q7N)'
d=base.replace('VCTRL CTRL 0 1.08\n','').replace('.control',block+'.control').replace('tran 2p 401n 0 2p uic','tran 2p 3201n 0 2p uic').replace('/work/zero.dat','/work/latest.dat')
d='\n'.join(line+extra if line.startswith('wrdata ') else line for line in d.split('\n'))
rev='\n'.join(line.removesuffix(extra) if line.startswith('wrdata ') else line for line in d.split('\n'))
rev=rev.replace(block,'').replace('VREGEN REGEN 0 1.08','VCTRL CTRL 0 1.08\nVREGEN REGEN 0 1.08').replace('tran 2p 3201n 0 2p uic','tran 2p 401n 0 2p uic').replace('/work/latest.dat','/work/zero.dat')
assert rev==base
assert 'XD1 P N ' in d and 'VCTRL ' not in d and 'VCLAMP ' not in d
(O/'latest.spice').write_text(d)
out=dict(status='prepared_not_simulated',receiver_sha256=sha(B/'zero.spice'),loop_sha256=sha(L/'closed.spice'),deck_sha256=sha(O/'latest.spice'),receiver_exact_reversal=True,limitations=['Zero RF input; seeded VCO and biases, no cold-start or noise qualification.','Actual added divider changes oscillator load; no old-loop tuning/lock claim transfers.','Ideal bias/reference/supplies and absent ADC output loading remain.','Requires simulator elaboration and independent model provenance before execution.'])
(O/'manifest.json').write_text(json.dumps(out,indent=2)+'\n');(P/'evidence/latest-rf-loop-preparation.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'])
