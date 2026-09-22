"""Apply replay-tested LO isolation to unchanged full autonomous receiver history."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';D=R/'scratch/transceiver-latest-rf-loop-selective';O=R/'scratch/transceiver-lo-interstage-autonomous-prepared'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=P/'evidence/latest-rf-loop-selective.json';d=json.loads(e.read_text());assert d['completed'];assert sha(D/'latest.spice')==d['provenance']['artifacts_sha256']['.spice']
replay=P/'evidence/lo-interstage.json';assert json.loads(replay.read_text())['completed']
s=(D/'latest.spice').read_text();cell=(P/'analog/lo_buffer.spice').read_text();changed=cell.replace('XP2 OUT MID','XCISO MID LOCAL pt_ref_reservoir_4\nRLOCAL LOCAL OUT 10k\nXP2 OUT LOCAL').replace('XN2 OUT MID','XN2 OUT LOCAL');needle='.include /screen/lo_buffer.spice';assert s.count(needle)==1
candidate=s.replace(needle,changed.rstrip());assert candidate.replace(changed.rstrip(),needle)==s
assert 'tran 2p 8001n 0 2p uic' in candidate
O.mkdir();(O/'latest.spice').write_text(candidate)
m=dict(artifacts_sha256={'latest.spice':sha(O/'latest.spice')},source_provenance=json.loads((R/'scratch/transceiver-lo-receiver-replay-prepared/manifest.json').read_text())['source_provenance'],parent_evidence_sha256=sha(e),parent_deck_sha256=sha(D/'latest.spice'),replay_evidence_sha256=sha(replay),candidate='Same4-unit MIM/10k interstage isolation in all four buffers; complete oscillator/divider/PFD/pump/filter/receiver retained.',limitations=['Original prescribed UIC and ideal supplies/reference stimulus; not cold-start or intrinsic phase-noise qualification.','No ADC or host integration in this fixture.','Must compare late lock, receiver disturbance and cycle-local pulses; replay success alone is insufficient.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
