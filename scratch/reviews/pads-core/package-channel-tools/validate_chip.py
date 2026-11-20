"""Validate out/<chip>/package-channel-<chip>.json (per-chip mode; adapted from scratch/pads-core/spec/validate.py).
usage: python3 validate_chip.py <rf|wired> [path]   (exit 0 = all checks pass)"""
import json, sys, os
R = '/home/ubuntu/svalbard/'; T = os.path.dirname(os.path.abspath(__file__)) + '/'
chip = sys.argv[1]
new = json.load(open(sys.argv[2] if len(sys.argv) > 2 else T + f'out/{chip}/package-channel-{chip}.json'))
old = json.load(open(T + 'single-die-2026-11-18.json'))
sys.argv = [sys.argv[0], '--chip', chip]
import channel_model as cm
ok = True
def chk(name, cond, info=''):
    global ok; ok &= bool(cond); print(('PASS ' if cond else 'FAIL ') + name, info)
chk('every template top-level key kept, same order (+chip)', [k for k in new if k != 'chip'] == list(old), [k for k in new if k not in old])
f0 = set(next(iter(old['pins'].values())))
chk('every pin has the old field set', all(set(p) == f0 for p in new['pins'].values()))
bm = cm.read_bond_map(chip)
chk('pins == bond-map signals (name and site)', {s: p['site'] for s, p in new['pins'].items()} == bm,
    sorted(set(bm.items()) ^ {(s, p['site']) for s, p in new['pins'].items()})[:6])
for k in ('supplies_grounds', 'pdn', 'host_ssn', 'thermal', 'board', 'status'): chk('unchanged: ' + k, new[k] == old[k])
GEO = ('board_net', 'connector_contact', 'bond_mm', 'bond_nH_0p83', 'bond_nH_1p0', 'trace_F_mm', 'trace_B_mm', 'trace_w_mm', 'z0_ohm', 'vias', 'via_nH',
       'connector_nH', 'connector_dist_to_gnd_mm', 'cob_delay_ps', 'min_spacing_F_mm', 'min_spacing_B_mm')
ob = {p['bond_pad']: p for p in old['pins'].values()}
bad = [(s, k) for s, p in new['pins'].items() if p['bond_pad'] in ob for k in GEO if ob[p['bond_pad']][k] != p[k]]
chk('per-bond-pad physical fields == single-die file at the same bond pad (%d of %d pins comparable)' %
    (sum(p['bond_pad'] in ob for p in new['pins'].values()), len(new['pins'])), not bad, bad[:4])
m = json.load(open(T + 'site_to_bond.json'))['site_to_bond']
chk('site -> bond pad == north_proof.py (coordinates only)', all(m[p['site']] == p['bond_pad'] for p in new['pins'].values()))
ba = {w['site']: w for w in json.load(open(R + 'scratch/pads-core/bond/bond-audit.json'))['models']['C']['wires'] if 'site' in w}
chk('site -> bond pad and board net == bond-audit.json', all(ba[p['site']]['bond'] == p['bond_pad'] and ba[p['site']]['net'] == p['board_net'] for p in new['pins'].values()))
c = json.load(open(R + 'projects/programmable_transceiver_platform/spec/contract.json'))['assembly_policy']['candidate_signal_sites']
bad = [(s, v) for s, v in c.items() if s.startswith(('D2H', 'H2D', 'HOST_', 'RESET')) and s != 'HOST_CS_N' and new['pins'][s]['site'] != v]
chk('host/south sites == contract candidate_signal_sites (HOST_CS_N: bidir[10] override)', not bad and new['pins']['HOST_CS_N']['site'] == 'bidir[10].pad', bad)
xt = [(s, q) for s, p in new['pins'].items() for q in p['xtalk_dB'] if abs(new['pins'][q]['bond_pad'] - p['bond_pad']) != 1]
chk('every xtalk partner is the adjacent bond pad', not xt, xt[:3])
chk('skew table pairs exist as pins', all((k + '_P' in new['pins'] or k in new['pins'] or k.endswith('_group')) for k in new['intra_pair_and_group_skew']))
print('ALL PASS' if ok else 'FAILED'); sys.exit(0 if ok else 1)
