"""s16 netlist check: fullfix (Magic extresist + fixcap) vs the drawn netlist and the C-only extraction of the same GDS.
usage: python3 check16.py  -> prints a summary and writes check16.json"""
import re, json
from collections import Counter, defaultdict
from pathlib import Path
H = Path(__file__).resolve().parent
FULL = H / 'pt_wiredtx8.fullfix16.rc.spice'; RAW = H / 'pt_wiredtx8.full.rc.spice'
CONLY = H / 'pt_wiredtx8.conlyflat.spice'; CGEN = H / 'pt_wiredtx8.ext.spice'; DRAWN = H / 'pt_wiredtx8.spice'
LOG = H.parent / 'xk' / 'pt_wiredtx8' / 'rc.log'


def v(s):
    m = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'a': 1e-18, 'u': 1e-6, 'm': 1e-3, 'k': 1e3}
    s = s.lower()
    return float(s[:-1]) * m[s[-1]] if s[-1] in m else float(s)


def lines(p):
    out = []
    for l in Path(p).read_text().split('\n'):
        if l.startswith('+') and out:
            out[-1] += ' ' + l[1:]
        else:
            out.append(l)
    return out


def ports(p, cell='pt_wiredtx8'):
    for l in lines(p):
        if l.lower().startswith('.subckt ') and l.split()[1] == cell:
            return [x for x in l.split()[2:] if '=' not in x]


def stats(p):
    c = Counter(); ctot = csub = ccpl = 0.0; rnets = set(); nets = set()
    for l in lines(p):
        if not l or l[0] in '*.':
            continue
        k = l[0].upper(); c[k] += 1; t = l.split()
        if k == 'C':
            x = v(t[3]); ctot += x
            if 'FLOATING' in l or t[2] in ('VSS', 'VSUBS', '0') or t[1] in ('VSS', 'VSUBS', '0'):
                csub += x
            else:
                ccpl += x
        if k == 'R':
            for n in t[1:3]:
                rnets.add(re.sub(r'\.(t|n)\d+$', '', n).rstrip('#'))
    return dict(counts=dict(c), c_total_pf=round(ctot * 1e12, 3), c_to_gnd_pf=round(csub * 1e12, 3), c_other_pf=round(ccpl * 1e12, 3),
                nets_with_r=len(rnets), rnets=rnets)


pf, pd, pc = ports(FULL), ports(DRAWN), ports(CONLY)
sf, sc, sr, sg = stats(FULL), stats(CONLY), stats(RAW), stats(CGEN)
grp = defaultdict(int)
for n in sf.pop('rnets'):
    grp[n.split('.')[0] if '.' in n else 'top'] += 1
sc.pop('rnets'); sr.pop('rnets'); sg.pop('rnets')
cov = [l.strip() for l in LOG.read_text().split('\n') if l.startswith('Nets ')] if LOG.exists() else []
res = dict(ports_full=len(pf), ports_drawn=len(pd), ports_conly=len(pc), port_names_order_equal=(pf == pd == pc),
           full=sf, conly_flat_same_run=sc, conly_generator=sg, c_total_ratio_full_vs_generator=round(sf['c_total_pf'] / sg['c_total_pf'], 4), raw_before_fixcap=sr, nets_with_r_by_inst=dict(grp), magic_coverage=cov,
           c_total_ratio_full_vs_conly=round(sf['c_total_pf'] / sc['c_total_pf'], 4),
           c_gnd_ratio_full_vs_conly=round(sf['c_to_gnd_pf'] / sc['c_to_gnd_pf'], 4))
(H / 'check16.json').write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
