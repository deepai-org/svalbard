"""Wired TX benches with the REAL phase source (MW-31, mode walk F9/U1): extracted pt_pll_ring_core open loop on the
regulated ring supply -> route RC -> extracted pt_wiredtx (4 phases: ring PH0/2/4/6) or wtx_serq8 core (8 phases).

    python3 sim_realring.py tune  '{"corner":"ss","temp":32,"vring":2.69,"band":1,"f":625e6}'
    python3 sim_realring.py block '{"corner":"ss","temp":32,"vdd":3.15,"vring":2.69,"band":1,"vctrl":1.6,"tag":"x"}'
    python3 sim_realring.py core8 '{...,"rep":1}'
Negative control: "kill":k opens ring phase k (pulled low) -> must fail.  "ideal":true keeps the ideal sources at the
SAME measured frequency (must reproduce the published ideal-phase result).
"""
import sys, json, os
from pathlib import Path
import numpy as np

WTX = Path(__file__).resolve().parent
sys.path.insert(0, str(WTX))
import tools, sim_wiredtx as S, sim_core8 as K, sim_ringsrc as R
HERE = tools.SCRATCH / 'realring'


def tune(corner, temp, vring, band, f, pess=False, tol=0.004, **_):
    wk = HERE / 'tune'
    pts = {}
    def run(vc):
        r = R.cal(corner, temp, vring, band, [round(vc, 4)], pess=pess, work=wk)[round(vc, 4)]
        pts[vc] = r.get('f_mhz', 0) * 1e6 if r.get('osc') else 0.0
        return pts[vc], r
    a, b = (1.0, 1.4) if not band else (1.3, 1.8)
    fa, ra = run(a); fb, rb = run(b); last = rb
    for _ in range(5):
        if abs(fb - f) / f < tol:
            break
        if fb == fa:
            break
        c = min(2.6, max(0.7, b + (f - fb) * (b - a) / (fb - fa)))
        a, fa = b, fb
        b = c; fb, last = run(b)
    out = dict(corner=corner, temp=temp, vring=vring, band=band, pess=pess, vctrl=round(b, 4), f_hz=fb, target=f, cal=last, pts=pts)
    (HERE / f'tune_{corner}_{vring}_{band}_{f / 1e6:g}{"_p" if pess else ""}.json').write_text(json.dumps(out, indent=1))
    return out


def _swap_phases(deck, names_ring, vring, vctrl, band, route, kill, dut_nodes):
    """replace the ideal phase sources (B/V PHx on <node>_drv) by the ring; keep R<..>_drv as the route R."""
    rr, cr = route
    L = []
    for l in deck.splitlines():
        p = l.split()
        if p and p[0][:3] in ('BPH', 'VPH') and p[1].endswith('_drv') and p[1][:-4] in dut_nodes:
            continue
        if p and p[0].startswith('RPH') and p[0].endswith('_drv') is False and len(p) == 4 and p[2] in dut_nodes and p[1] == p[2] + '_drv':
            l = f'{p[0]} {p[1]} {p[2]} {rr}'
        if p and p[0].startswith('R') and len(p) == 4 and p[2] in dut_nodes and p[1] == p[2] + '_drv':
            l = f'{p[0]} {p[1]} {p[2]} {rr}'
        if l.startswith('.include') and '.include ring.spice' not in L:
            L.append('.include ring.spice')
        L.append(l)
    out = [f'RG{k}' for k in range(8)]
    ins = R.ring_lines(vring, vctrl, band, out=out)
    for k in range(8):
        tgt = names_ring.get(k)
        src = out[k]
        if kill is not None and k == kill:
            ins += [f'RKILL{k} {src} 0 1k']; src = '0'
        if tgt:
            ins += [f'RRT{k} {src} {tgt}_drv 0.01', f'CRT{k}a {tgt}_drv 0 {cr / 2}', f'CRT{k}b {tgt} 0 {cr / 2}']
        else:
            ins += [f'CRD{k} {src} 0 {cr + 25e-15}']     # unused ring phase: same route C + a gate-load stand-in
    i = max(j for j, l in enumerate(L) if l.startswith('.include'))
    return '\n'.join(L[:i + 1] + ins + L[i + 1:]) + '\n'


