#!/usr/bin/env python3
"""R-aware simulation model of pad_hspad = the Magic C-only model (physical.spice) + the netres.py reduced resistor networks.

    make_rmodel.py <physical.spice> <netres main json> <netres TU json> <typ|high> <out.spice>

Inserted (exact reduced terminal networks from netres.py, one resistor per terminal pair):
  TERM_VCM  pin (port node) <-> the 50 switch sources, each on its own node
  PAD_P/N   bond pad (port node) <-> feed <-> MIM bottom plates <-> the 25 resistor heads (own nodes) <-> the 12 ESD diode
            terminals (tied together: one node `PAD_x__dio`)
  TU nets   one series resistor per unit between the resistor's TU terminal and the switch drain
  RX_P/N    pin (port node) <-> MIM top plates <-> RB / clamp terminals (tied together)
Parasitic capacitors stay on the port nodes. Unit index: the 25 TU nets of a leg sorted by the x of their `a_X_Y#` name;
checked against the gate sequence (10 x TERM_ENABLE, 1/2/4/8 x TERM_TRIM0..3). Not modelled: VSS / VDD / VBIAS / gate-line metal."""
import json, re, sys
src, fmain, ftu, corner, out = sys.argv[1:6]
main = json.load(open(fmain))['nets']; tu = json.load(open(ftu))['nets']
txt = re.sub(r'\n\+\s*', ' ', open(src).read()).splitlines()
MID = 615.75
i0 = next(i for i, l in enumerate(txt) if l.startswith('.subckt pad_hspad_flat')); i1 = next(i for i in range(i0, len(txt)) if txt[i].startswith('.ends'))
body = [l.split() for l in txt[i0 + 1:i1]]
model = lambda t: [w for w in t if '=' not in w][-1]
anchor = lambda n: (lambda m: (int(m[1]) * .005, int(m[2]) * .005) if m else None)(re.fullmatch(r'a_(\d+)_(\d+)#', n))
# --- units: switch (TU, gate, TERM_VCM), resistor (PAD, TU)
sw = {}
for t in body:
    if t[0][0] == 'X' and model(t) == 'nfet_06v0' and 'TERM_VCM' in (t[1], t[3]) and t[2].startswith('TERM_'):
        tun = t[1] if t[3] == 'TERM_VCM' else t[3]; sw[tun] = t
assert len(sw) == 50, len(sw)
unit = {}
GSEQ = ['TERM_ENABLE'] * 10 + [f'TERM_TRIM{k}' for k in range(4) for _ in range(1 << k)]
for leg in 'PN':
    nets = sorted((n for n in sw if (anchor(n)[1] < MID) == (leg == 'P')), key=lambda n: anchor(n)[0])
    assert [sw[n][2] for n in nets] == GSEQ, f'unit order check failed in leg {leg}'
    for k, n in enumerate(nets): unit[n] = (leg, k)
extra = []; nres = 0
def network(net, node):
    """insert the reduced network of `net`; node(term) -> node name"""
    global nres
    for a, b, r in main[net]['corners'][corner]['reduced_network']:
        na, nb = node(a), node(b)
        if na != nb and r < 1e8: extra.append(f'RNR{nres} {na} {nb} {r:.6g}'); nres += 1
def by_x(net, prefix, leg):
    t = main[net]['terminals']
    names = [n for n in t if n.startswith(prefix) and n[len(prefix):].isdigit() and (leg is None or (t[n]['y'] < MID) == (leg == 'P'))]
    return sorted(names, key=lambda n: t[n]['x'])
srcname = {}
for leg in 'PN':
    names = by_x('TERM_VCM', 'src', leg); assert len(names) == 25
    for k, n in enumerate(names): srcname[n] = f'TERM_VCM__{leg}{k}'
network('TERM_VCM', lambda t: 'TERM_VCM' if t == 'pin' else srcname[t])
hd = {}
for leg in 'PN':
    net = f'PAD_{leg}'; names = by_x(net, 'hd', None); assert len(names) == 25, len(names)
    hd[leg] = {n: f'{net}__h{k}' for k, n in enumerate(names)}
    network(net, lambda t, net=net, leg=leg: net if t == 'bond' else f'{net}__dio' if t.startswith('dio') else hd[leg][t] if t in hd[leg] else f'{net}__{t}')
    rx = f'RX_{leg}'
    network(rx, lambda t, rx=rx: rx if t == 'pin' else f'{rx}__dev' if t.startswith('dev') else f'{rx}__{t}')
# --- rewrite the devices
cnt = dict(sw=0, res=0, mim=0, dio=0, rxdev=0)
for t in body:
    if t[0][0] not in 'XD': continue
    m = model(t); nterm = len([w for w in t[1:] if '=' not in w]) - 1
    if t[0][0] == 'X' and m == 'nfet_06v0' and (t[1] in sw or t[3] in sw) and 'TERM_VCM' in (t[1], t[3]):
        tun = t[1] if t[3] == 'TERM_VCM' else t[3]; leg, k = unit[tun]
        t[1 if t[1] == 'TERM_VCM' else 3] = f'TERM_VCM__{leg}{k}'; cnt['sw'] += 1
    elif m == 'ppolyf_u' and any(p in t[1:3] for p in ('PAD_P', 'PAD_N')):
        i = 1 if t[1] in ('PAD_P', 'PAD_N') else 2; tun = t[3 - i]; leg, k = unit[tun]
        assert t[i] == f'PAD_{leg}'
        t[i] = f'PAD_{leg}__h{k}'; t[3 - i] = f'{tun[:-1]}_r#'
        r = tu[f'TU{k}_{leg}']['corners'][corner]['resistance_ohm']['a|b']
        extra.append(f'RTU{leg}{k} {tun[:-1]}_r# {tun} {r:.6g}'); cnt['res'] += 1
    elif m.startswith('cap_mim') and any(p in t[1:3] for p in ('PAD_P', 'PAD_N')):
        for i in (1, 2):
            if t[i] in ('PAD_P', 'PAD_N', 'RX_P', 'RX_N'): t[i] += '__mim'
        cnt['mim'] += 1
    elif m.startswith('diode') and any(p in t[1:3] for p in ('PAD_P', 'PAD_N')):
        for i in (1, 2):
            if t[i] in ('PAD_P', 'PAD_N'): t[i] += '__dio'
        cnt['dio'] += 1
    elif any(w in ('RX_P', 'RX_N') for w in t[1:1 + nterm]):
        for i in range(1, 1 + nterm):
            if t[i] in ('RX_P', 'RX_N'): t[i] += '__dev'
        cnt['rxdev'] += 1
    elif any(w in ('PAD_P', 'PAD_N') for w in t[1:1 + nterm]):
        raise SystemExit('unclassified device on a PAD net: ' + ' '.join(t))
assert cnt == dict(sw=50, res=50, mim=4, dio=24, rxdev=6), cnt
new = txt[:i0 + 1] + [' '.join(t) for t in body] + [f'* netres.py resistances ({corner} metal): {len(extra)} resistors, {fmain} {ftu}'] + extra + txt[i1:]
open(out, 'w').write('\n'.join(new) + '\n')
print(out, cnt, 'resistors', len(extra))
