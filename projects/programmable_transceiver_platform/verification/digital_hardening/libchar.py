#!/usr/bin/env python3
"""In-window Liberty characterization of gf180mcu_fd_sc_mcu7t5v0 with ngspice.

The PDK ships one in-window library (tt_025C_3v30). This script derives libraries at the
operating envelope's process corners (scratch/reviews/MANDATE.md: 22-32 C, 3.15-3.35 V; ss and ff
models) by SPICE simulation of the PDK cell netlists:

  * delay / transition tables (combinational, rising_edge/falling_edge, clear, preset arcs):
    every arc is simulated on a 6x6 subgrid of the library's own (input slew, load) index at the
    target corner AND at tt_025C_3v30 with the same harness. The published value is
        PDK_tt(i, j) * sim_corner(i, j) / sim_tt(i, j)
    with the ratio interpolated piecewise-linearly between subgrid points. Anchoring to the PDK tt
    table cancels harness differences (the PDK libraries come from a different simulator setup);
    the ratio carries the device, temperature and supply dependence.
  * setup / hold / recovery / removal tables: bisected on a 3x3 subgrid at the corner and at tt
    (pass = output reaches its new value with <= 10 % clock-to-Q push-out, and the old value is
    kept for hold/removal). Published value = PDK_tt + (sim_corner - sim_tt), interpolated.
  * min_pulse_width / minimum_period scalars: scaled by the cell's clock-to-Q ratio.
  * pin capacitances, power and leakage tables: kept from tt (not used for timing signoff).

Method check (`--validate`): the same procedure applied to ss_125C_3v00, an out-of-window corner
the PDK does publish, is compared entry by entry with the PDK's own ss_125C_3v00 library.

Usage:
  libchar.py run   --cells used|all|<c1,c2> --corners ss_032C_3v15,... --jobs 12 --cache DIR
  libchar.py build --cache DIR --out DIR [--corners ...]
  libchar.py validate --cache DIR
"""
import argparse
import bisect
import itertools
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liberty_io as L  # noqa: E402

PDK = Path(os.environ.get('PT_LIBCHAR_PDK', '/home/ubuntu/svalbard/scratch/digital-libchar/pdk'))
SC = 'gf180mcu_fd_sc_mcu7t5v0'
PRE = SC + '__'
NGSPICE_DIR = PDK / 'libs.tech/ngspice'
CELL_SPICE = PDK / f'libs.ref/{SC}/spice/{SC}.spice'
LIBDIR = PDK / f'libs.ref/{SC}/lib'
TT_LIB = LIBDIR / f'{SC}__tt_025C_3v30.lib'

# name -> (model section, temperature C, supply V)
CORNERS = {
    'tt_025C_3v30': ('typical', 25, 3.30),
    'ss_022C_3v15': ('ss', 22, 3.15),
    'ss_032C_3v15': ('ss', 32, 3.15),
    'ff_022C_3v35': ('ff', 22, 3.35),
    'ff_032C_3v35': ('ff', 32, 3.35),
    'ss_032C_3v50': ('ss', 32, 3.50),    # per-chip supply trim point for slow dies (MANDATE 2026-11-14)
    'ss_125C_3v00': ('ss', 125, 3.00),   # PDK publishes it: anchor of the ss corners, and plain-ratio validation
    'ss_n40C_3v00': ('ss', -40, 3.00),   # PDK publishes it: validation of the anchored ss derivation
}
REF = 'tt_025C_3v30'
SUB_DELAY = [0, 2, 4, 6, 8, 9]
SUB_CONS = [0, 4, 9]
DELAY_TABLES = ('cell_rise', 'cell_fall', 'rise_transition', 'fall_transition')
DELAY_TYPES = ('combinational', 'combinational_rise', 'combinational_fall', 'rising_edge', 'falling_edge',
               'clear', 'preset')
CONS_TYPES = ('setup_rising', 'setup_falling', 'hold_rising', 'hold_falling', 'recovery_rising',
              'recovery_falling', 'removal_rising', 'removal_falling')
SCALAR_TYPES = ('min_pulse_width', 'minimum_period')
# Liberty: thresholds 50 % delay; slew 30-70 % with slew_derate_from_library 0.5
SLEW_LO, SLEW_HI, DERATE = 0.3, 0.7, 0.5
RAMP = DERATE / (SLEW_HI - SLEW_LO)        # full-swing linear ramp time per library slew unit


def subckt_pins():
    pins = {}
    for line in open(CELL_SPICE):
        if line.upper().startswith('.SUBCKT '):
            t = line.split()
            pins[t[1]] = t[2:]
    return pins


def header(corner):
    sec, temp, vdd = CORNERS[corner]
    return [f'.include {NGSPICE_DIR}/design.ngspice', f'.lib {NGSPICE_DIR}/sm141064.ngspice {sec}',
            f'.include {CELL_SPICE}', f'.temp {temp}', f'VDD vdd 0 {vdd}',
            '.options method=gear reltol=1e-4 abstol=1e-13 vntol=1e-7 chgtol=1e-16']


def run_spice(lines, tag=''):
    with tempfile.TemporaryDirectory(prefix='plc') as d:
        fn = Path(d) / 'deck.sp'
        fn.write_text('\n'.join(lines) + '\n.end\n')
        p = subprocess.run(['ngspice', '-b', str(fn)], capture_output=True, text=True, cwd=d, timeout=3600)
    res = {}
    for name, val in re.findall(r'^([a-z][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)', p.stdout, re.M):
        res[name] = float(val)
    return res


