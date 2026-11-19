#!/usr/bin/env python3
"""Resistance-aware view of pt_lna for the nets that carry the stage's DC current (round 3).

Magic `extresist` (C-only flow + extresist) breaks the meshes of this layout into trees: on the per-strip-tap layout it put the
whole 16 mA tail current through one 3.9 ohm branch that has ~100 parallel taps in the drawing.  So the metal resistance of the
current-carrying nets is solved here with the pads owner's mesh solver (scratch/pads-core/hsfix/netres.py, read only: finite-volume
Metal1..5 mesh, one resistor per via cut, contact resistance not modelled) and inserted into the C-only extracted netlist:

  python3 lna_netres.py spec      writes scratch/rf_rx/netres/spec.json from the layout placement (same build as generate_lna)
  python3 lna_netres.py solve     runs netres.py in the analog image -> scratch/rf_rx/netres/res.json
  python3 lna_netres.py netlist   writes generated/lna.rext.spice: generated/lna.ext.spice with every heavy-device terminal on its own
                                  node and the solved reduced network (port / device-group terminals) between them

Terminal groups: all S/D contact strips of one terminal of one heavy device (lna_layout.heavy) are shorted (one terminal); ports are
the M3 port labels.  Light devices on these nets stay on the original node, which is the port (or, for internal nets, the first
group).  Corner 'typ' sheet / via resistance of the Magic tech (90 mohm/sq Metal1-4, 4.5 ohm per via cut)."""
import sys, json, re, subprocess
from pathlib import Path
import rfrx_flow as F
import lna_layout as LL

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
W = REPO / 'scratch' / 'rf_rx' / 'netres'
NETS = ('VDD', 'VSS', 'vtk', 'tail', 'tailx', 'src_p', 'src_n', 'x_p', 'x_n', 'tank_p', 'tank_n')
LL.WIDE = LL.WIDE_LNA      # the LNA routing (build_compact sets it per cell; this module only builds pt_lna)
NETRES = REPO / 'scratch' / 'pads-core' / 'hsfix' / 'netres.py'


def placement():
    work = REPO / 'scratch' / 'rf_rx' / 'layout' / 'lna'          # the generate_lna build directory (primitive .mag cells)
    LL.WIDE = LL.WIDE_LNA
    subs = F.parse_spice(HERE / 'lna.spice')
    devs, ports = LL.flatten(subs, 'pt_lna')
    geoms = F.build_primitives(work, devs)
    for d in devs:
        if LL.heavy(d) and d.nf > 1:
            geoms[(F.prim_key(d), d.name)] = LL.heavy_geom(work, d, geoms[F.prim_key(d)])
    L = LL.build(devs, geoms, ports, LL.LNA_ROW_WIDTH)
    xo = L.x0
    out = []
    for r in L.rows:
        for (d, g), ox0 in zip(r['items'], r['pos']):
            if not LL.heavy(d):
                continue
            ox, oy = F._snap(xo + ox0), F._snap(r['y_dev'] - g['fp'][1])
            rr = F._rects(work / (F.prim_key(d) + '.mag'))
            diff = next(k for k in ('ndiffc', 'pdiffc', 'mvndiffc', 'mvpdiffc') if k in rr)
            strips = sorted(rr[diff], key=lambda a: a[0])
            if d.nf == 1:
                sd = {0: [max(strips, key=lambda a: a[2])], 2: [min(strips, key=lambda a: a[0])]}
            else:
                sd = {0: [a for i, a in enumerate(strips) if i % 2 == 1], 2: [a for i, a in enumerate(strips) if i % 2 == 0]}
            for ti, ss in sd.items():
                out.append(dict(dev=d.name, term=ti, net=d.nodes[ti], boxes=[[round(ox + a[0], 3), round(oy + a[1], 3), round(ox + a[2], 3), round(oy + a[3], 3)] for a in ss]))
    return out, ports


