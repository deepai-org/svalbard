"""Variants of the extracted pt_pll_ring for the r12 duty / spacing study (devices added inside the extracted sub-cells,
new devices without their own wiring parasitics: exploration only, the chosen variant is laid out and re-extracted).
  patch.py OUT XC=n/p [ENB0=1]
XC=n/p : cross-coupled inverter pair between the complementary phase-buffer nodes M_k / M_{k+4} of ct_phbuf8 (each
         direction one inverter, NMOS n um / PMOS p um)
XA=n/p : the same between the restore nodes A_k / A_{k+4} of ct_ring9
ENB0=1 : stage-0 N1 clamp gate back on ENB (symmetric ring, the pre-e7b4d14 cell)"""
import sys, re
from pathlib import Path
out = Path(sys.argv[1]); opt = dict(a.split('=') for a in sys.argv[2:])
SRC = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing/generated/' + opt.pop('SRC', 'pll_ring') + '.ext.spice')
t = SRC.read_text()


def add(sub, lines):
    global t
    i = t.index(f'.subckt {sub} '); j = t.index('\n.ends', i)
    t = t[:j] + '\n' + '\n'.join(lines) + t[j:]


def pair(node, tag, wn, wp):
    L = []
    for k in range(4):
        for a, b in ((k, k + 4), (k + 4, k)):
            L += [f'X{tag}{a}{b}n {node}{b} {node}{a} VSS VSS nfet_03v3 w={wn}u l=0.28u',
                  f'X{tag}{a}{b}p {node}{b} {node}{a} VDD VDD pfet_03v3 w={wp}u l=0.28u']
    return L


if 'XC' in opt:
    wn, wp = opt['XC'].split('/'); add('ct_phbuf8', pair('M', 'xc', wn, wp))
if 'XA' in opt:
    wn, wp = opt['XA'].split('/'); add('ct_ring9', pair('A', 'xa', wn, wp))
if opt.get('ENB0') == '1':
    i = t.index('.subckt ct_ring9 '); j = t.index('\n.ends', i); s = t[i:j]
    # the 0.5u clamp on N1 whose gate is P1
    s = re.sub(r'^(X\S+) N1 P1 VSS VSS nfet_03v3 (.*w=0.5u.*)$', r'\1 N1 ENB VSS VSS nfet_03v3 \2', s, flags=re.M)
    t = t[:i] + s + t[j:]


def capsum(sub):
    i = t.index(f'.subckt {sub} '); j = t.index('\n.ends', i); s = t[i:j].replace('\n+', ' ')
    c = {}
    for l in s.splitlines():
        p = l.split()
        if p and p[0][0] in 'Cc' and len(p) >= 4:
            m = re.match(r'([\d.eE+-]+)([fpa]?)', p[3]); x = float(m.group(1)) * {'f': 1, 'p': 1e3, 'a': 1e-3, '': 1e15}[m.group(2)]
            for q in p[1:3]: c[q] = c.get(q, 0) + x
    return c, s


if opt.get('EQ'):
    # equalise wiring C: ring nodes P/N (in ct_ring9) to the largest, ring outputs O_k (cell + top route) to the largest,
    # PH ports (top) to the largest; groups selectable: EQ=pn,o,ph
    grp = opt['EQ'].split(',')
    top = 'pt_pll_ring_core' if '.subckt pt_pll_ring_core ' in t else 'pt_pll_ring'
    cr, _ = capsum('ct_ring9'); ct, st = capsum(top)
    xr = [l for l in st.splitlines() if l.split() and l.split()[-1] == 'ct_ring9'][0].split()
    xp = [l for l in st.splitlines() if l.split() and l.split()[-1] == 'ct_phbuf8'][0].split()
    if 'pn' in grp:
        nodes = ['P0', 'N0', 'P1', 'N1', 'P2', 'N2', 'P3', 'N3']; mx = max(cr[n] for n in nodes)
        add('ct_ring9', [f'Ceq{n} {n} VSS {mx - cr[n]:.3f}f' for n in nodes if mx - cr[n] > 0.01])
    if 'o' in grp:
        tot = {k: cr.get(f'O{k}', 0) + ct.get(xr[1 + k], 0) for k in range(8)}; mx = max(tot.values())
        add(top, [f'Ceqo{k} {xr[1 + k]} VSS {mx - tot[k]:.3f}f' for k in range(8) if mx - tot[k] > 0.01])
    if 'ph' in grp:
        ph = xp[9:17]; mx = max(ct.get(q, 0) for q in ph)
        add(top, [f'Ceqph{k} {q} VSS {mx - ct.get(q, 0):.3f}f' for k, q in enumerate(ph) if mx - ct.get(q, 0) > 0.01])
out.write_text(t)
print(out, opt)
