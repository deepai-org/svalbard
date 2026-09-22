"""Signed additive-residue sensitivity on recorded paths, not a noise simulation."""
import argparse
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[1]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def interval(decisions):
    # Open interval: equality is an unresolved threshold, not a guaranteed decision.
    positive = [d['preclock_residue_v'] for d in decisions if d['preclock_residue_v'] > 0]
    negative = [d['preclock_residue_v'] for d in decisions if d['preclock_residue_v'] < 0]
    assert len(positive)+len(negative) == len(decisions)
    return -min(positive) if positive else None, -max(negative) if negative else None

def first_flip(decisions, delta):
    return next((d['bit'] for d in decisions
        if d['preclock_residue_v']*(d['preclock_residue_v']+delta) <= 0), None)

control=[dict(bit=1,preclock_residue_v=.002),dict(bit=0,preclock_residue_v=-.003)]
assert interval(control)==(-.002,.003)
assert first_flip(control,-.001) is None and first_flip(control,.002) is None
assert first_flip(control,-.002)==1 and first_flip(control,.003)==0
assert interval([dict(bit=d['bit'],preclock_residue_v=-d['preclock_residue_v']) for d in control])==(-.003,.002)

ap=argparse.ArgumentParser()
ap.add_argument('--reservoir-double',action='store_true')
args=ap.parse_args()
name='sar-driver-reservoir' if args.reservoir_double else 'sar-driver-physical'
source=P/('evidence/'+name+'.json')
d=json.loads(source.read_text())
assert d['completed'], 'Do not score pending or partial runs'
rows=[]
for case in d['cases']:
    assert case['completed']
    for frame in case['frames']:
        decisions=frame['decisions']
        assert all(x['full_swing'] and x['polarity_agrees'] for x in decisions)
        lower,upper=interval(decisions)
        rows.append(dict(case=case['name'],hold_ns=frame['hold_ns'],
            nominal_code_correct=frame['code_error']==0,
            preserves_recorded_path_open_interval_v=[lower,upper],
            signed_sweeps=[dict(additive_residue_v=sign*size,
                first_at_risk_bit=first_flip(decisions,sign*size))
                for size in (.0001,.00025,.0005,.001,.002,.005) for sign in (-1,1)]))
out=dict(source_sha256=sha(source),script_sha256=sha(Path(__file__)),results=rows,
    limitations=['Additive static residue perturbation only; no comparator offset/noise bound is inferred.',
        'Stops at first at-risk decision; changed SAR histories require a new physical simulation.',
        'Preserving an incorrect nominal path is not accuracy.',
        'Clock-edge residue is a proxy; regeneration, kickback and aperture dynamics remain omitted.',
        'Selected inputs only; arbitrarily small margins are expected near quantizer thresholds.'])
(P/('evidence/'+name+'-margin.json')).write_text(json.dumps(out,indent=2)+'\n')
for row in rows:
    print(row['case'],row['hold_ns'],row['nominal_code_correct'],row['preserves_recorded_path_open_interval_v'])
