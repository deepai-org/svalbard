#!/usr/bin/env python3
"""Device-speed calibration structures (scratch/reviews/MANDATE.md, device-speed
guidance; scratch/reviews/gf180-device-speed-evidence.md section 7).

Purpose: the first die measures how fast the GF180 devices really are, so the
second die is sized on silicon numbers instead of the model alone. Every
structure here has an extracted-netlist prediction in its evidence, so the
measured/predicted ratio is the calibration.

Cells (one convkit flow each: layout, Magic DRC, Netgen LVS, analog-image GDS +
KLayout DRC + GDS round-trip LVS, LEF):

  pt_char_ro33  11-stage ring (NAND enable + 10 inverters), nfet_03v3 4/0.28,
                pfet_03v3 8/0.28 (device C dominates the wiring C), on-cell
                TSPC /4, output buffer -> OUT (a CLK_OBS input; CLK_OBS divides
                further by 2^N).  Calibrates 3.3 V CMOS gate delay.
  pt_char_ro50  The same ring with nfet_05v0 4/0.6, pfet_05v0 8/0.5 (the device
                class of the gf180mcu_fd_sc_mcu7t5v0 standard cells), run on
                the 3.3 V rail like the cells; same /4 and buffer.  Calibrates
                the standard-cell device speed (STA derate).
  pt_char_cmldiv  Self-oscillating CML divider: two CML latches in a
                master/slave loop with inversion and CK = CKB = VDD (no input
                clock), nfet_03v3 10/0.28 pairs, ppolyf_u_1k loads, 0.6 mA
                tails; two clocked CML /2 stages bring the rate below 1 GHz,
                a CML-to-CMOS stage and a TSPC /2 give OUT (a CLK_OBS input).
                f_so is set by the NMOS fT and the load RC: it calibrates the
                CML/serializer and LO-divider class directly.  Self-biased from
                a local poly resistor; BIAS is the mirror gate (ATB sense).
  pt_char_rffet nfet_03v3 W = 10 um as 5 fingers of 2 um, L = 0.28 um, gate
                contacted on both ends, in a two-port ground-signal-ground
                probe frame (gate port G-S-G, drain port G-S-G, source = the
                ground frame).  60 x 60 um Metal5 probe pads on a 100 um pitch
                with passivation openings.  On-wafer S-parameters give fT and
                fmax (Rg).  OPEN and SHORT de-embedding frames are separate cells
                (pt_char_rffet_open, pt_char_rffet_short).

All cells: EN = 0 is the safe state (rings stopped, CML tails off, no static
current).  No cell has a pad of its own except the probe frames.

    python3 speed.py sch [cell]        # schematic frequency benches (5 corners)
    python3 speed.py layout [cell]     # physical flow
    python3 speed.py ext [cell]        # extracted benches (5 corners + safe)
    python3 speed.py evidence          # generated/char_speed-evidence.json
"""
import json
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'converters' / 'lib'))
sys.path.insert(0, str(HERE.parent / 'converters'))
import convkit as ck  # noqa: E402
from convkit import Mos, Res, Circuit  # noqa: E402

ROOT = HERE.parents[3]
SCRATCH = ROOT / 'scratch' / 'characterization' / 'speed'
GEN = HERE / 'generated'
CORNERS = [('typical', 27, 3.3), ('ss', 32, 3.15), ('ff', 22, 3.35), ('ss', 22, 3.35), ('ff', 32, 3.15)]

# convkit reads the S/D contact layer as ndiffc/pdiffc; the 5 V PCells use the
# mv* layers.  Alias them (no change to convkit itself, which the converter
# family owns).
_mag_rects = ck.mag_rects


def _mag_rects_mv(path):
    r, p = _mag_rects(path)
    for a in ('ndiffc', 'pdiffc'):
        if a not in r and ('mv' + a) in r:
            r[a] = r['mv' + a]
    return r, p


ck.mag_rects = _mag_rects_mv