# ------------------------------------------------------------------ cell model
class Cell:
    def __init__(self, g, templates, spins):
        self.g = g
        self.name = L.unq(g.args[0])
        self.short = self.name[len(PRE):]
        self.templates = templates
        self.spins = spins[self.name]
        self.pins = {L.unq(p.args[0]): p for p in g.groups('pin')}
        self.inputs = [n for n, p in self.pins.items() if p.attr('direction') == 'input']
        self.outputs = [n for n, p in self.pins.items() if p.attr('direction') == 'output']
        ff = g.group('ff')
        self.seq = None
        if ff is not None:
            ck = ff.attr('clocked_on')
            neg = ck.replace(' ', '').startswith('(!') or ck.startswith('!')
            ckpin = L.bool_vars(ck)[0]
            self.seq = dict(clk=ckpin, neg=neg, d=L.bool_vars(ff.attr('next_state'))[0],
                            clear=L.bool_vars(ff.attr('clear'))[0] if ff.attr('clear') else None,
                            preset=L.bool_vars(ff.attr('preset'))[0] if ff.attr('preset') else None,
                            iq=L.unq(ff.args[0]), iqn=L.unq(ff.args[1]))
        self.unsupported = [g2.name for g2 in g.groups() if g2.name in ('latch', 'statetable', 'ff_bank', 'latch_bank')]

    def arcs(self):
        """(pin, timing group) for every timing group of the cell."""
        for pn, p in self.pins.items():
            for t in p.groups('timing'):
                yield pn, t

    def netmap(self, k, assign):
        """Instance node names: assign maps pin -> node; supplies tied; unlisted outputs floated."""
        nodes = []
        for x in self.spins:
            if x in assign:
                nodes.append(assign[x])
            elif x in ('VDD', 'VNW'):
                nodes.append('vdd')
            elif x in ('VSS', 'VPW'):
                nodes.append('0')
            else:
                nodes.append(f'nc{k}_{x}')
        return f'X{k} ' + ' '.join(nodes) + f' {self.name}'


def tie(v):
    return 'vdd' if v else '0'


def sensitize(cell, out, rel, sense, when):
    """[(side assignment dict, input edge 'r'/'f', output edge 'r'/'f')] sensitizing vectors."""
    func = L.parse_bool(cell.pins[out].attr('function'))
    others = [x for x in cell.inputs if x != rel]
    fixed = {}
    if when:
        wf = L.parse_bool(when)
        wv = L.bool_vars(when)
    res = []
    for vec in itertools.product([0, 1], repeat=len(others)):
        env = dict(zip(others, vec))
        if when and not wf(env if set(wv) <= set(env) else {**env, **{v: 0 for v in wv if v not in env}}):
            continue
        f0 = func({**env, rel: 0})
        f1 = func({**env, rel: 1})
        if f0 == f1:
            continue
        pos = f1 > f0
        if sense == 'positive_unate' and not pos:
            continue
        if sense == 'negative_unate' and pos:
            continue
        res.append((env, pos))
    return res


def interp_axis(sub, n):
    """For full index position i in 0..n-1, (lo idx in sub, hi idx in sub, weight)."""
    out = []
    for i in range(n):
        j = bisect.bisect_right(sub, i) - 1
        j = max(0, min(j, len(sub) - 2))
        a, b = sub[j], sub[j + 1]
        w = (i - a) / (b - a)
        out.append((j, j + 1, w))
    return out


def interp_grid(subvals, sub1, sub2, n1, n2):
    ax1 = interp_axis(sub1, n1)
    ax2 = interp_axis(sub2, n2) if n2 > 1 else [(0, 0, 0.0)]
    full = []
    for (a1, b1, w1) in ax1:
        row = []
        for (a2, b2, w2) in ax2:
            v = ((1 - w1) * (1 - w2) * subvals[a1][a2] + w1 * (1 - w2) * subvals[b1][a2] +
                 (1 - w1) * w2 * subvals[a1][b2] + w1 * w2 * subvals[b1][b2])
            row.append(v)
        full.append(row)
    return full


