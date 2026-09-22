"""Scope isolation to exactly four RF instances; preserve original PLL feedback."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
D=R/'scratch/transceiver-latest-rf-loop-selective';O=R/'scratch/transceiver-lo-rf-only-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=P/'evidence/latest-rf-loop-selective.json';d=json.loads(e.read_text())
assert d['completed'] and sha(D/'latest.spice')==d['provenance']['artifacts_sha256']['.spice']
s=(D/'latest.spice').read_text();cell=(P/'analog/lo_buffer.spice').read_text()
changed=cell.replace('pt_lo_buffer','pt_lo_rf_isolated').replace('XP2 OUT MID','XCISO MID LOCAL pt_ref_reservoir_4\nRLOCAL LOCAL OUT 10k\nXP2 OUT LOCAL').replace('XN2 OUT MID','XN2 OUT LOCAL').rstrip()
needle='.include /screen/lo_buffer.spice';assert s.count(needle)==1
candidate=s.replace(needle,needle+'\n'+changed)
instances=['XBIP','XBIN','XBQP','XBQN'];replacements=[]
for name in instances:
    lines=[l for l in candidate.splitlines() if l.startswith(name+' ')];assert len(lines)==1
    old=lines[0];assert old.endswith(' pt_lo_buffer')
    new=old.replace(' pt_lo_buffer',' pt_lo_rf_isolated');candidate=candidate.replace(old,new);replacements.append((old,new))
feedback='XFB FBG FB VDIV 0 pt_lo_buffer S=1'
assert feedback in candidate and feedback in s
assert sum(l.startswith('X') and ' pt_lo_rf_isolated' in l for l in candidate.splitlines())==4
assert [l for l in candidate.splitlines() if l.startswith('X') and ' pt_lo_buffer' in l]==[feedback]
assert candidate.count('tran 2p 8001n 0 2p uic')==1
candidate=candidate.replace('tran 2p 8001n 0 2p uic','tran 2p 1001n 0 2p uic')
reverse=candidate.replace('tran 2p 1001n 0 2p uic','tran 2p 8001n 0 2p uic').replace(needle+'\n'+changed,needle)
for old,new in replacements:reverse=reverse.replace(new,old)
assert reverse==s
O.mkdir();(O/'latest.spice').write_text(candidate)
m=json.loads((R/'scratch/transceiver-lo-interstage-autonomous-prepared/manifest.json').read_text())
m.update(artifacts_sha256={'latest.spice':sha(O/'latest.spice')},parent_deck_sha256=sha(D/'latest.spice'),
    candidate='RF-only isolated buffers; XFB original; 1001ns autonomous startup diagnostic.',
    modified_instances=instances,unchanged_feedback_instance=feedback,
    qualification_plan=['Require terminal full1001ns and provenance.','Check original feedback remains distinct.','Compare differential oscillator and Q7, FB crossings, control trajectory and RF output swing.'],
    limitations=['Short seeded startup screen, not full lock/noise/cold-start qualification.','A pass only justifies extending the autonomous run.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
