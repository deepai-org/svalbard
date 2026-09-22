"""Prepare one loaded replay candidate; exact reversal verifies the sole circuit edit."""
import argparse,hashlib,json,shutil
ap=argparse.ArgumentParser();ap.add_argument("--half",action="store_true");args=ap.parse_args()
name="lo-second-stage-half" if args.half else "lo-second-stage"
replacement="m={2*S}" if args.half else "m={8*S}"
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-lo-receiver-replay-prepared'
O=R/f'scratch/transceiver-{name}-prepared'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
m=json.loads((B/'manifest.json').read_text())
for n,h in m['artifacts_sha256'].items():assert sha(B/n)==h
scope=P/'evidence/lo-replay-scope.json';assert json.loads(scope.read_text())['scope_use_approved']
original=(B/'replay.spice').read_text()
cell=(P/'analog/lo_buffer.spice').read_text()
assert cell.count('m={4*S}')==2
candidate=cell.replace('m={4*S}',replacement)
assert candidate.replace(replacement,'m={4*S}')==cell
needle='.include /screen/lo_buffer.spice'
assert original.count(needle)==1
changed=original.replace(needle,candidate.rstrip())
assert changed.replace(candidate.rstrip(),needle)==original
O.mkdir()
for n in ('ring_pwl.spice','parent_samples.npy'):shutil.copyfile(B/n,O/n)
(O/'replay.spice').write_text(changed)
m.update(baseline_preparation_sha256=sha(B/'manifest.json'),scope_audit_sha256=sha(scope),candidate=f'Second inverter XP2/XN2 multiplicity m={{4*S}} to {replacement} in all four legs; first stage and actual receiver loads unchanged.',candidate_cell_source_sha256=sha(P/'analog/lo_buffer.spice'),exact_reversal_verified=True)
m['artifacts_sha256']={n:sha(O/n) for n in m['artifacts_sha256']}
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
print(O)