# ------------------------------------------------------------------ circuits
class B:
    """Small netlist builder on top of convkit primitives."""

    def __init__(self):
        self.devs = []
        self.k = 0

    def n(self, d, g, s, w=2.0, l=0.28, model='nfet_03v3', b='VSS'):
        self.k += 1
        self.devs.append(Mos(f'N{self.k}', model, w, l, d=d, g=g, s=s, b=b))
        return self.devs[-1].name

    def p(self, d, g, s, w=2.0, l=0.28, model='pfet_03v3', b='VDD'):
        self.k += 1
        self.devs.append(Mos(f'P{self.k}', model, w, l, d=d, g=g, s=s, b=b))
        return self.devs[-1].name

    def r(self, a, b, w, l):
        self.k += 1
        self.devs.append(Res(f'R{self.k}', w, l, a=a, b=b, sub='VSS'))
        return self.devs[-1].name

    def inv(self, a, y, wn=2.0, wp=4.0, ln=0.28, lp=0.28, mn='nfet_03v3', mp='pfet_03v3'):
        return [self.n(y, a, 'VSS', wn, ln, mn), self.p(y, a, 'VDD', wp, lp, mp)]

    def nand2(self, a, b, y, wn=2.0, wp=4.0, ln=0.28, lp=0.28, mn='nfet_03v3', mp='pfet_03v3', tag='x'):
        mid = f'{tag}_m'
        return [self.n(y, a, mid, wn, ln, mn), self.n(mid, b, 'VSS', wn, ln, mn),
                self.p(y, a, 'VDD', wp, lp, mp), self.p(y, b, 'VDD', wp, lp, mp)]

    def nor2(self, a, b, y, tag, wn=2.0, wp=4.0):
        mid = f'{tag}_m'
        return [self.n(y, a, 'VSS', wn), self.n(y, b, 'VSS', wn),
                self.p(mid, a, 'VDD', wp), self.p(y, b, mid, wp)]

    def tspc2(self, ck_, q, tag, rst=None):
        """TSPC positive-edge D flip-flop with QB fed back to D: /2.  Output q.
        rst (high = reset) pulls q low; with the clock held low by the caller
        every node is then driven (no floating dynamic node, no crowbar)."""
        x1, a, b_, x2, x3 = (f'{tag}_{s}' for s in ('x1', 'a', 'b', 'x2', 'x3'))
        d = q
        out = [self.p(x1, d, 'VDD', 2.0), self.p(a, ck_, x1, 2.0), self.n(a, d, 'VSS', 1.0),
               self.p(b_, ck_, 'VDD', 2.0), self.n(b_, a, x2, 2.0), self.n(x2, ck_, 'VSS', 2.0),
               self.p(q, b_, 'VDD', 3.0), self.n(q, ck_, x3, 2.0), self.n(x3, b_, 'VSS', 2.0)]
        if rst:
            out.append(self.n(q, rst, 'VSS', 1.0))
        return out


def rows_of(names, per_row=14):
    return [names[i:i + per_row] for i in range(0, len(names), per_row)]


def paired_rows(names, per_row=12):
    """Device order as built (each gate's NMOS and PMOS adjacent in `names`):
    chunk it and place each chunk as an NMOS row with its PMOS row directly
    above, so most nets stay inside one channel.  Resistors get their own row
    after the chunk they belong to."""
    rows = []
    for i in range(0, len(names), per_row * 2):
        ch = names[i:i + per_row * 2]
        for kind in 'NRP':
            r = [d for d in ch if d.startswith(kind)]
            if r:
                rows.append(r)
    return rows


def ring(cell, mn, mp, ln, lp, wn=4.0, wp=8.0, stages=11):
    """NAND-enabled ring + /4 + buffer.  OUT is low and static while EN = 0
    (the NAND output is high, the dividers hold, the buffer holds)."""
    b = B()
    ring_names = b.nand2('R10' if stages == 11 else f'R{stages - 1}', 'EN', 'R0', wn, wp, ln, lp, mn, mp, tag='en')
    for i in range(1, stages):
        ring_names += b.inv(f'R{i - 1}', f'R{i}', wn, wp, ln, lp, mn, mp)
    # tap: T0 = NOR(R5, ENB) on R5 (mid-ring) -> TSPC /2 /2 -> buffer.  EN = 0
    # holds T0 low and resets both TSPC outputs, so the dividers are static.
    tap = b.inv('EN', 'ENB', 1.0, 2.0) + b.nor2('R5', 'ENB', 'T0', 'tap')
    div = b.tspc2('T0', 'D1', 'd1', 'ENB') + b.tspc2('D1', 'D2', 'd2', 'ENB')
    out = b.inv('D2', 'OB', 2.0, 4.0) + b.inv('OB', 'OUT', 4.0, 8.0)
    names = ring_names + tap + div + out
    rows = paired_rows(names, 12)
    return Circuit(cell, ['EN', 'OUT', 'VDD', 'VSS'], b.devs, rows=rows, wide_nets={'VDD': 2.0, 'VSS': 2.0})


