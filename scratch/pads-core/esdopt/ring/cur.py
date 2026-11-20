"""Site-diode current / energy per finger on the bound ring (esd3 deck + savecurrents, as review-a6/esd_rev.py).
usage: python3 cur.py <model> <tag> --case P-N --stim cdm2|hbm2 [--cdie 1n]"""
import sys, json, re, argparse, numpy as np
from pathlib import Path
R = Path(__file__).resolve().parent; sys.path.insert(0, str(R))
import esd3 as E
p = argparse.ArgumentParser(); p.add_argument('model'); p.add_argument('tag'); p.add_argument('--case'); p.add_argument('--stim'); p.add_argument('--cdie')
a = p.parse_args(); E.CDIE = a.cdie; E.RXGATE = True; E.RINGV = (0.155, 0.189, 0.46, 0.57); E.FAR = (5, 7)
body, cell, ports, inner = E.load_model(a.model); devs = E.devices(body, inner)
site = [(n, nodes) for n, m, nodes in devs if m.startswith('diode') and any(re.match(r'PAD_[PN]__(dn|up)$', x) for x in nodes)]
pj = {l.split()[0]: float(re.search(r'pj=([\d.]+)u', l).group(1)) for l in body.splitlines() if l.startswith('D') and 'pj=' in l}
ar = {l.split()[0]: float(re.search(r'area=([\d.]+)p', l).group(1)) for l in body.splitlines() if l.startswith('D') and 'area=' in l}
wave, an = {'cdm2': ('PULSE(0 2 5n 0.2n 0.5n 1n 1)', 'tran .01n 40n uic'), 'hbm2': (f'EXP(0 {2/1.5:.4f} 5n 2n 15n 150n)', 'tran .1n 300n uic')}[a.stim]
d, vec, nodemap = E.deck(body, cell, ports, inner, a.case, wave, an, 'high')
iv = [f'@d.xpad.xphysical.{n.lower()}[id]' for n, _ in site]
d = d.replace('.control\n', '.options savecurrents\n.control\n', 1)
d = d.replace(f'{E.HERE}/esdrun/NAME.dat', f'{R}/esdrun/{a.tag}.dat').replace('wrdata ' + f'{R}/esdrun/{a.tag}.dat ' + ' '.join(vec), 'wrdata ' + f'{R}/esdrun/{a.tag}.dat ' + ' '.join(vec + iv))
assert iv[0] in d
(R / 'esdrun').mkdir(exist_ok=True)
x = E.s.run(R / 'esdrun', a.tag, d, timeout_s=3600)
r = E.analyse(x, vec + iv, nodemap, devs, a.case)
col = {v.lower(): i + 1 for i, v in enumerate(vec + iv)}; t = x[:, 0]
def V(n): return 0 * t if n == '0' else x[:, col[nodemap[n].lower()]]
rows = []
for (n, nodes), v in zip(site, iv):
    i = x[:, col[v.lower()]]; vd = V(nodes[0]) - V(nodes[1])         # anode - cathode; i = anode->cathode
    ipf = float(i.max()); ipr = float(-i.min()); e = float(np.trapezoid(np.abs(vd * i), t))
    ipk = max(ipf, ipr)
    rows.append(dict(d=n, nodes=nodes, i_fwd_pk_ma=round(ipf * 1e3, 1), i_rev_pk_ma=round(ipr * 1e3, 1), v_rev_pk=round(float(-vd.min()), 3),
                     ma_per_um=round(ipk * 1e3 / pj[n], 2), ma_per_um2=round(ipk * 1e3 / ar[n], 2), energy_nj=round(e * 1e9, 3)))
rows.sort(key=lambda c: -c['ma_per_um'])
out = dict(tag=a.tag, case=a.case, stim=a.stim, cdie=a.cdie, ring_ohm=E.RINGV, far=E.FAR, worst_gate=r['worst_mos'].get('gate_v'), diode_rev=r['worst_diode_reverse_v'], site=rows)
(R / 'esd' / f'{a.tag}.json').write_text(json.dumps(out, indent=1))
for c in rows: print(a.tag, c)
(R / 'esdrun' / f'{a.tag}.dat').unlink(missing_ok=True)
