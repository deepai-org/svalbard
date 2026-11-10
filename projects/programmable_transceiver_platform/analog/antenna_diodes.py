"""Shared antenna-diode planner for the Magic trunk/track layout generators.

The transceiver generators (timing/layout_engine, wired_rx, wired_tx, rf_rx, rf_tx, pads) all use
the same house style: device PCells in rows, M3 escapes, M4 channel tracks and one vertical M5
trunk per net in a trunk bank.  A net whose only block-local terminals are MOS gates collects all
of that M4/M5 perimeter on a thin gate oxide, which the KLayout gf180mcu antenna deck
(ANT.16_i_ANT.3..6: perimeter*thickness / (gate + 2*diode) < 400) flags.  The fix is a reverse-
biased N+/Psub diode (diode_nd2ps_03v3) on the net, dropped under the net's own trunk with a via
stack up to the trunk layer.

  plan(requests, painted, keepouts) -> (magic_cmds, placed)

`requests`: [dict(net, x, ylo, yhi, layer, area)] -- x/y range of the net's own top-layer wire
  (layer = 'metal4' or 'metal5'), `area` = diode area in um^2.
`painted`: [(magic_layer, x1, y1, x2, y2)] already drawn (metal1..5, via1..4 ...), used as
  obstacles for the lower stack layers.  The net's own top-layer wire is the landing.
`keepouts`: [(x1, y1, x2, y2)] PCell/instance bounding boxes (diffusion, wells, implants).

Every placed diode is reported so the caller can add `D<i> <sub> <net> diode_nd2ps_03v3 area= pj=`
to its LVS reference (see `spice_lines`).  This is a DRC-only change: the diode is a ~1 fF
reverse-biased junction to substrate on a gate net.
"""
import math

THICK = {'metal1': .54, 'metal2': .54, 'metal3': .54, 'metal4': .54, 'metal5': .9}
LIMIT = 400.0          # ANT.16_i ratio limit (thin gate, diode multiplier 2)
MARGIN = 0.5           # design target: estimated ratio below MARGIN*LIMIT needs no diode
DIFF_KEEP = 1.2        # diode diffusion to any PCell bbox (implants, wells, guard rings)
METAL_SPACE = 0.32     # stack metal to any foreign metal of the same layer
DIODE_SPACE = 1.0      # diode diffusion to another antenna diode (implants 0.16 each side + NP.2 0.4)
TAP_REACH = 15.0       # DF.14_LV: an NCOMP needs a substrate tap within 20 um; every keepout (guard-
                       # ringed PCell / tapped macro) carries taps, so stay within 15 um of one


def _dist(a, b):
    dx = max(0., b[0] - a[2], a[0] - b[2])
    dy = max(0., b[1] - a[3], a[1] - b[3])
    return math.hypot(dx, dy)


def need_area(perimeter_by_layer, gate_area):
    """Diode area (um^2) that brings every per-layer ratio below MARGIN*LIMIT (0 = none needed)."""
    need = 0.
    for layer, per in perimeter_by_layer.items():
        a = per * THICK.get(layer, .54) / (MARGIN * LIMIT)      # = gate + 2*diode required
        need = max(need, (a - gate_area) / 2)
    return 0. if need <= 0 else max(0.36, round(need * 1.5 + .05, 2))


TAP_GAP = 0.8          # diode COMP edge to its own substrate-tap COMP edge


def _tap(x, y, side, orient):
    """Own P+ substrate tap beside the diode (DF.14_LV: NCOMP within 20 um of a substrate tap).
    Unconnected M1 over it: it only ties the substrate locally, no device, no net of its own."""
    d = side / 2 + TAP_GAP + .3
    tx, ty = {'E': (x + d, y), 'W': (x - d, y), 'N': (x, y + d), 'S': (x, y - d)}[orient]
    return [('psubdiff', tx - .3, ty - .3, tx + .3, ty + .3),     # 0.6 um: its PPLUS >= 0.35 um^2 (PP.8a)
            ('psubdiffcont', tx - .15, ty - .15, tx + .15, ty + .15),
            ('metal1', tx - .2, ty - .2, tx + .2, ty + .2)]


def _stack(x, y, top, side):
    h = side / 2
    # Magic contact area 0.30 (it writes one 0.22 CO cut inside); M1 0.40 encloses it.
    rs = [('ndiode', x - h, y - h, x + h, y + h), ('ndiodec', x - .15, y - .15, x + .15, y + .15),
          ('metal1', x - .2, y - .2, x + .2, y + .2)]
    if top >= 2:
        rs.append(('via1', x - .13, y - .13, x + .13, y + .13))
    for m in range(2, top + 1):
        hh = .22 if m == 5 else .2
        rs.append((f'metal{m}', x - hh, y - hh, x + hh, y + hh))
        if m < top:
            rs.append((f'via{m}', x - .14, y - .14, x + .14, y + .14))
    return rs