CML = dict(w=10.0, wh=10.0, wck=10.0, rl=(1.0, 1.8))   # 1.8 kohm: 0.8 kohm did not self-oscillate (latch gain < 1); 1.2 kohm oscillated but its swing could not drive the next stage


def cml_latch(b, ck_, ckb, d, db, q, qb, tail_gate, tag, w=None, wh=None, wck=None, rl=None):
    """CML D latch: transparent while CK > CKB.  Q/QB are the load nodes."""
    w = w or CML['w']
    wh = wh or CML['wh']
    wck = wck or CML['wck']
    rl = rl or CML['rl']
    t, a, h = f'{tag}_t', f'{tag}_a', f'{tag}_h'
    return [b.n(t, tail_gate, 'VSS', 10.0, 0.5),               # tail, 0.6 mA (mirror x10 of 60 uA)
            b.n(a, ck_, t, wck), b.n(h, ckb, t, wck),            # clock steering
            b.n(qb, d, a, w), b.n(q, db, a, w),                  # track pair (D high pulls QB low)
            b.n(qb, q, h, wh), b.n(q, qb, h, wh),                # hold pair
            b.r('VDD', q, *rl), b.r('VDD', qb, *rl)]


def cml_div2(b, ck_, ckb, q, qb, tg, tag):
    """Master/slave CML /2: master transparent on CK, slave on CKB, slave output
    fed back inverted to the master input."""
    m, mb = f'{tag}_m', f'{tag}_mb'
    return (cml_latch(b, ck_, ckb, qb, q, m, mb, tg, tag + 'M')
            + cml_latch(b, ckb, ck_, m, mb, q, qb, tg, tag + 'S'))


def cmldiv(cell='pt_char_cmldiv'):
    b = B()
    names = []
    # local bias: EN -> ENB; PMOS switch to a poly resistor into a diode NFET (60 uA nominal);
    # ENB pulls the mirror gate low (tails off) when EN = 0.
    names += b.inv('EN', 'ENB', 1.0, 2.0)
    names += [b.p('BT', 'ENB', 'VDD', 4.0), b.r('BT', 'BIAS', 1.0, 36.0),
              b.n('BIAS', 'BIAS', 'VSS', 1.0, 0.5), b.n('BIAS', 'ENB', 'VSS', 1.0)]
    # stage 0: self-oscillating (CK = CKB = VDD)
    names += cml_div2(b, 'VDD', 'VDD', 'S0', 'S0B', 'BIAS', 's0')
    # stages 1, 2: clocked /2
    names += cml_div2(b, 'S0', 'S0B', 'S1', 'S1B', 'BIAS', 's1')
    names += cml_div2(b, 'S1', 'S1B', 'S2', 'S2B', 'BIAS', 's2')
    # CML -> CMOS: NMOS pair, PMOS mirror load, 0.6 mA tail; then inverters
    names += [b.n('CT', 'BIAS', 'VSS', 10.0, 0.5), b.n('CX', 'S2', 'CT', 10.0), b.n('CY', 'S2B', 'CT', 10.0),
              b.p('CX', 'CX', 'VDD', 8.0), b.p('CY', 'CX', 'VDD', 8.0)]
    names += b.inv('CY', 'C1', 2.0, 4.0) + b.nor2('C1', 'ENB', 'C2', 'cg')
    names += b.tspc2('C2', 'D1', 'd1', 'ENB')
    names += b.inv('D1', 'OB', 2.0, 4.0) + b.inv('OB', 'OUT', 4.0, 8.0)
    rows = paired_rows(names, 12)
    return Circuit(cell, ['EN', 'OUT', 'BIAS', 'VDD', 'VSS'], b.devs, rows=rows, wide_nets={'VDD': 2.0, 'VSS': 2.0})