def spec():
    pl, ports = placement()
    nets = []
    for n in NETS:
        terms = [dict(name=f"{t['dev']}.{'d' if t['term'] == 0 else 's'}", layer='M1', boxes=t['boxes']) for t in pl if t['net'] == n]
        if n in ports:
            terms.insert(0, dict(name='port', at_label=n, half=0.15))
        nets.append(dict(name=n, label=n, max_step=1.0, min_cuts=2, min_width=1.0, terminals=terms))
    W.mkdir(parents=True, exist_ok=True)
    (W / 'spec.json').write_text(json.dumps(dict(nets=nets), indent=1))
    print({x['name']: len(x['terminals']) for x in nets})


def solve():
    gds = HERE / 'generated' / 'lna.gds'
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '--env', 'OMP_NUM_THREADS=1', '--user', '1000:1000',
           '--env', 'HOME=/tmp', '--entrypoint', '/bin/bash',
           '--mount', f'type=bind,src={NETRES.parent},dst=/tool,readonly', '--mount', f'type=bind,src={gds.parent},dst=/gds,readonly',
           '--mount', f'type=bind,src={W},dst=/work', '--workdir', '/work', F.ANALOG_IMAGE,
           '-lc', 'python3 /tool/netres.py --gds /gds/lna.gds --top pt_lna --spec spec.json --out res.json --corner typ,high > netres.log 2>&1; echo rc=$?']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    print(r.stdout[-300:], r.stderr[-500:])


def netlist(corner='typ', src=None, dst=None):
    """C-only extracted netlist with the solved reduced networks inserted.  Extracted fingers are matched to their schematic
    heavy device by (gate net, set of S/D nets, model, L); each finger terminal on a solved net moves to that device's node."""
    res = json.loads((W / 'res.json').read_text())
    rows = res['nets'] if isinstance(res['nets'], dict) else {x['name']: x for x in res['nets']}
    subs = F.parse_spice(HERE / 'lna.spice'); devs, _ = LL.flatten(subs, 'pt_lna')
    key = {d.name: (d.model, d.nodes[1], frozenset((d.nodes[0], d.nodes[2])), round(d.l, 3)) for d in devs if LL.heavy(d)}
    add, node_of = [], {}
    for net in NETS:
        cn = rows[net]['corners'][corner]
        names = sorted({a for a, b, _ in cn['reduced_network']} | {b for a, b, _ in cn['reduced_network']})
        base = 'port' if 'port' in names else names[0]
        node = lambda nm: net if nm == base else f'{net}__{nm.replace(".", "_")}'
        for nm in names:
            if nm != 'port':
                node_of[(nm.rsplit('.', 1)[0], net)] = node(nm)
        add += [f'Rnr_{net}_{i} {node(a)} {node(b)} {rv:.6g}' for i, (a, b, rv) in enumerate(cn['reduced_network'])]
    bykey = {}
    for dn, k in key.items(): bykey.setdefault(k, []).append(dn)
    t = (Path(src) if src else HERE / 'generated' / 'lna.ext.spice').read_text().replace('\n+', ' ')
    out, moved = [], 0
    for l in t.splitlines():
        m = re.match(r'^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(nfet_03v3|pfet_03v3)\s+(.*)$', l)
        if m:
            lval = round(float(re.search(r'\bl=([\d.]+)u', l).group(1)), 3)
            k = (m.group(6), m.group(3), frozenset((m.group(2), m.group(4))), lval)
            if k in bykey:
                assert len(bykey[k]) == 1, k
                dn = bykey[k][0]
                d_, s_ = m.group(2), m.group(4)
                d_ = node_of.get((dn, d_), d_); s_ = node_of.get((dn, s_), s_)
                l = f'{m.group(1)} {d_} {m.group(3)} {s_} {m.group(5)} {m.group(6)} {m.group(7)}'; moved += 1
        out.append(l)
    txt = '\n'.join(out)
    e = txt.index('.ends', txt.index('.subckt pt_lna '))
    txt = txt[:e] + '* reduced metal networks of the current-carrying nets (lna_netres.py, netres.py corner ' + corner + ')\n' + '\n'.join(add) + '\n' + txt[e:]
    dst = Path(dst) if dst else HERE / 'generated' / 'lna.rext.spice'
    dst.write_text(txt + '\n'); print(dst, 'fingers moved', moved, 'resistors', len(add))


if __name__ == '__main__':
    {'spec': spec, 'solve': solve, 'netlist': netlist}[sys.argv[1]]()