# ------------------------------------------------------------------ delay arcs
def delay_deck(cell, corner, out, rel, ttype, sense, when, idx1, idx2, s1, s2):
    """One deck; instances for each subgrid point and each output edge. Returns (lines, keys)."""
    sec, temp, vdd = CORNERS[corner]
    h = vdd / 2
    lines = header(corner)
    keys = []
    k = 0
    smax = max(idx1[i] for i in s1)
    t0 = 1.0
    if ttype in ('combinational', 'combinational_rise', 'combinational_fall'):
        vecs = sensitize(cell, out, rel, sense, when)
        if not vecs:
            raise RuntimeError(f'{cell.name} {rel}->{out}: no sensitizing vector ({sense}, {when})')
        # one vector per output edge (first found)
        plan = []
        for oedge in ('r', 'f'):
            for env, pos in vecs:
                iedge = oedge if pos else ('f' if oedge == 'r' else 'r')
                plan.append((oedge, iedge, env))
                break
        for oedge, iedge, env in plan:
            for i in s1:
                sl = idx1[i]
                a, b = (0, vdd) if iedge == 'r' else (vdd, 0)
                src = f'in_{oedge}{i}'
                lines.append(f'V{src} {src} 0 PWL(0 {a} {t0}n {a} {t0 + sl * RAMP:.6g}n {b})')
                for j in s2:
                    k += 1
                    assign = {x: tie(v) for x, v in env.items()}
                    assign[rel] = src
                    assign[out] = f'o{k}'
                    lines.append(cell.netmap(k, assign))
                    lines.append(f'C{k} o{k} 0 {idx2[j]}p')
                    d = 'RISE' if iedge == 'r' else 'FALL'
                    lines.append(f'.meas tran d{k} TRIG v({src}) VAL={h} {d}=1 TARG v(o{k}) VAL={h} CROSS=1')
                    lines.append(f'.meas tran a{k} WHEN v(o{k})={SLEW_LO * vdd} CROSS=1')
                    lines.append(f'.meas tran b{k} WHEN v(o{k})={SLEW_HI * vdd} CROSS=1')
                    keys.append((oedge, i, j, k))
        tstop = t0 + smax * RAMP + 25
    else:
        sq = cell.seq
        ck, dpin = sq['clk'], sq['d']
        lo, hi = (vdd, 0) if sq['neg'] else (0, vdd)
        tm = 16.0  # measured event start (preload pulse 1-6 ns: wide enough for min_pulse_width at ss)
        env_when = {}
        if when:
            wv = L.bool_vars(when)
            wf = L.parse_bool(when)
            for vec in itertools.product([0, 1], repeat=len(wv)):
                e = dict(zip(wv, vec))
                if wf(e):
                    env_when = e
                    break
        for oedge in ('r', 'f'):
            if ttype in ('rising_edge', 'falling_edge'):
                # preload Q = !target via a fast clock pulse at 1-4 ns, then D=target, edge at tm
                tgt = 1 if oedge == 'r' else 0
                dsrc = f'd_{oedge}'
                lines.append(f'V{dsrc} {dsrc} 0 PWL(0 {vdd * (1 - tgt)} 9n {vdd * (1 - tgt)} 9.1n {vdd * tgt})')
                for i in s1:
                    sl = idx1[i]
                    csrc = f'c_{oedge}{i}'
                    lines.append(f'V{csrc} {csrc} 0 PWL(0 {lo} 1n {lo} 1.1n {hi} 6n {hi} 6.1n {lo} '
                                 f'{tm}n {lo} {tm + sl * RAMP:.6g}n {hi})')
                    for j in s2:
                        k += 1
                        assign = {x: tie(1) for x in (sq['clear'], sq['preset']) if x}
                        assign.update({ck: csrc, dpin: dsrc, out: f'o{k}'})
                        lines.append(cell.netmap(k, assign))
                        lines.append(f'C{k} o{k} 0 {idx2[j]}p')
                        d = 'FALL' if sq['neg'] else 'RISE'
                        td = f'TD={tm - 0.5}n'
                        lines.append(f'.meas tran d{k} TRIG v({csrc}) VAL={vdd / 2} {d}=2 TARG v(o{k}) VAL={vdd / 2} {td} CROSS=1')
                        lines.append(f'.meas tran a{k} WHEN v(o{k})={SLEW_LO * vdd} {td} CROSS=1')
                        lines.append(f'.meas tran b{k} WHEN v(o{k})={SLEW_HI * vdd} {td} CROSS=1')
                        keys.append((oedge, i, j, k))
            else:  # clear / preset: async pin falls at tm
                if (ttype == 'clear' and oedge != 'f') or (ttype == 'preset' and oedge != 'r'):
                    continue
                pre_q = 1 if ttype == 'clear' else 0
                dval = env_when.get(dpin, pre_q)
                ckv = env_when.get(ck, 0)
                dsrc = f'd_{oedge}'
                lines.append(f'V{dsrc} {dsrc} 0 PWL(0 {vdd * pre_q} 10n {vdd * pre_q} 10.1n {vdd * dval})')
                csrc = f'c_{oedge}'
                ck_end = vdd * ckv
                lines.append(f'V{csrc} {csrc} 0 PWL(0 {lo} 1n {lo} 1.1n {hi} 6n {hi} 6.1n {lo} 9n {lo} 9.1n {ck_end})')
                for i in s1:
                    sl = idx1[i]
                    asrc = f'r_{oedge}{i}'
                    lines.append(f'V{asrc} {asrc} 0 PWL(0 {vdd} {tm}n {vdd} {tm + sl * RAMP:.6g}n 0)')
                    for j in s2:
                        k += 1
                        assign = {x: tie(1) for x in (sq['clear'], sq['preset']) if x}
                        assign.update({ck: csrc, dpin: dsrc, rel: asrc, out: f'o{k}'})
                        lines.append(cell.netmap(k, assign))
                        lines.append(f'C{k} o{k} 0 {idx2[j]}p')
                        td = f'TD={tm - 0.5}n'
                        lines.append(f'.meas tran d{k} TRIG v({asrc}) VAL={vdd / 2} FALL=1 TARG v(o{k}) VAL={vdd / 2} {td} CROSS=1')
                        lines.append(f'.meas tran a{k} WHEN v(o{k})={SLEW_LO * vdd} {td} CROSS=1')
                        lines.append(f'.meas tran b{k} WHEN v(o{k})={SLEW_HI * vdd} {td} CROSS=1')
                        keys.append((oedge, i, j, k))
        tstop = tm + smax * RAMP + 25
    return lines, keys, tstop