CELLS = {
    'pt_char_ro33': lambda: ring('pt_char_ro33', 'nfet_03v3', 'pfet_03v3', 0.28, 0.28),
    'pt_char_ro50': lambda: ring('pt_char_ro50', 'nfet_05v0', 'pfet_05v0', 0.6, 0.5),
    'pt_char_cmldiv': cmldiv,
}
# on-cell division ratio from the oscillator to OUT
DIVIDE = {'pt_char_ro33': 4, 'pt_char_ro50': 4, 'pt_char_cmldiv': 8}   # cmldiv: from S0 (toggles at f_so/2 of the equivalent input clock)


# ------------------------------------------------------------------ benches
def header(corner, temp):
    return f'* {corner} {temp}C\n' + ck.models(corner) + f'.temp {temp}\n.option method=gear reltol=1e-3\n'


def deck(cell, inc, corner, temp, vdd, rg=True):
    """Start-up and frequency bench: EN rises at 5 ns; OUT into 50 fF (the
    CLK_OBS mux input and its wire).  For the ring, the osc node frequency is
    also measured directly on R5 (cross-check of the on-cell divider)."""
    T = {'pt_char_ro33': 400e-9, 'pt_char_ro50': 600e-9, 'pt_char_cmldiv': 200e-9}[cell]
    td = T / 2
    ports = CELLS[cell]().ports
    d = header(corner, temp) + f'.include {inc}\nVDD vdd 0 {vdd}\nVEN en 0 pwl(0 0 5n 0 5.1n {vdd})\n'
    d += 'X1 ' + ' '.join({'EN': 'en', 'OUT': 'out', 'BIAS': 'bias', 'VDD': 'vdd', 'VSS': '0'}[p] for p in ports) + f' {cell}\n'
    d += 'CL out 0 50f\n'
    d += f'.tran 5p {T}\n'
    d += f'.measure tran ioff avg i(VDD) from=1n to=4.9n\n'
    d += f'.measure tran per trig v(out) val={vdd / 2} td={td} rise=1 targ v(out) val={vdd / 2} td={td} rise=5\n'
    d += f'.measure tran ion avg i(VDD) from={td} to={T}\n'
    d += f'.measure tran omax max v(out) from={td} to={T}\n.measure tran omin min v(out) from={td} to={T}\n'
    if cell != 'pt_char_cmldiv':
        d += f'.measure tran pr trig v(x1.r5) val={vdd / 2} td={td} rise=1 targ v(x1.r5) val={vdd / 2} td={td} rise=21\n'
    else:
        # a perfectly symmetric netlist starts at its metastable point (silicon
        # starts from noise): .ic offsets S0/S0B by 0.2 V, released at t = 0
        d += f'.ic v(x1.s0)={vdd} v(x1.s0b)={vdd - 0.2}\n'
        d += (f'.measure tran ps0 trig v(x1.s0) val={vdd - 0.4} td={td} rise=1 targ v(x1.s0) val={vdd - 0.4} td={td} rise=21\n'
              f'.measure tran s0max max v(x1.s0) from={td} to={T}\n.measure tran s0min min v(x1.s0) from={td} to={T}\n'
              f'.measure tran vbias avg v(bias) from={td} to={T}\n')
    return d + '.end\n'


def run(work, name, text):
    work.mkdir(parents=True, exist_ok=True)
    ck.ngspice(work, name + '.spice', text)
    log = (work / (name + '.spice.log')).read_text(errors='replace')
    m = {g.group(1): float(g.group(2)) for g in re.finditer(r'^\s*([a-z_0-9]+)\s*=\s*([-+0-9.eE]+)', log, re.M)}
    m['_errors'] = [l.strip() for l in log.splitlines() if l.lower().startswith('error') or 'failed' in l.lower()][:5]
    return m


