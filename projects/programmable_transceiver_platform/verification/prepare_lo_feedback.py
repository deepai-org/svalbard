"""Prepare matched feedback-resistor hypothesis tests; production cells unchanged."""
import hashlib,json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[3]
P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-lo-receiver-replay-prepared'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
m=json.loads((B/'manifest.json').read_text())
for name,h in m['artifacts_sha256'].items():assert sha(B/name)==h
scope=P/'evidence/lo-replay-scope.json'
assert json.loads(scope.read_text())['scope_use_approved']
original=(B/'replay.spice').read_text()
for resistance in ['30k','300k']:
    changed=original
    for leg in ['IP','IN','QP','QN']:
        old=f'RFB{leg} B{leg} XB{leg}.MID 100k'
        assert changed.count(old)==1
        changed=changed.replace(old,old.replace('100k',resistance))
    restored=changed
    for leg in ['IP','IN','QP','QN']:
        old=f'RFB{leg} B{leg} XB{leg}.MID {resistance}'
        restored=restored.replace(old,old.replace(resistance,'100k'))
    assert restored==original
    O=R/f'scratch/transceiver-lo-feedback-{resistance}-prepared'
    O.mkdir()
    for name in ['ring_pwl.spice','parent_samples.npy']:shutil.copyfile(B/name,O/name)
    (O/'replay.spice').write_text(changed)
    out=dict(m)
    out.update(baseline_preparation_sha256=sha(B/'manifest.json'),scope_audit_sha256=sha(scope),
               candidate=f'All four self-bias resistors 100k to {resistance}; all other deck text unchanged.',
               exact_reversal_verified=True,
               hypothesis='Feedback strength trades slow bias tracking against signal loading; either direction may worsen recovery.',
               evaluation='Compare complete 512–1024ns window: stage cycle means/swing, missing edges, baseband DC/spur. No acceptance from one metric.',
               limitations=['Seeded replay excludes autonomous backloading and cold startup.',
                            'Changed resistance has different settling time; same window is not proof of steady state.',
                            'Supply current absent; power cannot be qualified.'])
    out['artifacts_sha256']={name:sha(O/name) for name in m['artifacts_sha256']}
    (O/'manifest.json').write_text(json.dumps(out,indent=2)+'\n')
    print(O)
