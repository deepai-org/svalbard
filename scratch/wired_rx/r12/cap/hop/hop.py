"""Hop-slack instrument for pt_wrx_cap (r12 capture).
registry(capture)  -> every flop / latch of the CURRENT capture.py: (cell, kind, ck, d, q, pre)
nodes(ext, reg)    -> ngspice vector names of each storage element's clock pin and D pin in the extracted top
                      (C-only: the net itself; R+C: the gate sub-node of the element's own input devices)
Crossing stream: ngspice `wrdata` into a FIFO, read here line by line, only VDD/2 crossings are kept (no waveform on disk).
analyse(cross, elems, T, t_su, t_h, t_start) -> per element: min setup / hold separation at its clock edges and the slacks."""
import json, re, os, threading
from pathlib import Path
import numpy as np

T_REQ = {'ff': (100, 78), 'tt': (120, 92), 'ss': (182, 132), 'pess': (228, 184), 'ss35': (182, 132), 'sf': (120, 92), 'fs': (120, 92)}
INPUT_D = ('S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'LDG', 'SLIPP', 'SLIPM') + tuple(f'PD{k}' for k in range(8))


def registry(c):
    """Instrument Cell.ff / Cell.latch of capture module c and rebuild every cell's netlist; returns {cell: [elem...]}."""
    reg = {}
    of = c.Cell.ff
    def ff(self, ck, d, q, keep=False, **kw):
        reg.setdefault(self.name, []).append(dict(kind='ff', ck=ck, d=d, q=q, pre=f'u{self.k + 1}_'))
        return of(self, ck, d, q, keep=keep, **kw)
    c.Cell.ff = ff
    ol = getattr(c, '_latch', None)
    if ol:
        def latch(cell, d, ck, ckn, q):
            reg.setdefault(cell.name, []).append(dict(kind='latch', ck=ck, d=d, q=q, pre=f'{q}_l'))
            return ol(cell, d, ck, ckn, q)
        c._latch = latch
    try:
        for n in c.CELLS:
            c.CELLS[n]()
    finally:
        c.Cell.ff = of
        if ol:
            c._latch = ol
    # split cells: pieces carry the elements of their groups; map by the q net (unique per element)
    return reg


def parse_ext(path):
    subs, cur, top_x = {}, None, []
    lines = Path(path).read_text().splitlines()
    joined = []
    for l in lines:
        if l.startswith('+') and joined:
            joined[-1] += ' ' + l[1:]
        else:
            joined.append(l)
    for l in joined:
        t = l.split()
        if not t:
            continue
        if t[0].lower() == '.subckt':
            cur = t[1]; subs[cur] = dict(ports=t[2:], x=[], dev=[])
        elif t[0].lower() == '.ends':
            cur = None
        elif cur and t[0][0] in 'Xx':
            if len(t) > 5 and t[5] in ('nfet_03v3', 'pfet_03v3'):
                subs[cur]['dev'].append(t[1:5])
            else:
                subs[cur]['x'].append(t)
    return subs


def nodes(ext, reg, top='pt_wrx_cap', prefix='xcap.'):
    subs = parse_ext(ext)
    out = []
    tops = set(subs[top]['ports'])
    def node(n):
        if n in tops:
            return {'VDD': 'vdd', 'VSS': '0'}.get(n, n.lower())
        return prefix + n.lower()
    for x in subs[top]['x']:
        inst = x[0][1:] if x[0][:2].upper() == 'XX' else x[0]
        cell = x[-1]
        conn = dict(zip(subs[cell]['ports'], x[1:-1]))
        elems = reg.get(cell, [])
        if not elems and cell.startswith('wc_front'):
            seen = set(); elems = []
            for e in reg.get('wc_front', []):
                if e['pre'] not in seen and e['pre'] + 'QB' in conn:
                    seen.add(e['pre']); elems.append(e)
        for e in elems:
            if e['ck'] not in conn or e['d'] not in conn:
                continue
            out.append(dict(inst=inst, cell=cell, **e, ck_node=node(conn[e['ck']]), d_node=node(conn[e['d']]),
                            q_node=node(conn[e['q']]), input=e['d'] in INPUT_D))
    return out


class Crossings:
    """Read a wr_singlescale wrdata stream (time v1 v2 ...) and keep VDD/2 crossings per column as (t, +1 rising / -1 falling)."""
    def __init__(self, path, names, th):
        self.path, self.names, self.th = str(path), names, th
        self.x = [[] for _ in names]; self.err = None; self.nlines = 0
    def run(self):
        try:
            prev = None; n = len(self.names) + 1
            with open(self.path) as f:
                for line in f:
                    a = line.split()
                    if len(a) != n:
                        continue
                    v = np.array(a, float); self.nlines += 1
                    if prev is not None:
                        p, q = prev[1:] > self.th, v[1:] > self.th
                        for k in np.nonzero(p != q)[0]:
                            y0, y1 = prev[k + 1], v[k + 1]
                            self.x[k].append((prev[0] + (self.th - y0) * (v[0] - prev[0]) / (y1 - y0), 1 if q[k] else -1))
                    prev = v
        except Exception as exc:
            self.err = repr(exc)
    def start(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        os.mkfifo(self.path)
        self.t = threading.Thread(target=self.run, daemon=True); self.t.start()
    def result(self, timeout=900):
        self.t.join(timeout)
        return {n: x for n, x in zip(self.names, self.x)}


def probe_names(elems):
    s = []
    for e in elems:
        for k in ('ck_node', 'd_node'):
            if e[k] not in s:
                s.append(e[k])
    return s


def analyse(cross, elems, T, corner, t_start, t_end=1.0):
    """Per element: min setup / hold separation over its clock RISING edges in [t_start, t_end] (separations capped at T)."""
    su_req, h_req = T_REQ[corner]
    rows = []
    for e in elems:
        ck = [t for t, s in cross.get(e['ck_node'], []) if s > 0 and t_start <= t <= t_end]
        d = np.array(sorted(t for t, s in cross.get(e['d_node'], [])))
        su, ho, wsu, who = T, T, None, None
        for t in ck:
            j = np.searchsorted(d, t)
            if j > 0 and t - d[j - 1] < su:
                su, wsu = t - d[j - 1], t
            if j < len(d) and d[j] - t < ho:
                ho, who = d[j] - t, t
        r = dict(inst=e['inst'], cell=e['cell'], kind=e['kind'], ck=e['ck'], d=e['d'], q=e['q'], input=e['input'], edges=len(ck),
                 d_edges=int(np.sum((d >= t_start) & (d <= t_end))),
                 setup_sep_ps=round(su * 1e12, 1), hold_sep_ps=round(ho * 1e12, 1),
                 setup_slack_ps=round(su * 1e12 - su_req, 1), hold_slack_ps=round(ho * 1e12 - h_req, 1),
                 worst_setup_at_ns=round(wsu * 1e9, 3) if wsu else None, worst_hold_at_ns=round(who * 1e9, 3) if who else None)
        r['slack_frac_T'] = round(min(r['setup_slack_ps'], r['hold_slack_ps']) / (T * 1e12), 3)
        rows.append(r)
    return rows


def summary(rows, T):
    lim = 0.1 * T * 1e12
    internal = [r for r in rows if not r['input'] and r['edges']]
    bad = [r for r in internal if r['setup_slack_ps'] < lim or r['hold_slack_ps'] < lim]
    ws = min(internal, key=lambda r: r['setup_slack_ps'], default=None)
    wh = min(internal, key=lambda r: r['hold_slack_ps'], default=None)
    inp = [r for r in rows if r['input'] and r['edges']]
    f = lambda r: None if r is None else {k: r[k] for k in ('inst', 'ck', 'd', 'q', 'setup_slack_ps', 'hold_slack_ps', 'edges')}
    return dict(limit_ps=round(lim, 1), elements=len(rows), internal_clocked=len(internal), never_clocked=[f"{r['inst']}.{r['q']}" for r in rows if not r['edges']],
                fail=len(bad), pass_=(len(bad) == 0 and len(internal) > 0), worst_setup=f(ws), worst_hold=f(wh),
                failing=[f(r) for r in sorted(bad, key=lambda r: min(r['setup_slack_ps'], r['hold_slack_ps']))[:40]],
                worst_input=f(min(inp, key=lambda r: min(r['setup_slack_ps'], r['hold_slack_ps']), default=None)))
