#!/usr/bin/env python3
"""Skeleton chip plan: which cell goes where, real GDS or placeholder.

Inputs : skeleton/floorplan-<chip>.json (the chip's die-fit packer result), integration/chips/<chip>/chip.conn + masters.txt (instances,
         masters, pin lists), GDS candidates per master.
Output : <run>/skel/plan.json for skeleton/build.py (KLayout).  Light, host python, no tools.

Blocks the packer could not place are squeezed into what is left ("overflow": 4 um spacing, no halo, no keep-away
rules, decap bank tiles give way); what still does not fit is listed and left out.
"""
import hashlib, json, os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); SO = os.path.dirname(HERE)
P = os.path.dirname(os.path.dirname(SO)); ROOT = os.path.dirname(os.path.dirname(P))
CHIP = os.environ['SIGNOFF_CHIP']        # rf | wired
RUN = os.environ.get('SIGNOFF_RUN', ROOT+f'/scratch/integration/signoff-run-{CHIP}')
sys.path.insert(0, P+'/integration/chips')
import check_top as ct

A = 'projects/programmable_transceiver_platform/analog/'
IS = 'scratch/island-support-20261108-075605/'
fp = json.load(open(HERE+f'/floorplan-{CHIP}.json'))
staged = json.load(open(ROOT+'/scratch/reviews/die-fit/m45free_staged.json'))
inst, ports, _w, err = ct.parse(ct.read_conn(f'{P}/integration/chips/{CHIP}/chip.conn'))
masters = ct.load_masters(open(P+'/integration/chips/masters.txt').read())
assert not err, err

# master -> [(gds path relative to repo root, top cell or None, kind)], first that fits its floorplan rectangle is used
SPECIAL = {
    'por': [(A+'core_support/por/gds/gf180mcu_ocd_ip__por.gds.gz', 'gf180mcu_ocd_ip__por')],
    'tx_steer': [(A+'pads/generated/steering-buffer-compact/tx_steering_buffer_flat.gds', 'tx_steering_buffer_flat')],
    'term_buffer': [(A+'pads/generated/termination-buffer-candidate/compact-array/buffer_compensated_flat.gds', 'buffer_compensated_flat')],
    'tx_interlock': [(A+'pads/generated/packaging-assembly.gds', 'attached_tx_interlock')],
    'pt_core_bias_rf': [('scratch/core-bias-rf/routing/pt_core_bias_routed.gds', 'pt_core_bias_rf')],
    'pt_core_bias_wired': [('scratch/core-bias-wired/routing/pt_core_bias_routed.gds', 'pt_core_bias_wired')],
    'pt_lc_qvco5': [(A+'timing/generated/lcvco/pt_lc_qvco5.gds', 'pt_lc_qvco5')],
    'pt_usb_txdrv': [(A+'wired_tx/generated/usbdrv.gds', None)],
    'iso_clamp': [(IS+'layout/iso_clamp.gds', 'iso_clamp')],
    'pad_tlp': [(A+'pads/generated/tlp-site/pad_tlp_flat.gds', 'pad_tlp_flat')],
    'pad_rf_pair': [(A+'pads/generated/stress-safe-families/rf-pair/pad.gds', None)],
    'pad_rftxpad': [(A+'pads/generated/stress-safe-families/rf-tx/pad.gds', None)],
    'pad_single_leg': [(A+'pads/generated/stress-safe-families/single-leg/pad.gds', None)],
    'pad_refpad': [(A+'pads/generated/stress-safe-families/reference/combined.gds', None)],
    'pad_hspad': [(A+'pads/generated/stress-safe-families/wired-receive-hs/pad_hspad.gds', None)],
    'pad_wirepad': [(A+'pads/generated/stress-safe-families/wired-receive-usb/combined.gds', None)],
    'pad_txpad': [(A+'pads/generated/stress-safe-families/wired-transmit/combined.gds', None)],
    'pt_digital_macro': [('scratch/digital-hardening-ac1-r4/export/pt_digital_macro.gds', 'pt_digital_macro')],
}
for n in ('isw_wired', 'isw_rf', 'isw_pll', 'isw_conv', 'isw_debug', 'atb_leaf_s', 'atb_leaf_f', 'atb_grp', 'atb_pad'):
    SPECIAL[n] = [(IS+f'layout/{n}.gds', n)]


_sha = {}
TWIN = {'pt_adc_q': 'pt_adc_i', 'pt_dac_q': 'pt_dac_i'}
def candidates(m):
    out = []
    for g, c in SPECIAL.get(m, []):
        out.append(dict(gds=g, cell=c, kind='published' if g.startswith(A) else 'scratch'))
    md = masters.get(m)
    if md and md.get('path') and m not in SPECIAL:
        rel = os.path.relpath(md['path'], ROOT)
        stem = re.sub(r'(\.ext|\.pex|_ext)?\.spice$', '', rel)
        out.append(dict(gds=stem+'.gds', cell=md['sub'], kind='published'))
    if m in staged and 'file' in staged[m]:
        out.append(dict(gds=staged[m]['file'].lstrip('/'), cell=staged[m].get('top'), kind='staged'))
    t = TWIN.get(m)      # Q twin not staged separately: the I cell stands in (same outline)
    if t and t in staged and 'file' in staged[t]:
        out.append(dict(gds=staged[t]['file'].lstrip('/'), cell=staged[t].get('top'), kind='staged-twin'))
    out = [c for c in out if os.path.exists(ROOT+'/'+c['gds'])]
    for c in out:
        if c['gds'] not in _sha: _sha[c['gds']] = hashlib.sha256(open(ROOT+'/'+c['gds'], 'rb').read()).hexdigest()
        c['sha256'] = _sha[c['gds']]
    return out