def sim_delay(cell, corner, out, rel, ttype, sense, when, idx1, idx2):
    s1 = [i for i in SUB_DELAY if i < len(idx1)]
    s2 = [j for j in SUB_DELAY if j < len(idx2)]
    # (tstop scale, integration fallback): a few decks hit 'timestep too small' at t ~ 0 with gear;
    # trapezoidal integration with a looser reltol is the fallback (ratio error < 1 %).
    for scale, opt in ((1, None), (3, None), (9, None), (1, 'method=trap reltol=1e-3'), (3, 'method=trap reltol=1e-3')):
        lines, keys, tstop = delay_deck(cell, corner, out, rel, ttype, sense, when, idx1, idx2, s1, s2)
        if opt:
            lines = [l if not l.startswith('.options') else f'.options {opt} abstol=1e-13 vntol=1e-7 chgtol=1e-16' for l in lines]
        tstop *= scale
        lines.append(f'.tran 2p {tstop:.4g}n 0 {max(0.02, tstop / 4000):.4g}n')
        r = run_spice(lines)
        res = {}
        ok = True
        for oedge, i, j, k in keys:
            if f'd{k}' not in r or f'a{k}' not in r or f'b{k}' not in r:
                ok = False
                break
            res[f'{oedge},{i},{j}'] = (r[f'd{k}'] * 1e9, abs(r[f'b{k}'] - r[f'a{k}']) / DERATE * 1e9)
        if ok:
            return dict(s1=s1, s2=s2, res=res)
    raise RuntimeError(f'{cell.name} {rel}->{out} {ttype} {corner}: measurement failed')


# ------------------------------------------------------------------ constraints (bisection)
def cons_instances(cell, pin, ttype, when, idx1, idx2, tau, vdd, s1, s2, tables):
    """Build sources/instances for constraint checks at offsets tau[(table,i,j)].
    Returns (lines, checks) where checks map key -> (meas names, kind)."""
    sq = cell.seq
    ck, dpin = sq['clk'], sq['d']
    lo, hi = (vdd, 0) if sq['neg'] else (0, vdd)
    tc = 30.0  # clock 50 % crossing time of the checked edge
    lines, checks = [], {}
    k = 0
    statics = {}
    if when:
        wv = L.bool_vars(when)
        wf = L.parse_bool(when)
        for vec in itertools.product([0, 1], repeat=len(wv)):
            e = dict(zip(wv, vec))
            if wf(e):
                statics = e
                break
    for tab in tables:
        for i in s1:
            for j in s2:
                k += 1
                key = (tab, i, j)
                t = tau[key]
                cs, ds = idx2[j] * RAMP, idx1[i] * RAMP          # related (clock) ramp, constrained ramp
                c0 = tc - cs / 2
                # preload clock pulse at 2-5 ns, checked edge at tc
                lines.append(f'Vc{k} c{k} 0 PWL(0 {lo} 2n {lo} 2.1n {hi} 8n {hi} 8.1n {lo} {c0:.6g}n {lo} {c0 + cs:.6g}n {hi})')
                assign = {x: tie(1) for x in (sq['clear'], sq['preset']) if x}
                assign.update({x: tie(v) for x, v in statics.items() if x not in (ck, dpin, pin)})
                assign[ck] = f'c{k}'
                if pin == dpin:
                    rise = tab == 'rise_constraint'
                    if ttype.startswith('setup'):
                        old, new = (0, 1) if rise else (1, 0)
                        ev = tc - t       # D 50 % crossing
                        dpts = [(0, old), (ev - ds / 2, old), (ev + ds / 2, new)]
                        kind = ('capture', new)
                    else:  # hold: capture 'old_cap' (set well before), then D toggles at tc + t
                        cap_v = 0 if rise else 1
                        pre = 1 - cap_v
                        ev = tc + t
                        dpts = [(0, pre), (10, pre), (10.1, cap_v), (ev - ds / 2, cap_v), (ev + ds / 2, 1 - cap_v)]
                        kind = ('keep', cap_v)
                    # monotone PWL times
                    pts, last = [], -1
                    for tt, v in dpts:
                        tt = max(tt, last + 0.001)
                        pts.append(f'{tt:.6g}n {vdd * v}')
                        last = tt
                    # preload value for setup = old (clock at 2 ns captures it)
                    lines.append(f'Vd{k} d{k} 0 PWL({" ".join(pts)})')
                    assign[dpin] = f'd{k}'
                else:  # recovery / removal on async pin (active low), release (rise) at tc -/+ t
                    act = pin
                    is_clear = act == sq['clear']
                    dval = 1 if is_clear else 0
                    assign[dpin] = tie(dval)
                    ev = tc - t if ttype.startswith('recovery') else tc + t
                    pts, last = [], -1
                    for tt, v in [(0, 0), (ev - ds / 2, 0), (ev + ds / 2, 1)]:
                        tt = max(tt, last + 0.001)
                        pts.append(f'{tt:.6g}n {vdd * v}')
                        last = tt
                    lines.append(f'Va{k} a{k} 0 PWL({" ".join(pts)})')
                    assign[act] = f'a{k}'
                    kind = ('capture', dval) if ttype.startswith('recovery') else ('keep', 1 - dval)
                out = 'Q' if 'Q' in cell.outputs else cell.outputs[0]
                assign[out] = f'q{k}'
                lines.append(cell.netmap(k, assign))
                lines.append(f'Cq{k} q{k} 0 0.01p')
                edge = 'FALL' if sq['neg'] else 'RISE'
                lines.append(f'.meas tran e{k} WHEN v(c{k})={vdd / 2} {edge}=2')
                lines.append(f'.meas tran q{k} WHEN v(q{k})={vdd / 2} CROSS=LAST')
                lines.append(f'.meas tran f{k} FIND v(q{k}) AT=TEND')
                checks[key] = (k, kind)
    return lines, checks, tc


