"""Chip-grid supply entry on the R+C ptrim netlist: for every grid strap crossing ptrim's Metal4 supply straps, a via4 landing
from the nearest extracted strap node (Magic extresist rnode coordinates, .res.ext) to the block supply pin (= the ideal grid).
usage: grid.py RC.spice RES.ext OUT.spice VSS=y1,y2,.. VDD_WIRE_SW=y1,.. [w=10.5] [toppin=1]
  y: grid strap centre (um, ptrim frame); w: grid strap width -> via4 array over the 5 um x w overlap: cuts at 0.52 um pitch,
  4.5 ohm per cut (typical, extraction value) -> R_land = 4.5 / ncuts.  toppin=0 also removes the block's own top pin feed
  (strap reached only through the grid landings)."""
import re, sys, json
rc, rx, out = sys.argv[1:4]; o = dict(a.split('=', 1) for a in sys.argv[4:])
w = float(o.get('w', 10.5)); X = dict(VSS=189.2, VDD_WIRE_SW=196.2)
ncut = int(4.6 / 0.52) * int((w - 0.4) / 0.52); Rl = 4.5 / ncut
nodes = {}
for l in open(rx):
    m = re.match(r'rnode "(\S+)" \S+ \S+ (-?\d+) (-?\d+)', l)
    if m: nodes[m.group(1)] = (int(m.group(2)) * 0.005, int(m.group(3)) * 0.005)
txt = open(rc).read(); have = set(re.findall(r'\b((?:VSS|VDD_WIRE_SW)\.[nt]\d+)\b', txt))
add, rep = [], {}
for net in ('VSS', 'VDD_WIRE_SW'):
    for y in [float(v) for v in o.get(net, '').split(',') if v]:
        c = [(abs(p[1] - y), n) for n, p in nodes.items() if (n == net or n.startswith(net + '.')) and abs(p[0] - X[net]) < 2.6 and (n == net or n in have)]
        d, n = min(c); add.append(f'RGRID_{net}_{int(y)} {n} {net} {Rl:.4g}'); rep[f'{net}@{y}'] = dict(node=n, dy_um=round(d, 2))
lines = txt.rstrip().splitlines(); i = max(j for j, l in enumerate(lines) if l.lower().startswith('.ends'))
lines[i:i] = add
open(out, 'w').write('\n'.join(lines) + '\n'); print(json.dumps(dict(R_land_ohm=round(Rl, 4), cuts=ncut, landings=rep)))