def pins_of(m):
    md = masters.get(m)
    if not md: return []
    return (md['pins'] if md['kind'] != 'file' else ct.subckt_pins(md['path'], md['sub'])) or []


item_master = {k: v[0] for k, v in fp['items'].items()}
rects = {k: dict(v) for k, v in fp['placed_rects'].items()}
unplaced = [u[0] for u in fp['unplaced']]

# ---- overflow placement of what the packer left out (2 um bitmap) -------------------------------------------------------
G = 2.0; NX, NY = int(3932/G), int(5122/G)
occ = np.ones((NX, NY), bool)
CORE = (452.0, 452.0, 3480.0, 4670.0)
def cells(r, grow=0.0):
    return (max(0, int((r[0]-grow)//G)), max(0, int((r[1]-grow)//G)), min(NX, int(-(-(r[2]+grow)//G))), min(NY, int(-(-(r[3]+grow)//G))))
def mark(r, v, grow=0.0):
    a, b, c, d = cells(r, grow); occ[a:c, b:d] = v
mark(CORE, False)
for n, rs in fp['pads'].items():
    for r in rs: mark(r, True, 10.0)
for n, r in fp['fixed'].items(): mark(r, True, 4.0)
for n, v in rects.items():
    if not n.startswith(('decap_bank', 'decap_tile')): mark(v['rect'], True, 4.0)
bbv6 = {k.split(':')[1]: (v[2]-v[0], v[3]-v[1]) for k, v in json.load(open(ROOT+'/scratch/chip-assembly-v6/bbox.json')).items()}
ledger_area = {k: v[1] for k, v in fp['items'].items()}
def want_size(n):
    m = item_master.get(n, n)
    if m in staged and 'w' in staged[m]: return staged[m]['w'], staged[m]['h']
    if m in bbv6: return bbv6[m]
    s = ledger_area.get(n, 0)**0.5
    return (s, s) if s else None
overflow, left_out = {}, []
# RF / oscillator blocks first (the fill keep-out study needs them in the skeleton), then real conn blocks by area, reservations last
PRIO = ['pll_tx', 'pll_cdr', 'lo_mmd', 'term_buffer']
for n in sorted(unplaced, key=lambda n: (PRIO.index(n) if n in PRIO else 99, n not in inst, -(ledger_area.get(n, 0)))):
    sz = want_size(n); done = False
    if sz:
        for rot in (False, True):
            w, h = (sz[1], sz[0]) if rot else sz
            cw, ch = int(-(-(w+8)//G)), int(-(-(h+8)//G))
            free = (~occ).astype(np.int32)
            S = np.zeros((NX+1, NY+1), np.int32); S[1:, 1:] = free.cumsum(0).cumsum(1)
            if cw >= NX or ch >= NY: continue
            tot = S[cw:, ch:]-S[:-cw, ch:]-S[cw:, :-ch]+S[:-cw, :-ch]
            ok = np.argwhere(tot == cw*ch)
            if len(ok):
                i, j = ok[0]; x, y = i*G+4, j*G+4
                overflow[n] = dict(rect=[x, y, round(x+w, 3), round(y+h, 3)], rot=rot, grp='overflow')
                mark(overflow[n]['rect'], True, 4.0); done = True; break
    if not done: left_out.append(n)
def hit(a, b): return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
dropped_decap = [n for n, v in rects.items() if n.startswith(('decap_bank', 'decap_tile')) and any(hit(v['rect'], o['rect']) for o in overflow.values())]
for n in dropped_decap: del rects[n]
rects.update(overflow)

plan = dict(die=[0, 0, 3932.0, 5122.0], core=list(CORE), blocks=[], pads=[], left_out=left_out, dropped_decap=dropped_decap,
            overflow=sorted(overflow), ports=sorted(ports))
for n, v in rects.items():
    m = 'decap' if n.startswith(('decap_bank', 'decap_tile')) else item_master.get(n, n)
    if m == '(booked)': m = n
    plan['blocks'].append(dict(name=n, master=m, rect=v['rect'], rot=v.get('rot', False), in_conn=n in inst,
                               cands=candidates(m), pins=pins_of(m)))
plan['blocks'].append(dict(name='digital', master='pt_digital_macro', rect=fp['fixed']['digital'], rot=False, in_conn=True,
                           cands=candidates('pt_digital_macro'), pins=[]))
for n, r in fp['fixed'].items():
    if n != 'digital': plan['blocks'].append(dict(name=n, master=n, rect=r, rot=False, in_conn=False, cands=[], pins=[], reserve=True))
for n, rs in fp['pads'].items():
    m = item_master.get(n)
    plan['pads'].append(dict(name=n, master=m, rects=rs, edge='west' if rs[0][0] < 1000 else 'east', cands=candidates(m), pins=pins_of(m),
                             in_conn=n in inst))
plan['conn_not_in_floorplan'] = sorted(n for n in inst if n not in rects and n not in fp['pads'] and n != 'digital'
                                       and not item_master.get(n, '').startswith(('prov_', 'pad_', 'pt_host', 'pt_debug', 'atb_provider')))
os.makedirs(RUN+'/skel', exist_ok=True)
json.dump(plan, open(RUN+'/skel/plan.json', 'w'), indent=0)
print(f"blocks {len(plan['blocks'])} (overflow placed {len(overflow)}: {sorted(overflow)}), pads {len(plan['pads'])}")
print('left out (no room):', left_out)
print('decap bank tiles given up:', len(dropped_decap))
print('conn instances with no floorplan entry:', plan['conn_not_in_floorplan'])
print('no GDS candidate:', sorted({b['master'] for b in plan['blocks'] if not b['cands'] and not b.get('reserve')}))