def analyse(cell, m, vdd):
    f_out = 4 / m['per'] if m.get('per') else None
    r = dict(f_out_hz=f_out, divide=DIVIDE[cell], f_osc_hz=(f_out * DIVIDE[cell] if f_out else None),
             i_on_ma=-m.get('ion', float('nan')) * 1e3, i_off_ua=-m.get('ioff', float('nan')) * 1e6,
             out_v=[m.get('omin'), m.get('omax')], sim_messages=m['_errors'])
    if 'pr' in m:
        r['f_ring_direct_hz'] = 20 / m['pr']
    if 'ps0' in m:
        r['f_s0_direct_hz'] = 20 / m['ps0']   # S0 toggles at f_so (the latch-loop oscillation)
        r['s0_swing_v'] = [m.get('s0min'), m.get('s0max')]
        r['v_bias'] = m.get('vbias')
    # divider consistency: the on-cell /N output must equal the directly measured
    # oscillator frequency / N within 1 % (otherwise a divider is missing edges)
    direct = r.get('f_ring_direct_hz') or (r.get('f_s0_direct_hz') and r['f_s0_direct_hz'] / 2)
    # (S0 toggles at f_so/2 of the self-oscillation 'clock'; OUT = S0 / 8)
    if cell == 'pt_char_cmldiv' and r.get('f_out_hz'):
        r['f_so_equivalent_clock_hz'] = 16 * r['f_out_hz']
    if cell == 'pt_char_cmldiv' and r.get('f_s0_direct_hz'):
        r['f_osc_hz'] = r['f_s0_direct_hz']
        r['f_so_equivalent_clock_hz'] = 2 * r['f_s0_direct_hz']
        direct_out = r['f_s0_direct_hz'] / 8
    else:
        direct_out = direct / DIVIDE[cell] if direct else None
    r['divider_consistent'] = bool(f_out and direct_out and abs(f_out / direct_out - 1) < 0.01)
    r['out_full_swing'] = bool(m.get('omax') is not None and m['omax'] > 0.9 * vdd and m['omin'] < 0.1 * vdd)
    r['f_out_clk_obs_ok'] = bool(f_out and f_out <= 500e6)       # clk_obs passes 500 MHz (README)
    r['pass'] = bool(r['divider_consistent'] and r['out_full_swing'] and r['f_out_clk_obs_ok'] and r['i_off_ua'] < 1.0)
    return r


def sch(cells):
    work = SCRATCH / 'sch'
    work.mkdir(parents=True, exist_ok=True)
    out = {}
    jobs = []
    for cell in cells:
        (work / f'{cell}.spice').write_text(CELLS[cell]().spice(include_macros=False))
        for c, t, v in CORNERS[:1]:     # schematic: tt only (divider check); corners run extracted
            jobs.append((cell, c, t, v))

    def one(j):
        cell, c, t, v = j
        m = run(work, f'{cell}_{c}_{t}_{v}', deck(cell, f'{cell}.spice', c, t, v))
        return j, analyse(cell, m, v)
    with ThreadPoolExecutor(1) as ex:
        for (cell, c, t, v), r in ex.map(one, jobs):
            out.setdefault(cell, {})[f'{c}_{t}_{v}'] = r
            print(cell, c, t, v, json.dumps({k: r.get(k) for k in ('f_osc_hz', 'f_out_hz', 'i_on_ma', 'i_off_ua', 'divider_consistent', 'pass')}), flush=True)
    save('schematic', out)
    return out


RSH_POLY = 7.3     # ohm/sq, gate poly (gf180mcuD.tech extract estimate; see lcvco/qvco.spice)


def with_gate_r(netlist_text):
    """Explicit gate resistance (the PDK models have rgatemod = 0): every MOS
    instance gets Rg = Rsh * W / (3 L) in series with its gate (single finger,
    gate contacted at one end, as the convkit PCells are drawn)."""
    out = []
    k = 0
    for line in netlist_text.splitlines():
        f = line.split()
        if f and f[0][0] in 'Xx' and len(f) > 5 and re.match(r'[np]fet_0[35]v[03]', f[5]):
            w = float(re.search(r'\bw=([\d.]+)u', line).group(1))
            l = float(re.search(r'\bl=([\d.]+)u', line).group(1))
            k += 1
            g = f[2]
            f[2] = f'rg_{k}'
            out.append(' '.join(f))
            out.append(f'RRG{k} {g} rg_{k} {RSH_POLY * w / (3 * l):.2f}')
        else:
            out.append(line)
    return '\n'.join(out) + '\n'