def sim_constraints(cell, corner, pin, ttype, when, idx1, idx2, tables, log=None):
    sec, temp, vdd = CORNERS[corner]
    s1 = [i for i in SUB_CONS if i < len(idx1)]
    s2 = [j for j in SUB_CONS if j < len(idx2)]
    keys = [(tab, i, j) for tab in tables for i in s1 for j in s2]
    lo = {k: -8.0 for k in keys}
    hi = {k: 14.0 for k in keys}
    # reference clock-to-Q (large margin) from the same harness: setup-type checks at tau=+14
    smax = max(max(idx1), max(idx2)) * RAMP

    def evaluate(tau):
        lines = header(corner)
        body, checks, tc = cons_instances(cell, pin, ttype, when, idx1, idx2, tau, vdd, s1, s2, tables)
        tend = tc + 40 + smax
        TEND = f'{tend:.6g}n'
        body = [b.replace('AT=TEND', f'AT={tend - 1:.6g}n') for b in body]
        lines += body
        lines.append(f'.tran 2p {tend:.6g}n 0 0.02n')
        r = run_spice(lines)
        out = {}
        for key, (k, (kind, val)) in checks.items():
            fv = r.get(f'f{k}')
            e = r.get(f'e{k}')
            q = r.get(f'q{k}')
            if fv is None or e is None:
                out[key] = (False, None)
                continue
            final = 1 if fv > vdd / 2 else 0
            if kind == 'capture':
                okv = final == val
                dq = (q - e) * 1e9 if (q is not None and q > e) else None
                out[key] = (okv and dq is not None, dq)
            else:
                # keep: final value is val and it was reached through the checked edge (no glitch back)
                okv = final == val and (q is None or q < e + 0.0 or True)
                dq = (q - e) * 1e9 if (q is not None and q > e) else None
                out[key] = (okv, dq)
        return out

    # reference delays at the passing extreme
    ref = evaluate(hi)
    for key, (ok, dq) in ref.items():
        if not ok:
            raise RuntimeError(f'{cell.name} {pin} {ttype} {key} {corner}: fails at +{hi[key]} ns')
    dref = {key: dq for key, (ok, dq) in ref.items()}
    chk_lo = evaluate(lo)
    for key, (ok, dq) in chk_lo.items():
        if ok and (dq is None or dref[key] is None or dq <= 1.1 * dref[key]):
            if log is not None:
                log.append(f'{cell.short} {pin} {ttype} {key} {corner}: passes at lower bound')
    for _ in range(16):
        mid = {k: (lo[k] + hi[k]) / 2 for k in keys}
        res = evaluate(mid)
        for key, (ok, dq) in res.items():
            good = ok
            if good and dref[key] is not None and dq is not None:
                good = dq <= 1.1 * dref[key]
            elif good and dref[key] is not None and dq is None:
                good = False
            if good:
                hi[key] = mid[key]
            else:
                lo[key] = mid[key]
    return dict(s1=s1, s2=s2, res={f'{t},{i},{j}': hi[(t, i, j)] for (t, i, j) in keys},
                dref={f'{t},{i},{j}': dref[(t, i, j)] for (t, i, j) in keys})


# ------------------------------------------------------------------ per-cell job
def arc_id(pin, t):
    return '|'.join([pin, t.attr('related_pin') or '', t.attr('timing_type') or 'combinational',
                     t.attr('timing_sense') or '', t.attr('when') or ''])


def char_cell(cellname, corner, cache):
    outf = Path(cache) / corner / f'{cellname}.json'
    if outf.exists():
        return cellname, corner, 'cached'
    lib = load_tt()
    templates = {L.unq(g.args[0]): g for g in lib.groups('lu_table_template')}
    cell = Cell(lib.group('cell', PRE + cellname), templates, subckt_pins())
    res = dict(cell=cellname, corner=corner, arcs={}, notes=[])
    t0 = time.time()
    if cell.unsupported:
        res['skip'] = 'unsupported group ' + ','.join(cell.unsupported)
    else:
        shared = {}
        arcs = list(cell.arcs())
        # Unconditional arcs first: a conditional (`when`) delay arc of the same pin pair and sense
        # reuses that ratio (the corner/temperature/supply ratio is a property of the driving
        # stage; checked against the PDK's own conditional tables by `validate`).
        arcs.sort(key=lambda pt: 0 if not pt[1].attr('when') else 1)
        for pin, t in arcs:
            tt = t.attr('timing_type') or 'combinational'
            aid = arc_id(pin, t)
            tabs = [g for g in t.groups() if g.name in DELAY_TABLES]
            if tt in DELAY_TYPES:
                if not tabs:
                    continue
                idx1, idx2, _ = L.table(tabs[0], templates)
                key = (pin, t.attr('related_pin'), tt, t.attr('timing_sense'))
                if t.attr('when') and key in shared:
                    res['arcs'][aid] = dict(kind='delay', alias=shared[key])
                    continue
                res['arcs'][aid] = dict(kind='delay', **sim_delay(cell, corner, pin, t.attr('related_pin'), tt,
                                                                   t.attr('timing_sense'), t.attr('when'), idx1, idx2))
                shared.setdefault(key, aid)
            elif tt in CONS_TYPES:
                ctabs = [g for g in t.groups() if g.name in ('rise_constraint', 'fall_constraint')]
                idx1, idx2, _ = L.table(ctabs[0], templates)
                res['arcs'][aid] = dict(kind='cons', **sim_constraints(cell, corner, pin, tt, t.attr('when'), idx1, idx2,
                                                                       [g.name for g in ctabs], res['notes']))
            elif tt in SCALAR_TYPES:
                continue
            else:
                res['notes'].append(f'unhandled timing_type {tt} on {aid}')
    res['seconds'] = round(time.time() - t0, 1)
    outf.parent.mkdir(parents=True, exist_ok=True)
    tmp = outf.with_suffix('.tmp')
    tmp.write_text(json.dumps(res))
    tmp.rename(outf)
    return cellname, corner, res['seconds']


_TT = None


def load_tt():
    global _TT
    if _TT is None:
        _TT = L.parse(TT_LIB.read_text())
    return _TT