def _hit(a, b, gap):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def _points(seg, step):
    """Points along a wire centreline seg = (layer, x1, y1, x2, y2), middle first."""
    layer, x1, y1, x2, y2 = seg
    L = max(abs(x2 - x1), abs(y2 - y1))
    n = max(0, int(L / step))
    out = []
    for k in sorted(range(n + 1), key=lambda k: abs(k - n / 2)):
        f = k / n if n else .5
        out.append((round(x1 + f * (x2 - x1), 3), round(y1 + f * (y2 - y1), 3)))
    return out


def plan(requests, painted, keepouts, step=0.1, taps=None):
    """requests: [dict(net, area, segs=[(layer, x1, y1, x2, y2), ...])] -- the net's own wire
    centrelines on metal4/metal5 (tried in order) on which the diode's via stack may land.
    `taps`: boxes that contain a P-substrate tap (NMOS guard rings, tapped macros); default keepouts."""
    taps = keepouts if taps is None else taps
    by_layer = {}
    for l, *r in painted:
        by_layer.setdefault(l, []).append(tuple(r))
    placed_diff, cmds, placed = [], [], []
    for rq in requests:
        side = max(0.6, round(math.sqrt(rq['area']) + .005, 2))
        done = None
        for seg in rq['segs']:
            top = int(seg[0][-1])
            for x, y in _points(seg, step):
              for orient in ('E', 'W', 'N', 'S'):
                stack = _stack(x, y, top, side) + _tap(x, y, side, orient)
                ok = True
                for l, *r in stack:
                    r = tuple(r)
                    if l in ('ndiode', 'psubdiff'):
                        if any(_hit(r, ko, DIFF_KEEP) for ko in keepouts) or \
                           any(_hit(r, d, DIODE_SPACE) for d in placed_diff + by_layer.get('ndiode', [])):
                            ok = False
                            break
                    elif l[-1].isdigit() and int(l[-1]) < top and l.startswith(('metal', 'via')):
                        gap = METAL_SPACE if l.startswith('metal') else .3
                        if any(_hit(r, o, gap) for o in by_layer.get(l, [])):
                            ok = False
                            break
                if ok:
                    done = (x, y, top, stack)
                    break
              if done:
                  break
            if done:
                break
        if done is None:
            placed.append(dict(net=rq['net'], placed=False, area_wanted=rq['area']))
            continue
        x, y, top, stack = done
        for l, *r in stack:
            by_layer.setdefault(l, []).append(tuple(r))
            cmds += [f'box values {r[0]:.3f} {r[1]:.3f} {r[2]:.3f} {r[3]:.3f}', f'paint {l}']
        placed_diff += [tuple(r_[1:]) for r_ in stack if r_[0] in ('ndiode', 'psubdiff')]
        placed.append(dict(net=rq['net'], placed=True, x=x, y=y, top=f'metal{top}', side=side,
                           area=round(side * side, 4), pj=round(4 * side, 4)))
    return cmds, placed