def ext(cells, rg=True):
    work = SCRATCH / ('ext_rg' if rg else 'ext')
    work.mkdir(parents=True, exist_ok=True)
    out = {}
    jobs = []
    for cell in cells:
        txt = (GEN / f'{cell[3:]}.ext.spice').read_text()
        (work / f'{cell}.ext.spice').write_text(with_gate_r(txt) if rg else txt)
        for c, t, v in (CORNERS if rg else CORNERS[:1]):
            jobs.append((cell, c, t, v))

    def one(j):
        cell, c, t, v = j
        m = run(work, f'{cell}_{c}_{t}_{v}', deck(cell, f'{cell}.ext.spice', c, t, v))
        return j, analyse(cell, m, v)
    with ThreadPoolExecutor(1) as ex:
        for (cell, c, t, v), r in ex.map(one, jobs):
            r.update(netlist='extracted (Magic C) + explicit gate R' if rg else 'extracted (Magic C), no gate R')
            out.setdefault(cell, {})[f'{c}_{t}_{v}'] = r
            print(cell, c, t, v, json.dumps({k: r.get(k) for k in ('f_osc_hz', 'f_out_hz', 'i_on_ma', 'i_off_ua', 'divider_consistent', 'pass')}), flush=True)
    save('extracted_rg' if rg else 'extracted_norg', out)
    return out


def save(key, d):
    p = SCRATCH / 'results.json'
    res = json.loads(p.read_text()) if p.exists() else {}
    for cell, v in d.items():
        res.setdefault(key, {}).setdefault(cell, {}).update(v)
    p.write_text(json.dumps(res, indent=1, default=str) + '\n')


LEF_TCL = '''crashbackups stop
load {cell}
select top cell
lef write {cell}.lef -hide
quit -noprompt
'''


def layout(cell):
    import flow as convflow   # converters/flow.py: export_gds (read-only use)
    c = CELLS[cell]()
    work = SCRATCH / 'layout' / cell
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sch_txt = c.spice(include_macros=False)
    (HERE / f'{cell}.spice').write_text('* generated by speed.py; do not edit\n' + sch_txt)
    L = ck.Layout(c, work).build()
    L.write()
    (work / f'{cell}.lvs_sch.spice').write_text(sch_txt)
    res = ck.lvs(work, f'{cell}.lvs.spice', cell, f'{cell}.lvs_sch.spice', cell)
    gx = convflow.export_gds(work, c)
    (work / 'lef.tcl').write_text(LEF_TCL.format(cell=cell))
    r = ck.docker(ck.DIGITAL_IMAGE, work, f'magic -dnull -noconsole -rcfile {ck.PDK}/libs.tech/magic/gf180mcuD.magicrc /work/lef.tcl')
    (work / 'lef.log').write_text(r.stdout + r.stderr)
    GEN.mkdir(exist_ok=True)
    short = cell.replace('pt_', '')
    for src, dst in [(f'{cell}.gds', f'{short}.gds'), (f'{cell}.ext.spice', f'{short}.ext.spice'),
                     (f'{cell}.lvs.spice', f'{short}.lvs.spice'), ('lvs.txt', f'{short}-lvs.txt'),
                     (f'{cell}.lef', f'{short}.lef'), (f'{cell}_flat.mag', f'{short}.mag')]:
        if (work / src).exists():
            shutil.copy(work / src, GEN / dst)
    (GEN / f'{short}-drc.txt').write_text((work / 'drc-count.txt').read_text() + (work / 'drc-details.txt').read_text())
    if (work / 'klayout-drc.lyrdb').exists():
        shutil.copy(work / 'klayout-drc.lyrdb', GEN / f'{short}-klayout-drc.lyrdb')
    lef = (GEN / f'{short}.lef').read_text() if (GEN / f'{short}.lef').exists() else ''
    lef_pins = sorted(set(re.findall(r'^\s*PIN (\S+)', lef, re.M)))
    info = dict(L.report, lvs=res['final'], lvs_unique=res['match_unique'], gds_export=gx,
                lef_pins=lef_pins, lef_pins_match_ports=lef_pins == sorted(c.ports),
                devices=sum(len(d.units()) for d in c.devices))
    info['gds_subcells_uniquified'] = uniquify(GEN / f'{short}.gds')
    info['published_gds_after_rename'] = verify_gds(GEN / f'{short}.gds', cell, work / f'{cell}.lvs_sch.spice')
    (GEN / f'{short}-physical.json').write_text(json.dumps(info, indent=1, default=str) + '\n')
    print(cell, 'drc', info.get('drc_count'), 'lvs', res['final'], 'klayout', (gx.get('klayout_drc') or {}).get('violations'),
          'rt', gx.get('published_gds_lvs_unique'), 'lef', info['lef_pins_match_ports'], flush=True)
    return info