def used_cells():
    f = Path(__file__).resolve().parent / 'liberty' / 'used_cells.txt'
    return [x.strip() for x in f.read_text().split() if x.strip()]


def timing_cells(lib):
    out = []
    for g in lib.groups('cell'):
        n = L.unq(g.args[0])[len(PRE):]
        if any(p.groups('timing') for p in g.groups('pin')):
            out.append(n)
    return out


# ------------------------------------------------------------------ build libraries
def ratio_grid(sim_c, sim_r, which, oedge, n1, n2):
    s1, s2 = sim_c['s1'], sim_c['s2']
    sub = [[sim_c['res'][f'{oedge},{i},{j}'][which] / sim_r['res'][f'{oedge},{i},{j}'][which] for j in s2] for i in s1]
    return interp_grid(sub, s1, s2, n1, n2)


def delta_grid(sim_c, sim_r, tab, n1, n2):
    s1, s2 = sim_c['s1'], sim_c['s2']
    sub = [[sim_c['res'][f'{tab},{i},{j}'] - sim_r['res'][f'{tab},{i},{j}'] for j in s2] for i in s1]
    return interp_grid(sub, s1, s2, n1, n2)


ANCHOR = {'ss': 'ss_125C_3v00'}   # PDK-published corner of the same process section, simulated too