def _touch(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _inside(pt, r):
    return r[0] - 1e-6 <= pt[0] <= r[2] + 1e-6 and r[1] - 1e-6 <= pt[1] <= r[3] + 1e-6


def requests_from_shapes(net_shapes, terminals, landing_min=3):
    """Diode requests from net-tagged rectangles, mirroring how the deck evaluates antennas.

    net_shapes: [(layer, x1, y1, x2, y2, net)] for metal1..5 / via1..4 drawn by the generator.
    terminals:  [(x, y, net, kind, gate_area_um2)] device pin landings (on metal1), kind 'g' for a
                thin-oxide gate, 'sd' for diffusion (protects the net), 'x' ignored.
    For each metal level N the deck sees the partial net built from metal<=N and via<N only (a row's
    Metal4 track before the Metal5 trunk exists), so the ratio is evaluated per such component.
    A component above MARGIN*LIMIT without diffusion gets a diode landing on its own metal N."""
    by_net = {}
    for s in net_shapes:
        if s[5] is not None and s[0][:5] in ('metal', 'via1', 'via2', 'via3', 'via4'):
            by_net.setdefault(s[5], []).append(s)
    terms = {}
    for x, y, net, kind, ga in terminals:
        terms.setdefault(net, []).append((x, y, kind, ga))
    out = []
    for net, shapes in sorted(by_net.items()):
        tl = terms.get(net, [])
        if not any(k == 'g' for *_, k, _ in tl):
            continue
        lvl = [(int(s[0][-1]), s[0].startswith('via')) for s in shapes]
        n = len(shapes)
        adj = [[] for _ in range(n)]
        for i in range(n):
            li, vi = lvl[i]
            for j in range(i + 1, n):
                lj, vj = lvl[j]
                if not _touch(shapes[i][1:5], shapes[j][1:5]):
                    continue
                if (not vi and not vj and li == lj) or (vi and not vj and lj in (li, li + 1)) or \
                   (vj and not vi and li in (lj, lj + 1)):
                    adj[i].append(j)
                    adj[j].append(i)
        diode_at = {}   # shape index -> diode area already planned on that component
        for N in range(2, 6):
            use = [i for i in range(n) if (not lvl[i][1] and lvl[i][0] <= N) or (lvl[i][1] and lvl[i][0] < N)]
            useset, seen = set(use), set()
            for s0 in use:
                if s0 in seen or lvl[s0][1] or lvl[s0][0] != N:
                    continue
                comp, stack = [], [s0]
                seen.add(s0)
                while stack:
                    i = stack.pop()
                    comp.append(i)
                    for j in adj[i]:
                        if j in useset and j not in seen:
                            seen.add(j)
                            stack.append(j)
                m1 = [shapes[i][1:5] for i in comp if not lvl[i][1]]   # pin landings (any metal of the component)
                ga, prot = 0., False
                for x, y, kind, a in tl:
                    if any(_inside((x, y), r) for r in m1):
                        if kind == 'sd':
                            prot = True
                        elif kind == 'g':
                            ga += a
                if prot or ga <= 0:
                    continue
                dio = sum(diode_at.get(i, 0.) for i in comp)
                per = sum(2 * ((shapes[i][3] - shapes[i][1]) + (shapes[i][4] - shapes[i][2]))
                          for i in comp if lvl[i] == (N, False))
                if per * THICK[f'metal{N}'] / (ga + 2 * dio) < MARGIN * LIMIT:
                    continue
                need = need_area({f'metal{N}': per}, ga) - dio
                need = max(0.36, round(need, 2))
                segs = []
                for i in sorted(comp, key=lambda i: -lvl[i][0]):
                    L_, v_ = lvl[i]
                    if v_ or L_ < landing_min:
                        continue
                    x1, y1, x2, y2 = shapes[i][1:5]
                    w, h = x2 - x1, y2 - y1
                    segs.append((f'metal{L_}', x1, (y1 + y2) / 2, x2, (y1 + y2) / 2) if w >= h else
                                (f'metal{L_}', (x1 + x2) / 2, y1, (x1 + x2) / 2, y2))
                out.append(dict(net=net, level=N, area=need, segs=segs))
                diode_at[comp[0]] = diode_at.get(comp[0], 0.) + need
    return out


def _val_um(v):
    v = v.lower()
    for suf, k in (('u', 1.), ('n', 1e-3), ('e-6', 1.), ('e-9', 1e-3)):
        if v.endswith(suf):
            return float(v[:-len(suf)]) * k
    return float(v) * 1e6


def _subckts(text):
    text = text.replace('\n+', ' ')
    subs, cur = {}, None
    for line in text.splitlines():
        t = line.split()
        if not t or t[0].startswith('*'):
            continue
        if t[0].lower() == '.subckt':
            cur = t[1]
            subs[cur] = dict(ports=[p for p in t[2:] if '=' not in p], lines=[])
        elif t[0].lower() == '.ends':
            cur = None
        elif cur:
            subs[cur]['lines'].append(t)
    return subs


def macro_pin_info(spice_path, name, _subs=None):
    """{pin: (protected, gate_area_um2)} for a macro subckt: protected when a MOS source/drain
    (diffusion) sits on the pin inside the macro.  Unknown children count as protected."""
    from pathlib import Path
    subs = _subs or _subckts(Path(spice_path).read_text())
    if name not in subs:
        return {}
    s = subs[name]
    info = {p: [False, 0.] for p in s['ports']}
    for t in s['lines']:
        if t[0][0] not in 'XxMm':
            continue
        params = dict(p.split('=', 1) for p in t if '=' in p)
        toks = [p for p in t[1:] if '=' not in p]
        model = toks[-1]
        nodes = toks[:-1]
        if 'fet' in model and len(nodes) >= 4:
            l = _val_um(params.get('l', '0.28u'))
            d, g, so = nodes[0], nodes[1], nodes[2]
            for n in (d, so):
                if n in info:
                    info[n][0] = True
            if g in info:
                info[g][1] += _val_um(params.get('w', '1u')) * l * float(params.get('m', 1))
        elif model in subs:
            child = macro_pin_info(None, model, subs)
            for n, cp in zip(nodes, subs[model]['ports']):
                if n in info and cp in child:
                    info[n][0] |= child[cp][0]
                    info[n][1] += child[cp][1]
        else:
            for n in nodes:
                if n in info:
                    info[n][0] = True
    return {p: tuple(v) for p, v in info.items()}


def spice_lines(placed, sub='VSS', prefix='DANT'):
    """LVS-reference lines for the placed diodes (ngspice/netgen diode_nd2ps_03v3, SI units)."""
    out = []
    for i, p in enumerate(q for q in placed if q.get('placed')):
        out.append(f'{prefix}{i} {sub} {p["net"]} diode_nd2ps_03v3 area={p["area"]:.4g}p pj={p["pj"]:.4g}u')
    return out


def painted_from_cmds(cmds):
    """Recover painted rectangles from a Magic `box values ...` / `paint layer` command list."""
    out, box = [], None
    for c in cmds:
        if c.startswith('box values '):
            box = [float(v) for v in c.split()[2:6]]
        elif c.startswith('paint ') and box:
            for l in c.split()[1].split(','):
                out.append((l, *box))
    return out
