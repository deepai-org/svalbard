#!/usr/bin/env python3
"""Compare matched tighter-tolerance runs and each original trajectory."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
R = Path(__file__).resolve().parents[3]
P = R/'projects/programmable_transceiver_platform'
ap=argparse.ArgumentParser()
ap.add_argument('--reltol',action='store_true')
args=ap.parse_args()
name='cdac-probe-reltol' if args.reltol else 'cdac-probe-convergence'
W = R/'scratch'/('transceiver-'+name)
expected_options='option reltol=1e-5' if args.reltol else 'option reltol=1e-5 abstol=1e-14 vntol=1e-8'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(root):
    rec = json.loads((root/'result.json').read_text())
    assert rec['source_sha256_before'] == rec['source_sha256_after']
    for ext, expected in rec['artifacts_sha256'].items():
        assert sha(root/('frames'+ext)) == expected
    assert rec['returncode'] == 0 and not rec['timed_out']
    assert 'aborted' not in (root/'frames.log').read_text().lower()
    with (root/'frames.dat').open() as f:
        h = f.readline().lower().split()
    a = np.loadtxt(root/'frames.dat', skiprows=1)
    assert a.shape[1] == len(h) and np.isfinite(a).all()
    assert np.all(np.diff(a[:,0]) > 0) and a[-1,0]+1e-21 >= 209.9e-9
    return h, a

names = ['v(hp)','v(hn)','v(q_hp)','v(q_hn)','v(vh)','v(vl)','v(ip)','v(in)']
def compare(left, right):
    h,a = left
    j,b = right
    same = np.array_equal(a[:,0], b[:,0])
    assert a[0,0] >= b[0,0] and a[-1,0] <= b[-1,0]+1e-21
    err = {n: float(np.max(abs(a[:,h.index(n)] - np.interp(a[:,0],b[:,0],b[:,j.index(n)])))) for n in names}
    return dict(same_time_grid=same, errors_v=err, below_original_10uv_limit=max(err.values()) < 1e-5,
                interpolation='Right trajectory linearly interpolated onto left timestamps; no time alignment.')

out = dict(status='pending', completed=False)
cases = {}
for case in ('baseline','probed'):
    root = W/case
    if not (root/'result.json').exists():
        cases[case] = dict(status='pending')
        continue
    rec = json.loads((root/'result.json').read_text())
    assert rec['source_sha256_before'] == rec['source_sha256_after']
    m = json.loads((root/'manifest.json').read_text())
    assert sha(root/'frames.spice') == m['deck_sha256_before']
    for ext, expected in rec['artifacts_sha256'].items():
        assert sha(root/('frames'+ext)) == expected
    log = (root/'frames.log').read_text()
    errors = [line.strip() for line in log.splitlines() if 'timestep too small' in line.lower() or 'aborted' in line.lower()]
    cases[case] = dict(status='terminal', returncode=rec['returncode'], timed_out=rec['timed_out'],
                       errors=errors, result_sha256=sha(root/'result.json'))
out['cases'] = cases
failed = any(c.get('returncode', 0) != 0 or c.get('timed_out', False) or c.get('errors') for c in cases.values())
if failed:
    out['status'] = 'comparison_unavailable'
    out['reason'] = 'At least one case failed; pending cases may continue, but no matched convergence claim is possible.'
if not failed and all((W/c/'result.json').exists() for c in ('baseline','probed')):
    data = {}
    manifests = {}
    for case, old in [('baseline','transceiver-adc-reference-current'),('probed','transceiver-cdac-branch-replay')]:
        root = W/case
        m = json.loads((root/'manifest.json').read_text())
        assert sha(root/'frames.spice') == m['deck_sha256_before']
        assert sha(R/'scratch'/old/'frames.spice') == m['parent_deck_sha256']
        assert m['settings'] == expected_options
        data[case] = read(root)
        data[case+'_original'] = read(R/'scratch'/old)
        manifests[case] = sha(root/'manifest.json')
    out.update(status='terminal', completed=True, manifest_sha256=manifests,
               matched_pair=compare(data['probed'],data['baseline']),
               baseline_tolerance_change=compare(data['baseline'],data['baseline_original']),
               probed_tolerance_change=compare(data['probed'],data['probed_original']))
    captures = {}
    for case in ('baseline','probed','baseline_original','probed_original'):
        h,a = data[case]
        values = []
        for hold in (70,120,170):
            mask = (a[:,0] >= (hold+39.3)*1e-9) & (a[:,0] <= (hold+39.7)*1e-9)
            assert mask.any()
            for prefix in ('','q_'):
                v = a[mask][:,[h.index(f'v({prefix}d{i})') for i in range(8)]]
                assert np.all((v < .33) | (v > 2.97))
                values.append(np.unique((v>1.65).astype(int)@2**np.arange(8)).tolist())
        captures[case] = values
    out['captured_codes'] = captures
    out['codes_match_all_runs'] = all(v == captures['baseline'] for v in captures.values())
    # Independent rail closure is necessary before any later branch attribution.
    h,a = data['probed']
    def vec(n): return a[:,h.index(n)]
    balances = {}
    for rail in ('h','l'):
        ports = [f'i(v.{inst}.x{side}{bit}.x{rail}.vport)'
                 for inst in ('xd','xq_d') for side in ('p','n') for bit in range(8)]
        residual = vec(f'i(vref{rail}_del)')-vec(f'i(vref{rail}_res)')-sum(vec(n) for n in ports)
        balances[rail] = dict(max_residual_a=float(abs(residual).max()),
                              signed_residual_charge_c=float(np.trapezoid(residual,a[:,0])),
                              closed_test=rail=='h')
    out['rail_current_sums'] = balances
    out['high_rail_kcl_verified'] = balances['h']['max_residual_a'] < 1e-9
    out['low_rail_caveat'] = 'Four dummy-capacitor reference terminals are unsensed; low-rail residual is not a closed KCL test.'
out['limitations'] = ['No circuit promotion or automatic branch attribution from this diagnostic.',
                       'Two tolerance settings do not prove numerical convergence, intrinsic noise, or ADC precision.',
                       'A failed original replay gate remains failed regardless of this result.']
(P/'evidence'/(name+'.json')).write_text(json.dumps(out,indent=2)+'\n')
print(out['status'],out['completed'])