UNIQ_PY = r'''
import sys, json
try:
    import klayout.db as db
except ImportError:
    import pya as db
try:
    src, dst = SRC, DST          # klayout -b -rd SRC=... -rd DST=...
except NameError:
    src, dst = sys.argv[1], sys.argv[2]
ly = db.Layout(); ly.read(src)
top = ly.top_cell()
ren = {}
for c in ly.each_cell():
    if c.cell_index() != top.cell_index() and not c.name.startswith(top.name + '__'):
        old = c.name
        c.name = top.name + '__' + old
        ren[old] = c.name
ly.write(dst)
print(json.dumps(dict(top=top.name, renamed=ren)))
'''


def uniquify(gds):
    """Prefix every subcell of a published GDS with its top-cell name.  The
    convkit flow names PCell masters prim_0, prim_1, ... in every block, so two
    blocks merged naively would silently share one (different) master."""
    gds = Path(gds)
    work = gds.parent
    (work / '_uniq.py').write_text(UNIQ_PY)
    r = ck.docker(ck.ANALOG_IMAGE, work, f'export PATH=/foss/tools/bin:/foss/tools/klayout:$PATH; '
                  f'python3 _uniq.py {gds.name} u_{gds.name} 2>/dev/null || klayout -b -rd SRC={gds.name} -rd DST=u_{gds.name} -r _uniq.py',
                  entry='/bin/bash')
    out = work / ('u_' + gds.name)
    if not out.exists():
        raise RuntimeError(r.stdout + r.stderr)
    out.replace(gds)
    (work / '_uniq.py').unlink()
    return json.loads(r.stdout.strip().splitlines()[-1])


RT_TCL = """crashbackups stop
gds read {gds}
load {cell}
extract all
ext2spice lvs
ext2spice -o {cell}.gdsrt.spice
quit -noprompt
"""


def verify_gds(gds, cell, sch):
    """Round-trip LVS of the published (renamed) GDS against the schematic."""
    gds = Path(gds)
    work = SCRATCH / 'verify' / cell
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copy(gds, work / gds.name)
    shutil.copy(sch, work / 'sch.spice')
    (work / 'rt.tcl').write_text(RT_TCL.format(gds=gds.name, cell=cell))
    r = ck.docker(ck.ANALOG_IMAGE, work, 'export PATH=/foss/tools/bin:$PATH; export PDK=gf180mcuD PDKPATH=/foss/pdks/gf180mcuD; '
                  'magic -dnull -noconsole -rcfile $PDKPATH/libs.tech/magic/gf180mcuD.magicrc rt.tcl', entry='/bin/bash')
    (work / 'rt.log').write_text(r.stdout + r.stderr)
    res = ck.lvs(work, f'{cell}.gdsrt.spice', cell, 'sch.spice', cell)
    return dict(gds_sha256=ck.sha256(gds), lvs=res['final'], lvs_unique=res['match_unique'])


