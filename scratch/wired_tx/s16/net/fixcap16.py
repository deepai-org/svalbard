"""s16 capacitance repair of the Magic extresist netlist (supersedes s14/chain/fixcap.py for this flow).

Reference: the C-only extraction of the SAME flattened GDS in the same Magic run setup (xk/conly: extract with
capacitance + coupling, no resistance, ext2spice cthresh 0).  Both runs read identical .ext cap records (25864).
Two artifacts of `ext2spice extresist on` are repaired:
  1. ground C over-count (s14 finding, WT42): for a resisted net the root's lumped substrate cap AND the extresist
     sub-node caps are written.  s14's fixcap.py scaled only the '**FLOATING'-tagged caps; for port nets (MAIN_CODE*, D*,
     MAIN_P/N, POST_*, TX_RUN, IBIAS ...) the root's cap is written to VSS WITHOUT the tag (e.g. MAIN_CODE5 73.2 fF
     untagged + 40.9 fF tagged vs 14.13 fF in the .ext node record), so those nets kept up to 5x their ground C.
     Here: per net (base name, .tN/.nN and '#' stripped) every cap to VSS (tagged or not) on the root and its sub-nodes
     is scaled so the sum equals the C-only netlist's ground C of that net.
  2. dropped coupling caps (found 2026-11-20 in s16): ext2spice extresist omits coupling caps to unnamed nets written
     with a trailing '#' (6424 pairs, 1.28 pF, e.g. OVN - a_51268_56632# 24.9 fF, XMUX.ENMI pairs 25 fF).  Each pair
     present in the C-only netlist and absent here is added between the two nets' root nodes (lumped at the root;
     the RC position of these caps is approximate).
Resistors and the coupling caps that ext2spice did write are unchanged.
usage: fixcap16.py <conly.spice> <in.full.rc.spice> <out.spice>"""
import re, sys
from collections import defaultdict
ref, src, dst = sys.argv[1:4]


def v(s):
    m = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'a': 1e-18}
    s = s.lower()
    return float(s[:-1]) * m[s[-1]] if s[-1] in m else float(s)


B = lambda n: re.sub(r'\.(t|n)\d+$', '', n).rstrip('#').replace('/', '.')
G = ('VSS', 'VSUBS', '0')
# reference: per-net ground C and pair coupling
rg = defaultdict(float); rp = defaultdict(float)
for l in open(ref):
    if not l.startswith('C'):
        continue
    t = l.split(); a, b = B(t[1]), B(t[2]); x = v(t[3])
    if a == b:
        continue
    if b in G or 'FLOATING' in l:
        rg[a] += x
    elif a in G:
        rg[b] += x
    else:
        rp[tuple(sorted((a, b)))] += x
L = open(src).read().split('\n')
tok = defaultdict(set); gidx = []; fg = defaultdict(float); fp = set(); end = None
for i, l in enumerate(L):
    p = l.split()
    if not p:
        continue
    if p[0].lower().startswith('.ends'):
        end = i
    if p[0][0] in 'XRCD' and len(p) > 2:
        nn = p[1:5] if p[0][0] == 'X' else p[1:3]
        for n in nn:
            tok[B(n)].add(n)
    if l.startswith('C'):
        a, b = B(p[1]), B(p[2])
        if b in G or a in G or 'FLOATING' in l:
            n = a if a not in G else b
            gidx.append((i, n)); fg[n] += v(p[3])
        else:
            fp.add(tuple(sorted((a, b))))


def root(n):
    ts = tok.get(n, ())
    for t in ts:
        if B(t) == n and t.rstrip('#') == t.replace('/', '.') and not re.search(r'\.(t|n)\d+$', t):
            return t
    for t in sorted(ts):
        if t.endswith('.n0'):
            return t
    return sorted(ts)[0] if ts else None


b0 = sum(fg.values()); a0 = 0; nomatch = 0
for i, n in gidx:
    p = L[i].split()
    k = rg[n] / fg[n] if fg[n] > 0 and n in rg else (0.0 if n not in rg else 1.0)
    if n not in rg:
        nomatch += 1
    c = v(p[3]) * k; a0 += c
    a_, b_ = p[1], p[2]
    L[i] = f'{p[0]} {a_} {b_} {c:.6g}'
add = []; miss_tok = 0; addc = 0.0
for (a, b), x in rp.items():
    if (a, b) in fp:
        continue
    ra, rb = root(a), root(b)
    if ra is None or rb is None:
        miss_tok += 1; continue
    add.append(f'CX{len(add)} {ra} {rb} {x:.6g}'); addc += x
L = L[:end] + add + L[end:]
# ground caps for nets that have reference ground C but no ground cap in the full netlist
noground = 0
for n, x in rg.items():
    if n not in fg and n not in G and root(n):
        L.insert(end, f'CGX{noground} {root(n)} VSS {x:.6g}'); noground += 1
open(dst, 'w').write('\n'.join(L))
print(f'ground C {b0 * 1e12:.3f} pF -> {a0 * 1e12:.3f} pF (ref {sum(rg.values()) * 1e12:.3f}); ground caps without ref net {nomatch}; '
      f'nets given a ground cap {noground}; coupling pairs added {len(add)} = {addc * 1e12:.3f} pF; pairs without a node {miss_tok}')