def block(corner='typical', temp=27, vdd=3.3, vring=2.925, band=1, vctrl=1.5, f=None, tag='blk', route=(30.0, 60e-15),
          kill=None, ideal=False, pess=False, ring_pess=False, nwords=8, bpc=4, ideal_cfg=None, **_):
    """published extracted pt_wiredtx, serializer mode, CMD outputs decoded (as sim_wiredtx.run_case)."""
    dut = tools.GENERATED / 'wiredtx.ext.spice'
    if f is None:
        f = R.cal(corner, temp, vring, band, [vctrl], pess=ring_pess, work=HERE / 'tune')[vctrl]['f_mhz'] * 1e6
    rate = f * bpc
    S.PESSIMISTIC = pess
    nodes = {0: 'WTX_PH0', 2: 'WTX_PH90', 4: 'WTX_PH180', 6: 'WTX_PH270'}
    work = HERE / 'blk' / tag
    if ideal and ideal_cfg:
        # isolating controls (review finding 2): ideal tanh sources with ONE real-ring property at a time:
        # swing (V), duty (at mid-swing), rise offsets of PH0/90/180/270 (s).  Rising edges stay on their grid.
        import math
        sw = ideal_cfg.get('swing', vdd); du = ideal_cfg.get('duty', 0.5); offs = ideal_cfg.get('offsets', [0, 0, 0, 0])
        def phase_sources(rate_, vdd_, stopped=False, bpc=4, fallback=False):
            tq = bpc / rate_; tr = min(50e-12, tq / 16); kk = 2.197 / tr; c = math.sin(math.pi * (du - 0.5)); out = []
            for k, ph in enumerate(('0', '90', '180', '270')):
                t0_ = k * tq / 4 + tr / 2 + offs[k] + math.asin(c) / (2 * math.pi) * tq
                out.append(f'BPH{ph} WTX_PH{ph} 0 V={sw}*(0.5+0.5*tanh({kk * tq / (2 * math.pi):.6e}'
                           f'*(sin(2*3.141592653589793*(time-{t0_:.6e})/{tq:.6e})+{c:.6f})))')
            out += [f'VMODEH MODE_H 0 {vdd_ if bpc == 2 else 0}', f'VMODEF MODE_F 0 {vdd_ if bpc == 1 else 0}']
            return out
        S.phase_sources = phase_sources
    if not ideal:
        b0 = S.build
        def build(*a, **k):
            d, n = b0(*a, **k)
            d = _swap_phases(d, nodes, vring, vctrl, band, route, kill, set(nodes.values()))
            return d, n
        S.build = build
        for sub in ('phase', 'data'):
            (work / f'{tag}_{sub}').mkdir(parents=True, exist_ok=True)
            (work / f'{tag}_{sub}' / 'ring.spice').write_text(R.ring_text(ring_pess))
    r = S.run_case(work, dut, 'pt_wiredtx', rate=rate, nwords=nwords, corner=corner, temp=temp, vdd=vdd, tag=tag, bpc=bpc)
    r.update(real_ring=not ideal, vring=vring, vctrl=vctrl, band=band, ring_f_hz=f, route=route, kill=kill, pess=pess, ring_pess=ring_pess, ideal_cfg=ideal_cfg)
    (work / 'result.json').write_text(json.dumps(r, indent=1, default=str))
    return r


def core8(corner='typical', temp=27, vdd=3.3, vring=2.925, band=0, vctrl=1.2, f=None, tag='c8', route=(30.0, 60e-15),
          kill=None, ideal=False, pess=False, ring_pess=False, nwords=7, rep=1, **_):
    if f is None:
        f = R.cal(corner, temp, vring, band, [vctrl], pess=ring_pess, work=HERE / 'tune')[vctrl]['f_mhz'] * 1e6
    rate = f * 8
    S.PESSIMISTIC = pess
    nodes = {k: f'PH{a}' for k, a in enumerate((0, 45, 90, 135, 180, 225, 270, 315))}
    work = HERE / 'c8' / tag
    if not ideal:
        d0 = K.deck
        def deck(*a, **k):
            d, n = d0(*a, **k)
            return _swap_phases(d, nodes, vring, vctrl, band, route, kill, set(nodes.values())), n
        K.deck = deck
        for sub in ('phase', 'data'):
            (work / f'{tag}_{sub}').mkdir(parents=True, exist_ok=True)
            (work / f'{tag}_{sub}' / 'ring.spice').write_text(R.ring_text(ring_pess))
    r = K.run(work, K.DUTS['ext'], rate=rate, corner=corner, temp=temp, vdd=vdd, nwords=nwords, tag=tag, rep=rep)
    r.update(real_ring=not ideal, vring=vring, vctrl=vctrl, band=band, ring_f_hz=f, route=route, kill=kill, pess=pess, ring_pess=ring_pess)
    (work / 'result.json').write_text(json.dumps(r, indent=1, default=str))
    return r


if __name__ == '__main__':
    fn = dict(tune=tune, block=block, core8=core8)[sys.argv[1]]
    r = fn(**json.loads(sys.argv[2]))
    print(json.dumps({k: v for k, v in r.items() if k not in ('cal', 'pts')}, default=str)[:3000])