def evidence():
    res = json.loads((SCRATCH / 'results.json').read_text())
    rec = dict(block='device-speed calibration structures', generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               source_hashes={p.name: ck.sha256(p) for p in (Path(__file__), HERE / 'rffet.py', HERE.parent / 'converters' / 'lib' / 'convkit.py')},
               criteria=dict(functional='extracted netlist + explicit gate R, 5 corners (tt/27/3.3, ss/32/3.15, ff/22/3.35, ss/22/3.35, ff/32/3.15): '
                                        'OUT toggles rail to rail (>90 %/<10 % VDD), f_out <= 500 MHz (clk_obs limit), EN=0 supply current < 1 uA',
                             divider='schematic tt: f(OUT) = f(oscillator node)/N within 1 %',
                             clean='Magic DRC 0, KLayout DRC 0, LVS unique, published-GDS (renamed) round-trip LVS unique, LEF pins = ports'),
               cells={})
    for cell in CELLS:
        short = cell[3:]
        phys = json.loads((GEN / f'{short}-physical.json').read_text())
        ext_rg = res.get('extracted_rg', {}).get(cell, {})
        ext_no = res.get('extracted_norg', {}).get(cell, {})
        sch_ = res.get('schematic', {}).get(cell, {})
        clean = bool(phys.get('drc_count') == 0 and phys.get('lvs_unique') and phys['gds_export']['klayout_drc']['violations'] == 0
                     and phys['gds_export'].get('published_gds_lvs_unique') and phys.get('lef_pins_match_ports')
                     and (phys.get('published_gds_after_rename') or {}).get('lvs_unique'))
        func = bool(len(ext_rg) == len(CORNERS) and all(r.get('pass') for r in ext_rg.values()))
        div = bool(sch_) and all(r.get('divider_consistent') for r in sch_.values())
        rec['cells'][cell] = dict(
            clean=clean, functional_extracted_rg=func, divider_consistent_schematic=div,
            prediction_f_osc_hz={k: r.get('f_osc_hz') for k, r in ext_rg.items()},
            prediction_f_out_hz={k: r.get('f_out_hz') for k, r in ext_rg.items()},
            i_on_ma={k: r.get('i_on_ma') for k, r in ext_rg.items()},
            i_off_ua={k: r.get('i_off_ua') for k, r in ext_rg.items()},
            no_gate_r_tt_f_osc_hz={k: r.get('f_osc_hz') for k, r in ext_no.items()},
            schematic_tt=sch_, extracted_rg=ext_rg, physical=phys,
            verdict='pass' if (clean and func and div) else 'fail')
    rf = json.loads((GEN / 'char_rffet-physical.json').read_text())
    rec['cells']['pt_char_rffet'] = dict(physical=rf, verdict='pass' if (
        all(rf[c]['magic_drc'] == 0 and rf[c]['gds_export']['klayout_drc']['violations'] == 0 for c in rf)
        and rf['pt_char_rffet']['lvs_unique'] and rf['pt_char_rffet']['published_gds_after_rename']['lvs_unique']
        and rf['pt_char_rffet_open']['extracted_ports'] == ['G', 'D', 'GND'] and rf['pt_char_rffet_short']['extracted_ports'] == ['GND'])
        else 'fail', prediction='fT/fmax from the model: gf180-device-speed-evidence.md E4/E5 (ss/32: fT 17.1-17.5 GHz, '
                                'fmax 37.5 GHz at Rg 150 ohm); this structure measures them')
    rec['observable'] = 'open: CLK_OBS source codes, EN bits and the BIAS ATB code are requested in scratch/reviews/interface-changes.md'
    (GEN / 'char_speed-evidence.json').write_text(json.dumps(rec, indent=1, default=str) + '\n')
    print({c: v.get('verdict') for c, v in rec['cells'].items()})


if __name__ == '__main__':
    what = sys.argv[1]
    cells = sys.argv[2].split(',') if len(sys.argv) > 2 else list(CELLS)
    if what == 'netlist':
        for c in cells:
            print(CELLS[c]().spice(include_macros=False))
    elif what == 'sch':
        sch(cells)
    elif what == 'layout':
        for c in cells:
            layout(c)
    elif what == 'evidence':
        evidence()
    elif what == 'ext':
        ext(cells, rg=True)
    elif what == 'ext_norg':
        ext(cells, rg=False)
