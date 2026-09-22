"""Locate decision errors in completed physical-reference driver experiments."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parents[1]
R = P.parents[1]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def search(anchor):
    code = 0
    steps = []
    for bit in range(7, -1, -1):
        trial = code + (1 << bit)
        keep = anchor + (trial - 128) / 128 <= 0
        steps.append(dict(trial=trial, keep=keep))
        if keep:
            code = trial
    return code, steps

# Independent transfer and exact boundary controls.
for k in range(256):
    for fraction in (0, .25, .75):
        assert search((128-k-fraction)/128)[0] == k
for x in (-2., -1., -.4, 0., .4, 1., 2.):
    assert search(x)[0] == max(0, min(255, math.floor(128-128*x)))

ap=argparse.ArgumentParser()
ap.add_argument('--reservoir-double',action='store_true')
args=ap.parse_args()
source = P/('evidence/sar-driver-reservoir.json' if args.reservoir_double else 'evidence/sar-driver-physical.json')
d = json.loads(source.read_text())
assert d['completed']
rows = []
for case in d['cases']:
    path = R/('scratch/transceiver-'+case['name'])/'baseline.dat'
    assert sha(path) == case['waveform_sha256']
    with path.open() as f:
        header = f.readline().lower().split()
    a = np.loadtxt(path, skiprows=1)
    def at(node, ns):
        return float(np.interp(ns*1e-9, a[:, 0], a[:, header.index('v('+node+')')]))
    for frame in case['frames']:
        hold = frame['hold_ns']
        anchor = frame['decisions'][0]['preclock_residue_v']
        span0 = frame['decisions'][0]['reference_span_v']
        held_code, expected = search(anchor)
        events = []
        actual_code = 0
        for j, (decision, ideal) in enumerate(zip(frame['decisions'], expected)):
            ns = hold+.5+5*j
            bits = [at('sd'+str(k), ns) for k in range(8)]
            assert all(v < .33 or v > 2.97 for v in bits)
            trial = sum(int(v > 1.65)*2**k for k, v in enumerate(bits))
            assert trial == actual_code+(1 << decision['bit'])
            q = at('qp', hold+2.4+5*j)-at('qn', hold+2.4+5*j)
            assert abs(q) > 2.97
            keep = q < 0
            if keep:
                actual_code = trial
            rail = anchor+((2*trial-255)*decision['reference_span_v']-span0)/256
            events.append(dict(bit=decision['bit'], actual_trial=trial,
                ideal_trial=ideal['trial'], actual_keep=keep, ideal_keep=ideal['keep'],
                actual_residue_v=decision['preclock_residue_v'],
                reference_span_v=decision['reference_span_v'],
                high_rail_error_v=at('vh',ns)-2.15,
                low_rail_error_v=at('vl',ns)-1.15,
                span_slope_v_per_ns=((at('vh',ns)-at('vl',ns))-(at('vh',ns-.2)-at('vl',ns-.2)))/.2,
                nominal_rail_residue_v=anchor+(trial-128)/128,
                measured_rail_residue_v=rail,
                unexplained_residue_v=decision['preclock_residue_v']-rail,
                diverges=keep != ideal['keep']))
        assert actual_code == frame['final_code']
        first = next((e for e in events if e['diverges']), None)
        if first:
            assert first['actual_trial'] == first['ideal_trial']
        rows.append(dict(case=case['name'], hold_ns=hold,
            actual_code=actual_code, source_ideal_code=frame['ideal_source_code'],
            held_ideal_code=held_code, first_divergence=first, steps=events))
out = dict(source_sha256=sha(source), script_sha256=sha(Path(__file__)), results=rows,
    limitations=['Rail formula assumes equal capacitors and bottom plates following rails; residual is not a unique mechanism.',
        'Held anchor hides acquisition and initial loading errors.',
        'Only the first divergence has matched ideal/actual histories.',
        'Three frames at each of two levels do not establish linearity or noise.'])
(P/('evidence/sar-reservoir-driver-divergence.json' if args.reservoir_double else 'evidence/sar-physical-divergence.json')).write_text(json.dumps(out, indent=2)+'\n')
for row in rows:
    print(row['case'], row['hold_ns'], 'actual/source/held', row['actual_code'],
          row['source_ideal_code'], row['held_ideal_code'], row['first_divergence'])