def derive(cache, corner, base_lib=None, cells=None, anchored=None):
    """Return a new library tree for `corner` (tt tree copy with re-derived timing tables).

    anchored (default for ss corners): the value is interpolated between the PDK's own tt and
    ss_125C_3v00 tables, PDK_tt + (PDK_ss125 - PDK_tt) * s, with the corner fraction
    s = (sim_corner/sim_tt - 1) / (sim_ss125/sim_tt - 1) per table entry (delays, transitions) or per
    cell from clock-to-Q (constraints, pulse widths). Both ends are published characterization; SPICE
    supplies only how far the in-window corner sits between them. (Validation showed the plain ratio
    method under-predicts the PDK's own ss_125C tables: median -5 %, 5th percentile -32 %, and
    setup/hold deltas by ~0.2 ns, because of harness differences in slew-dominated entries and in
    the constraint criteria.)"""
    lib = L.parse(TT_LIB.read_text()) if base_lib is None else base_lib
    anc_name = ANCHOR.get(CORNERS[corner][0]) if anchored is None else (ANCHOR.get(CORNERS[corner][0]) if anchored else None)
    if anc_name == corner:
        anc_name = None
    anc_lib = L.parse((LIBDIR / f'{SC}__{anc_name}.lib').read_text()) if anc_name else None
    templates = {L.unq(g.args[0]): g for g in lib.groups('lu_table_template')}
    sec, temp, vdd = CORNERS[corner]
    keep, stats = [], dict(cells=0, tables=0, skipped=[])
    for g in lib.groups('cell'):
        name = L.unq(g.args[0])[len(PRE):]
        has_timing = any(p.groups('timing') for p in g.groups('pin'))
        if not has_timing:
            keep.append(g)  # fill, tap, endcap, antenna, tie (tie has no timing arcs in this library)
            continue
        fc = Path(cache) / corner / f'{name}.json'
        fr = Path(cache) / REF / f'{name}.json'
        if not (fc.exists() and fr.exists()) or (cells is not None and name not in cells):
            stats['skipped'].append(name)
            continue
        jc, jr = json.loads(fc.read_text()), json.loads(fr.read_text())
        if 'skip' in jc:
            stats['skipped'].append(name)
            continue
        ja = None
        if anc_lib is not None:
            fa = Path(cache) / anc_name / f'{name}.json'
            if not fa.exists():
                stats['skipped'].append(name)
                continue
            ja = json.loads(fa.read_text())
            ag = anc_lib.group('cell', PRE + name)
            atiming = {pn: p.groups('timing') for pn, p in ((L.unq(p.args[0]), p) for p in ag.groups('pin'))}
        # clock-to-Q ratio for scalar constraints
        cq = []
        for aid, a in jc['arcs'].items():
            if a['kind'] == 'delay' and 'alias' not in a and ('|rising_edge|' in aid or '|falling_edge|' in aid):
                ra = jr['arcs'][aid]
                for key in a['res']:
                    cq.append(a['res'][key][0] / ra['res'][key][0])
        cq_ratio = max(cq) if cq else None
        s_cell = None
        if ja is not None:
            sa = []
            for aid, a in jc['arcs'].items():
                if a['kind'] == 'delay' and 'alias' not in a and ('|rising_edge|' in aid or '|falling_edge|' in aid):
                    for key in a['res']:
                        r_c = a['res'][key][0] / jr['arcs'][aid]['res'][key][0]
                        r_a = ja['arcs'][aid]['res'][key][0] / jr['arcs'][aid]['res'][key][0]
                        if abs(r_a - 1) > 0.02:
                            sa.append((r_c - 1) / (r_a - 1))
            if sa:
                sa.sort()
                s_cell = min(1.5, max(0.0, sa[len(sa) // 2]))
        cell = Cell(g, templates, subckt_pins())
        tcount = {}
        for pin, t in cell.arcs():
            tt = t.attr('timing_type') or 'combinational'
            aid = arc_id(pin, t)
            k_t = tcount.get(pin, 0); tcount[pin] = k_t + 1
            at = atiming[pin][k_t] if ja is not None else None   # same timing group in the anchor library
            if tt in SCALAR_TYPES:
                for tg in t.groups():
                    if tg.name in ('rise_constraint', 'fall_constraint'):
                        _, _, v = L.table(tg, templates)
                        if at is not None and s_cell is not None:
                            _, _, va = L.table(at.group(tg.name), templates)
                            L.set_values(tg, [[x + (y - x) * s_cell for x, y in zip(r0, r1)] for r0, r1 in zip(v, va)])
                        elif cq_ratio:
                            L.set_values(tg, [[x * cq_ratio for x in row] for row in v])
                        else:
                            continue
                        stats['tables'] += 1
                continue
            a, ar = jc['arcs'].get(aid), jr['arcs'].get(aid)
            if a is None or ar is None:
                raise RuntimeError(f'{name}: missing arc {aid} in cache')
            al = a.get('alias') or ar.get('alias')
            aa = ja['arcs'].get(aid) if ja is not None else None
            if aa is not None and 'alias' in aa:
                al = al or aa['alias']
            if al:   # all corners use the same (unconditional) arc so the ratio is consistent
                a, ar = jc['arcs'][al], jr['arcs'][al]
                aa = ja['arcs'][al] if ja is not None else None
            for tg in t.groups():
                if tg.name in DELAY_TABLES:
                    idx1, idx2, v = L.table(tg, templates)
                    oedge = 'r' if 'rise' in tg.name else 'f'
                    which = 0 if tg.name.startswith('cell') else 1
                    rg = ratio_grid(a, ar, which, oedge, len(idx1), len(idx2))
                    if aa is not None:
                        _, _, va = L.table(at.group(tg.name), templates)
                        ga = ratio_grid(aa, ar, which, oedge, len(idx1), len(idx2))
                        out_v = []
                        for i in range(len(idx1)):
                            row = []
                            for j in range(len(idx2)):
                                if abs(ga[i][j] - 1) > 0.02:
                                    sf = min(1.5, max(0.0, (rg[i][j] - 1) / (ga[i][j] - 1)))
                                    row.append(v[i][j] + (va[i][j] - v[i][j]) * sf)
                                else:
                                    row.append(v[i][j] * rg[i][j])
                            out_v.append(row)
                        L.set_values(tg, out_v)
                    else:
                        L.set_values(tg, [[v[i][j] * rg[i][j] for j in range(len(idx2))] for i in range(len(idx1))])
                    stats['tables'] += 1
                elif tg.name in ('rise_constraint', 'fall_constraint'):
                    idx1, idx2, v = L.table(tg, templates)
                    if at is not None and s_cell is not None:
                        _, _, va = L.table(at.group(tg.name), templates)
                        L.set_values(tg, [[x + (y - x) * s_cell for x, y in zip(r0, r1)] for r0, r1 in zip(v, va)])
                    else:
                        dg = delta_grid(a, ar, tg.name, len(idx1), len(idx2))
                        L.set_values(tg, [[v[i][j] + dg[i][j] for j in range(len(idx2))] for i in range(len(idx1))])
                    stats['tables'] += 1
        keep.append(g)
        stats['cells'] += 1
    # replace cell list, rename library and operating point
    newname = f'{SC}__{corner}'
    lib.args = [newname]
    lib.children = [c for c in lib.children if not (isinstance(c, L.Group) and c.name == 'cell')] + keep
    lib.set_attr('nom_temperature', str(temp))
    lib.set_attr('nom_voltage', str(vdd))
    for c in lib.children:
        if isinstance(c, L.Complex) and c.name == 'voltage_map' and L.unq(c.args[0]) in ('VDD', 'VNW'):
            c.args[1] = str(vdd)
        if isinstance(c, L.Group) and c.name == 'operating_conditions':
            c.args = [newname]
            c.set_attr('temperature', str(temp))
            c.set_attr('voltage', str(vdd))
        if isinstance(c, L.Group) and c.name in ('input_voltage', 'output_voltage'):
            for a in ('vih', 'vimax', 'voh', 'vomax'):
                if c.attr(a) is not None:
                    c.set_attr(a, str(vdd))
        if isinstance(c, L.Simple) and c.name == 'default_operating_conditions':
            c.value = newname
    return lib, stats


def cmd_build(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for corner in args.corners.split(','):
        lib, stats = derive(args.cache, corner)
        fn = out / f'{SC}__{corner}.lib'
        with open(fn, 'w') as fh:
            fh.write(f'/* {SC} {corner}: derived by verification/digital_hardening/libchar.py from the PDK '
                     f'tt_025C_3v30 library\n * and ngspice simulation of the PDK cell netlists (model section '
                     f'{CORNERS[corner][0]}, {CORNERS[corner][1]} C, {CORNERS[corner][2]} V).\n'
                     f' * Delay/transition: PDK_tt x sim(corner)/sim(tt); constraints: PDK_tt + sim(corner) - sim(tt).\n'
                     f' * Power/leakage/capacitance: tt values (not for power signoff). */\n')
            L.write(lib, fh)
        summary[corner] = dict(file=str(fn), cells=stats['cells'], tables=stats['tables'], skipped=stats['skipped'])
        print(corner, stats['cells'], 'cells', stats['tables'], 'tables; skipped', len(stats['skipped']))
    (out / 'build-summary.json').write_text(json.dumps(summary, indent=1))


def cmd_run(args):
    lib = load_tt()
    if args.cells == 'used':
        cells = used_cells()
    elif args.cells == 'all':
        cells = timing_cells(lib)
    else:
        cells = args.cells.split(',')
    tcells = set(timing_cells(lib))
    cells = [c for c in cells if c in tcells]
    corners = args.corners.split(',')
    if REF not in corners:
        corners = [REF] + corners
    jobs = [(c, k) for c in cells for k in corners]
    # sequential cells first (longest)
    jobs.sort(key=lambda x: (0 if x[0].startswith(('dff', 'sdff', 'lat', 'icg')) else 1, x[0], x[1]))
    print(f'{len(jobs)} jobs, {args.jobs} workers', flush=True)
    fails = []
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(char_cell, c, k, args.cache): (c, k) for c, k in jobs}
        for n, f in enumerate(as_completed(futs), 1):
            c, k = futs[f]
            try:
                r = f.result()
                print(f'[{n}/{len(jobs)}] {c} {k} {r[2]}', flush=True)
            except Exception as e:  # noqa: BLE001
                fails.append((c, k, str(e)))
                print(f'[{n}/{len(jobs)}] FAIL {c} {k}: {e}', flush=True)
    Path(args.cache, 'failures.json').write_text(json.dumps(fails, indent=1))
    return 1 if fails else 0


def cmd_validate(args):
    """Compare a derived PDK-published corner with the PDK's own library: ss_125C_3v00 by the plain
    ratio method, or ss_n40C_3v00 by the anchored method (anchor ss_125C_3v00), plus harness tt vs PDK tt."""
    corner = args.corner
    pdk = L.parse((LIBDIR / f'{SC}__{corner}.lib').read_text())
    templates = {L.unq(g.args[0]): g for g in pdk.groups('lu_table_template')}
    cells = set(args.cells.split(',')) if args.cells else None
    derived, stats = derive(args.cache, corner, cells=cells, anchored=(corner != 'ss_125C_3v00'))
    errs = dict(delay=[], transition=[], constraint=[])
    per_cell = {}
    for g in derived.groups('cell'):
        name = L.unq(g.args[0])
        pg = pdk.group('cell', name)
        if pg is None or not any(p.groups('timing') for p in g.groups('pin')):
            continue
        ce = []
        for p in g.groups('pin'):
            pp = pg.group('pin', L.unq(p.args[0]))
            pts = pp.groups('timing')
            for i, t in enumerate(p.groups('timing')):
                pt = pts[i]
                for tg in t.groups():
                    if tg.name not in DELAY_TABLES + ('rise_constraint', 'fall_constraint'):
                        continue
                    ptg = pt.group(tg.name)
                    _, _, v = L.table(tg, templates)
                    _, _, w = L.table(ptg, templates)
                    for a, b in zip(sum(v, []), sum(w, [])):
                        if tg.name.startswith('cell'):
                            if b > 0.3:          # relative error is meaningless for near-zero delays
                                errs['delay'].append((a - b) / b)
                                ce.append((a - b) / b)
                        elif 'transition' in tg.name:
                            if b > 0.3:
                                errs['transition'].append((a - b) / b)
                        else:
                            errs['constraint'].append(a - b)
        if ce:
            per_cell[name[len(PRE):]] = dict(mean=sum(ce) / len(ce), max=max(ce), min=min(ce))
    rep = {}
    for k, v in errs.items():
        if not v:
            continue
        v = sorted(v)
        rep[k] = dict(n=len(v), mean=sum(v) / len(v), p05=v[int(0.05 * len(v))], p50=v[len(v) // 2],
                      p95=v[int(0.95 * len(v)) - 1], min=v[0], max=v[-1],
                      unit='relative' if k != 'constraint' else 'ns')
    # harness absolute check at tt: sim delay vs PDK tt table at the subgrid points
    tt = load_tt()
    abs_err = []
    for f in sorted((Path(args.cache) / REF).glob('*.json')):
        j = json.loads(f.read_text())
        if cells and j['cell'] not in cells:
            continue
        g = tt.group('cell', PRE + j['cell'])
        for pin, t in Cell(g, templates, subckt_pins()).arcs():
            a = j['arcs'].get(arc_id(pin, t))
            if not a or a['kind'] != 'delay' or 'alias' in a:
                continue
            for tg in t.groups():
                if tg.name in ('cell_rise', 'cell_fall'):
                    _, _, v = L.table(tg, templates)
                    oe = 'r' if 'rise' in tg.name else 'f'
                    for i in a['s1']:
                        for jj in a['s2']:
                            abs_err.append(a['res'][f'{oe},{i},{jj}'][0] / v[i][jj] - 1)
    abs_err.sort()
    if abs_err:
        rep['harness_tt_abs_delay'] = dict(n=len(abs_err), mean=sum(abs_err) / len(abs_err), p05=abs_err[int(0.05 * len(abs_err))],
                                           p95=abs_err[int(0.95 * len(abs_err)) - 1], unit='relative (sim/PDK - 1)')
    worst = sorted(per_cell.items(), key=lambda kv: -abs(kv[1]['mean']))[:10]
    rep['worst_cells_delay_mean'] = dict(worst)
    rep['cells_compared'] = len(per_cell)
    for k, v in rep.items():
        pass
    out = Path(args.cache) / f'validation-{corner}.json'
    out.write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--cells', default='used')
    r.add_argument('--corners', default='ss_022C_3v15,ss_032C_3v15,ff_022C_3v35,ff_032C_3v35,ss_125C_3v00')
    r.add_argument('--jobs', type=int, default=12)
    r.add_argument('--cache', required=True)
    b = sub.add_parser('build')
    b.add_argument('--cache', required=True)
    b.add_argument('--out', required=True)
    b.add_argument('--corners', default='ss_022C_3v15,ss_032C_3v15,ff_022C_3v35,ff_032C_3v35')
    v = sub.add_parser('validate')
    v.add_argument('--cache', required=True)
    v.add_argument('--cells', default='')
    v.add_argument('--corner', default='ss_125C_3v00')
    a = ap.parse_args()
    sys.exit({'run': cmd_run, 'build': cmd_build, 'validate': cmd_validate}[a.cmd](a) or 0)


if __name__ == '__main__':
    main()
