"""Supply-current split of the flat block netlist (PDS-14).  Every MOSFET whose drain or source is VDD gets that terminal on
VDD_<group> with a 0 V ammeter VAM_<group> from VDD inside the subckt (bulk stays on VDD).  Group of a device = group of
its non-supply drain/source net: name prefix XSER. -> ser, XMUX. -> mux (mux_main / mux_post when the net name carries the
MAIN / POST bank marker M / Q: BM, ENBM, XTM, ... / BQ, ENBQ, XTQ, ...), XAUX. -> aux, PS k -> phbuf, MAIN_* / POST_* -> mux;
unnamed nets take the majority group of the devices whose gates they drive (iterated).  Caps to VDD, decap devices and bulk
currents are not assigned: block remainder = i(VDD total) - sum of the groups.
"""
import re
from collections import Counter, defaultdict

B = lambda n: re.sub(r'\.(t|n)\d+$', '', n).rstrip('#')
SUP = {'VDD', 'VSS'}
MAINQ = re.compile(r'^XMUX\.(?:[A-Z]*?)(M|Q)\d*$')


def named(n):
    b = B(n)
    if b.startswith('XSER.'):
        return 'ser'
    if b.startswith('XAUX.'):
        return 'aux'
    if b.startswith('XMUX.'):
        m = MAINQ.match(b)
        return {'M': 'mux_main', 'Q': 'mux_post'}[m.group(1)] if m and b.split('.')[1] not in ('ENMI',) else 'mux'
    if re.fullmatch(r'PS\d', b):
        return 'phbuf'
    if re.fullmatch(r'(MAIN|POST)_[PN]', b):
        return 'mux'
    return None


def split(text):
    L = text.split('\n')
    dev = []
    for i, l in enumerate(L):
        p = l.split()
        if p and p[0][0] == 'X' and len(p) > 5 and ('fet' in p[5]):
            dev.append((i, p))
    grp = {}
    gates = defaultdict(list)       # net -> device indices it gates
    for k, (i, p) in enumerate(dev):
        for n in (p[1], p[2], p[3]):
            b = B(n)
            if b not in grp and named(n):
                grp[b] = named(n)
        gates[B(p[2])].append(k)

    def dgroup(p):
        for n in (p[1], p[3]):
            if B(n) not in SUP and grp.get(B(n)):
                return grp[B(n)]
        return None
    for _ in range(30):
        ch = 0
        for net, ks in gates.items():
            if net in grp or net in SUP:
                continue
            c = Counter(g for g in (dgroup(dev[k][1]) for k in ks) if g)
            if c:
                grp[net] = c.most_common(1)[0][0]; ch += 1
        for i, p in dev:                     # a device with a known group gives it to its unnamed d/s nets
            g = dgroup(p)
            if g:
                for n in (p[1], p[3]):
                    if B(n) not in SUP and B(n) not in grp:
                        grp[B(n)] = g; ch += 1
        if not ch:
            break
    used = Counter()
    for i, p in dev:
        g = dgroup(p)
        if g and ('VDD' in (p[1], p[3])):
            if p[1] == 'VDD':
                p[1] = f'VDD_{g}'
            if p[3] == 'VDD':
                p[3] = f'VDD_{g}'
            L[i] = ' '.join(p); used[g] += 1
        elif 'VDD' in (p[1], p[3]):
            used['unassigned'] += 1
    end = max(i for i, l in enumerate(L) if l.lower().startswith('.ends'))
    L[end:end] = [f'VAM_{g} VDD VDD_{g} 0' for g in used if g != 'unassigned']
    return '\n'.join(L), dict(used)
