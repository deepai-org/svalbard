"""Prepare isolated second-inverter bias in the full loaded LO replay."""
import hashlib,json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-lo-receiver-replay-prepared';O=R/'scratch/transceiver-lo-interstage-prepared'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
m=json.loads((B/'manifest.json').read_text())
for name,h in m['artifacts_sha256'].items():assert sha(B/name)==h
scope=P/'evidence/lo-replay-scope.json';assert json.loads(scope.read_text())['scope_use_approved']
cell=(P/'analog/lo_buffer.spice').read_text()
candidate=cell.replace('XP2 OUT MID','XCISO MID LOCAL pt_ref_reservoir_4\nRLOCAL LOCAL OUT 10k\nXP2 OUT LOCAL').replace('XN2 OUT MID','XN2 OUT LOCAL')
assert candidate!=cell
original=(B/'replay.spice').read_text();needle='.include /screen/lo_buffer.spice';assert original.count(needle)==1
changed=original.replace(needle,candidate.rstrip());assert changed.replace(candidate.rstrip(),needle)==original
# Probe local biases and buffer supply to support diagnosis; original outputs retained.
extra=' v(XBIP.LOCAL) v(XBIN.LOCAL) v(XBQP.LOCAL) v(XBQN.LOCAL) i(VBUF)'
lines=changed.splitlines();lines=[line+extra if line.startswith('save ') or line.startswith('wrdata ') else line for line in lines];changed='\n'.join(lines)+'\n'
O.mkdir()
for name in ['ring_pwl.spice','parent_samples.npy']:shutil.copyfile(B/name,O/name)
(O/'replay.spice').write_text(changed)
m.update(candidate='AC-couple MID to second-stage LOCAL with four PDK MIM units;10k feedback LOCAL to OUT, all four legs; original transistor sizes.',baseline_preparation_sha256=sha(B/'manifest.json'),scope_audit_sha256=sha(scope),exact_circuit_reversal_verified=True,added_diagnostic_nodes=extra.split(),limitations=['New LOCAL nodes are not seeded; UIC replay is not cold-start qualification.', 'Local50fF AC evidence does not predict loaded nonlinear operation.', 'Source replay omits autonomous oscillator backloading; any improvement needs full-loop validation.'])
m['artifacts_sha256']={name:sha(O/name) for name in m['artifacts_sha256']}
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
