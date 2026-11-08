"""pt_wrx_cap: wired-RX fast 1:N capture front end (slot demultiplexer), built from compact rows.

Rows are compiled with wrx_compact (a copy of analog/timing/compact.py with gap-track sharing); the
TSPC flop, NAND and helper column patterns are timing's (fastcells._tspc_cols).

Function (one ring cycle = CKP0 period T; CK = CKP0 gated by EN, CKN = !CK, low when disabled):
  * front (wc_front): sampler output S_j (latched by pt_slicer at phase j, valid one period) is first
    captured by the opposite ring phase CKP(j+4) (half a period after its own sampling clock, so the
    capture is independent of the slicer delay), then aligned:
        j=0     : CK rise -> CK rise          j=1..4: CK fall -> CK rise          j=5..7: CK rise
    so the octet O0..O7 of ring cycle m is valid for one period from the CK rise two cycles later.
  * lanes (wc_lane): DL0..3 / EL0..3 by mode (one-hot BQ/BH/BF):
        quarter: DLj = O(2j), ELj = O(2j+1)
        half   : DL0=DL2=O0, DL1=DL3=O4; EL0=EL2=O2, EL1=EL3=O6
        full   : every DLj = O[psel], ELj = O[psel+4]  (psel one-hot PS0..7, shadowed at the word load)
  * slot counter (wc_cnt): self-starting /5 core (slot 0..4) with T (/10) and U (/20) index bits,
    restarted once per word by LDE re-registered on CK.
  * slots (wc_slot0/1 enables, wc_pair x20): bit pair i (DW_i, EW_i) takes lane i mod 4; its slot
    enable (see slot()) is registered on CK rise and gates CKN (GCK_i), so the two slot flops R
    clock once per word.
  * word: pair 19 is in the last slot in every mode; its registered enable, re-registered on CK rise,
    gates CKN (GW): the word flops W take all R in the CK-low half after the last slot, half a period
    before slot 0 of the next word.  DW/EW are buffered W outputs, stable for one word.
  * slip (full rate): SLIPP/SLIPM and the one-hot phase select are shadowed at GW; the slip of the
    word being captured is presented as SLP/SLM with that word at the next GW.
EN=0: CK/CKN low, every flop reset (outputs 0), inputs only see gate loads.
"""
from pathlib import Path
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'timing'))
sys.path.insert(0, str(HERE))
import wrx_compact as compact                     # noqa: E402
import layout_engine as le                        # noqa: E402
import fastcells as fc                            # noqa: E402

C, G, BRK, fet = fc.C, fc.G, fc.BRK, fc.fet
S_ = C('VSS', 'VDD', same=False)
FAST = HERE / 'generated' / 'fast'
SCRATCH = HERE.parents[3] / 'scratch' / 'wired_rx' / 'cap'


class Cell:
    def __init__(self, name):
        self.name, self.cols, self.net, self.k = name, [], [], 0

    def _add(self, cols, net):
        if self.cols:
            self.cols.append(BRK)
        self.cols += cols
        self.net += net

    def pre(self):
        self.k += 1
        return f'u{self.k}_'

    def inv(self, a, y, wn=2, wp=4):
        p = self.pre()
        self._add([S_, G(a, wn, wp), C(y)], [fet(p + 'n', y, a, 'VSS', 'VSS', wn), fet(p + 'p', y, a, 'VDD', 'VDD', wp, 'p')])

    def buf(self, a, y, mid=None):
        mid = mid or f'{y}_b'
        self.inv(a, mid, 1, 2)
        self.inv(mid, y, 2, 4)

    def nand(self, ins, y, wn=None, wp=2):
        p = self.pre()
        n = len(ins)
        wn = wn or {1: 2, 2: 2, 3: 3, 4: 4}[n]
        cols = [S_]
        net = []
        for k, a in enumerate(ins):
            cols.append(G(a, wn, wp))
            last = k == n - 1
            pnet = 'VDD' if k % 2 else y
            if last:
                cols.append(C(y, 'VDD' if (k + 1) % 2 == 0 else y, same=False))
            else:
                cols.append(dict(k='c', n=None, p=pnet))
            d = y if last else f'{p}m{k}'
            s = 'VSS' if k == 0 else f'{p}m{k - 1}'
            net += [fet(f'{p}n{k}', d, a, s, 'VSS', wn), fet(f'{p}p{k}', y, a, 'VDD', 'VDD', wp, 'p')]
        self._add(cols, net)

    def nor2(self, a, b, y, wn=2, wp=4):
        p = self.pre()
        cols = [S_, G(a, wn, wp), dict(k='c', n=y, p=None), G(b, wn, wp), C('VSS', y, same=False)]
        net = [fet(p + 'n1', y, a, 'VSS', 'VSS', wn), fet(p + 'n2', y, b, 'VSS', 'VSS', wn),
               fet(p + 'p1', p + 'm', a, 'VDD', 'VDD', wp, 'p'), fet(p + 'p2', y, b, p + 'm', 'VDD', wp, 'p')]
        self._add(cols, net)

    def ff(self, ck, d, q):
        """TSPC D flip-flop (rising ck), Q = NOR(QB, ENB) (timing's ct_tspcd pattern)."""
        p = self.pre()
        cols, net = fc._tspc_cols(ck, d, q, p + 'QB', p + 'X', p + 'Y', p)
        self._add(cols, net)

    def aoi3(self, pairs, y):
        """y = a0&b0 | a1&b1 | a2&b2 (NAND2 x3 -> NAND3)."""
        zs = []
        for a, b in pairs:
            z = f'{y}_z{len(zs)}'
            self.nand([a, b], z)
            zs.append(z)
        self.nand(zs, y)

    def row(self, ports, track_order=None):
        r = compact.Row(self.name, self.cols, ports=ports, wn=2, wp=4)
        if track_order:
            r.track_order = track_order
        return r, ports + ['VDD', 'VSS'], self.net


# ----------------------------------------------------------------------------------------- cells
def pair():
    """Bit pair i: two slot flops on the pair's gated clock GCK (one pulse per word, from wc_slot), two
    word flops on GW.  No ring-rate clock reaches the pairs."""
    c = Cell('wc_pair')
    c.buf('GCK', 'GCL')
    c.ff('GCL', 'DLN', 'RD')
    c.ff('GCL', 'ELN', 'RE')
    c.buf('GW', 'GWL')
    c.ff('GWL', 'RD', 'DW')            # word outputs: static NOR output stage of the TSPC flop
    c.ff('GWL', 'RE', 'EW')
    ports = ['GCK', 'GW', 'DLN', 'ELN', 'ENB', 'DW', 'EW']
    return c.row(ports)


def cnt():
    """Slot counter: self-starting /5 core (abc 100 -> 110 -> 011 -> 001 -> 000 = slot 0..4) with T (/10)
    and U (/20) index bits, restarted to slot 0 / T=U=0 by INJ (LDE re-registered, once per word)."""
    c = Cell('wc_cnt')
    c.buf('CK', 'CKL')
    c.buf('CK', 'CKM')
    c.ff('CKM', 'LDE', 'INJ')
    c.inv('INJ', 'INJB', 1, 2)
    c.nor2('QB_', 'QC_', 'NBC', 1, 2)
    c.inv('NBC', 'ORBC', 1, 2)
    c.nand(['INJB', 'ORBC'], 'AN')             # a <= INJ | NOR(b, c)
    c.nand(['QA_', 'INJB'], 'BNB')
    c.inv('BNB', 'BN', 1, 2)                   # b <= a & !INJ
    c.nand(['QB_', 'INJB'], 'CNB')
    c.inv('CNB', 'CN', 1, 2)                   # c <= b & !INJ
    c.nor2('QA_', 'QC_', 'S4', 1, 2)           # slot 4 (000)
    c.inv('S4', 'S4B', 1, 2)
    c.inv('QT_', 'TB', 1, 2)
    c.nand(['QT_', 'S4B'], 'TX1')
    c.nand(['TB', 'S4'], 'TX2')
    c.nand(['TX1', 'TX2'], 'TXR')              # T ^ S4
    c.nand(['INJB', 'TXR'], 'TNB')
    c.inv('TNB', 'TN', 1, 2)                   # T <= !INJ & (T ^ S4)
    c.nand(['S4', 'QT_'], 'S4TB')
    c.inv('S4TB', 'S4T', 1, 2)
    c.inv('QU_', 'UB', 1, 2)
    c.nand(['QU_', 'S4TB'], 'UX1')
    c.nand(['UB', 'S4T'], 'UX2')
    c.nand(['UX1', 'UX2'], 'UXR')
    c.nand(['INJB', 'UXR'], 'UNB')
    c.inv('UNB', 'UN', 1, 2)                   # U <= !INJ & (U ^ (S4 & T))
    c.ff('CKL', 'AN', 'QA_')
    c.ff('CKL', 'BN', 'QB_')
    c.ff('CKL', 'CN', 'QC_')
    c.ff('CKM', 'TN', 'QT_')
    c.ff('CKM', 'UN', 'QU_')
    # slot one-hot and index outputs for the decoders
    c.inv('QB_', 'BB', 1, 2)
    c.inv('QA_', 'AB', 1, 2)
    c.nand(['QA_', 'BB'], 'S0B')
    c.inv('S0B', 'SL0', 2, 4)                  # 100
    c.nand(['QA_', 'QB_'], 'S1B')
    c.inv('S1B', 'SL1', 2, 4)                  # 110
    c.nand(['QB_', 'QC_'], 'S2B')
    c.inv('S2B', 'SL2', 2, 4)                  # 011
    c.nand(['BB', 'QC_'], 'S3B')
    c.inv('S3B', 'SL3', 2, 4)                  # 001
    c.inv('S4B', 'SL4', 2, 4)                  # 000
    c.buf('QT_', 'TT')
    c.inv('QT_', 'TF', 2, 4)
    c.buf('QU_', 'UT')
    c.inv('QU_', 'UF', 2, 4)
    ports = ['CK', 'ENB', 'LDE', 'SL0', 'SL1', 'SL2', 'SL3', 'SL4', 'TT', 'TF', 'UT', 'UF']
    return c.row(ports)


def slot(half):
    """Slot enables, registers and clock gates for pairs 10*half .. 10*half+9:
    E_i = BQ & SL(i/4) | BH & SL((i/2)%5) & T==(i/10) | BF & SL(i%5) & T==((i/5)%2) & U==(i/10),
    registered on CK rise (ELQ_i), GCK_i = CKN & ELQ_i (one pulse per word, at the CK fall)."""
    c = Cell(f'wc_slot{half}')
    used = []
    c.buf('CK', 'CKL0')
    c.buf('CKN', 'CNL0')
    for i in range(10 * half, 10 * half + 10):
        if i % 5 == 0 and i % 10:
            c.buf('CK', 'CKL1')
            c.buf('CKN', 'CNL1')
        ck, cn = ('CKL1', 'CNL1') if i % 10 >= 5 else ('CKL0', 'CNL0')
        h = i // 2
        tq = f'SL{i // 4}'
        th = [f'SL{h % 5}', 'TT' if h // 5 else 'TF']
        tf_ = [f'SL{i % 5}', 'TT' if (i // 5) % 2 else 'TF', 'UT' if i // 10 else 'UF']
        c.nand(['BQ', tq], f'E{i}_q')
        c.nand(['BH'] + th, f'E{i}_h')
        c.nand(['BF'] + tf_, f'E{i}_f')
        c.nand([f'E{i}_q', f'E{i}_h', f'E{i}_f'], f'E{i}')
        q = 'ELQ19' if i == 19 else f'ELQ{i}'
        c.ff(ck, f'E{i}', q)
        c.nand([cn, q], f'G{i}B')
        c.inv(f'G{i}B', f'GCK{i}', 2, 4)
        for t in [tq] + th + tf_:
            if t not in used:
                used.append(t)
    ports = ['CK', 'CKN', 'ENB', 'BQ', 'BH', 'BF'] + sorted(used) + [f'GCK{i}' for i in range(10 * half, 10 * half + 10)] + \
        (['ELQ19'] if half else [])
    return c.row(ports)


def ctl():
    """Clock generation (EN gating), reset buffer, word-load gate GW, one-hot phase select and slip
    shadow registers, slip outputs, mode one-hot."""
    c = Cell('wc_ctl')
    c.inv('EN', 'ENB0', 2, 4)
    c.inv('ENB0', 'ENX', 2, 4)
    c.inv('ENX', 'ENB', 4, 8)
    c.inv('ENX', 'ENB', 4, 8)
    c.nand(['CKP0', 'EN'], 'CKG')
    c.inv('CKG', 'CKA', 2, 4)
    c.inv('CKA', 'CKAB', 4, 8)
    c.inv('CKAB', 'CK', 4, 8)
    c.inv('CKAB', 'CK', 4, 8)
    c.nor2('CKA', 'ENB', 'CKNA')
    c.inv('CKNA', 'CKNB', 4, 8)
    c.inv('CKNB', 'CKN', 4, 8)
    c.inv('CKNB', 'CKN', 4, 8)
    # word load gate: ELQ19 (pair 19 = last slot in every mode) re-registered on CK fall gates CK, so
    # the word flops load at the CK rise after the last slot capture (half a period either side)
    c.buf('CKN', 'CNL')
    c.ff('CNL', 'ELQ19', 'ELW')
    c.nand(['CK', 'ELW'], 'GWB')
    c.inv('GWB', 'GW0', 2, 4)
    c.inv('GW0', 'GWX', 2, 4)
    c.inv('GWX', 'GW', 4, 8)
    c.inv('GWX', 'GW', 4, 8)
    c.buf('GW', 'GWL')
    # phase-select / slip shadow clock: the last slot's own capture edge (CK fall), so the lanes have a
    # full period to settle before slot 0 of the next word
    c.nand(['CKN', 'ELQ19'], 'GPB')
    c.inv('GPB', 'GP0', 3, 6)
    for b in range(3):
        c.inv(f'PSEL{b}', f'PN{b}', 1, 2)
    for k in range(8):
        bits = [(f'PSEL{b}' if (k >> b) & 1 else f'PN{b}') for b in range(3)]
        c.nand(bits, f'PD{k}B')
        c.inv(f'PD{k}B', f'PD{k}', 1, 2)
        if k % 4 == 0:
            c.buf('GP0', f'GPL{k // 4}')
        c.ff(f'GPL{k // 4}', f'PD{k}', f'PS{k}')
    c.buf('GP0', 'GPL2')
    c.ff('GPL2', 'SLIPP', 'SPQ')        # slip of the word now starting
    c.ff('GPL2', 'SLIPM', 'SMQ')
    c.ff('GPL2', 'SPQ', 'SPQ2')         # ... of the word now completing
    c.ff('GPL2', 'SMQ', 'SMQ2')
    c.ff('GWL', 'SPQ2', 'SLP')         # presented with that word
    c.ff('GWL', 'SMQ2', 'SLM')
    # mode one-hot
    c.nor2('B2', 'B1', 'BQ', 2, 4)
    c.buf('B2', 'BH')
    c.buf('B1', 'BF')
    ports = ['EN', 'CKP0', 'ELQ19', 'PSEL0', 'PSEL1', 'PSEL2', 'SLIPP', 'SLIPM', 'B2', 'B1',
             'ENB', 'CK', 'CKN', 'GW', 'BQ', 'BH', 'BF', 'SLP', 'SLM'] + [f'PS{k}' for k in range(8)]
    return c.row(ports)


def front():
    c = Cell('wc_front')
    for j in range(8):
        c.buf(f'CKP{(j + 4) % 8}', f'PC{j}')
        c.ff(f'PC{j}', f'S{j}', f'F{j}')
    # align stages on locally buffered CKP0 / CKP4 (same buffer as stage 1: margins independent of
    # the global CK tree delay)
    c.buf('CKP0', 'CKF1')
    c.buf('CKP4', 'CNF')
    c.ff('CKF1', 'F0', 'A0')
    c.ff('CKF1', 'A0', 'O0')
    c.buf('CKP0', 'CKF2')
    for j in range(1, 5):
        c.ff('CNF', f'F{j}', f'B{j}')
        c.ff('CKF2', f'B{j}', f'O{j}')
    c.buf('CKP0', 'CKF3')
    for j in range(5, 8):
        c.ff('CKF3', f'F{j}', f'O{j}')
    c.buf('CKP0', 'CKF4')                 # TSPC flops need sharp clock edges: <= 4 flops per local buffer
    for j in range(4, 8):                 # previous cycle's phases 4..7 (full-rate data, psel 4..7)
        c.ff('CKF4', f'O{j}', f'OP{j}')
    ports = [f'CKP{k}' for k in range(8)] + [f'S{j}' for j in range(8)] + ['ENB'] + [f'O{j}' for j in range(8)] + \
        [f'OP{j}' for j in range(4, 8)]
    return c.row(ports)


def lane():
    c = Cell('wc_lane')
    # full-rate 8:1 selections DF = O[psel], EF = O[psel+4]
    for nm, off in (('DF', 0), ('EF', 4)):
        zs = []
        for k in range(8):
            z = f'{nm}z{k}'
            # data for psel 4..7 from the previous cycle (OP), so the edge (psel+4) lies after it
            src = f'OP{k}' if (off == 0 and k >= 4) else f'O{(k + off) % 8}'
            c.nand([f'PS{k}', src], z)
            zs.append(z)
        c.nand(zs[:4], f'{nm}a')
        c.nand(zs[4:], f'{nm}b')
        c.inv(f'{nm}a', f'{nm}an', 1, 2)
        c.inv(f'{nm}b', f'{nm}bn', 1, 2)
        c.nand([f'{nm}an', f'{nm}bn'], nm)
    for j in range(4):
        c.aoi3([('BQ', f'O{2 * j}'), ('BH', 'O0' if j % 2 == 0 else 'O4'), ('BF', 'DF')], f'DL{j}')
        c.aoi3([('BQ', f'O{2 * j + 1}'), ('BH', 'O2' if j % 2 == 0 else 'O6'), ('BF', 'EF')], f'EL{j}')
    ports = [f'O{j}' for j in range(8)] + [f'OP{j}' for j in range(4, 8)] + [f'PS{k}' for k in range(8)] + ['BQ', 'BH', 'BF'] + \
        [f'DL{j}' for j in range(4)] + [f'EL{j}' for j in range(4)]
    return c.row(ports)


CELLS = dict(wc_pair=pair, wc_cnt=cnt, wc_slot0=lambda: slot(0), wc_slot1=lambda: slot(1),
             wc_ctl=ctl, wc_front=front, wc_lane=lane)


def subckt(name, ports, net):
    return f'.subckt {name} {" ".join(ports)}\n' + '\n'.join(net) + f'\n.ends {name}\n'


def build_cell(name):
    row, ports, net = CELLS[name]()
    row.build()
    work = SCRATCH / 'cells' / name
    if work.exists():
        shutil.rmtree(work)
    row.emit(work, ports)
    sch = subckt(name, ports, net)
    res = compact.check(work, name, sch)
    FAST.mkdir(parents=True, exist_ok=True)
    for suf in ('.mag', '.ext.spice', '.lvs.spice', '.gds'):
        f = work / f'{name}{suf}'
        if f.exists():
            shutil.copy(f, FAST / f'{name}{suf}')
    (FAST / f'{name}.spice').write_text('* SPDX-License-Identifier: Apache-2.0\n* generated by capture.py (intended netlist)\n' + sch)
    rails = {}
    for key, (net_, yy) in row.rails.items():
        rails.setdefault(net_, [0.3, yy])
    (FAST / f'{name}.pins.json').write_text(json.dumps(dict(ports=ports, pins={k: list(v) for k, v in row.pins.items()},
                                                           rails=rails, bbox=[0.0, 0.0, round(row.width, 3), round(row.top, 3)]),
                                                      indent=1))
    res.update(size_um=[round(row.width, 2), round(row.top, 2)], area_um2=round(row.width * row.top, 1), devices=len(net))
    print(name, json.dumps({k: (v if k != 'lvs' else v['unique_match']) for k, v in res.items()}), flush=True)
    return res


# ----------------------------------------------------------------------------------------- top
TOP_PORTS = ([f'S{j}' for j in range(8)] + [f'CKP{k}' for k in range(8)] +
             ['EN', 'LDE', 'B2', 'B1', 'PSEL0', 'PSEL1', 'PSEL2', 'SLIPP', 'SLIPM'] +
             [f'DW{i}' for i in range(20)] + [f'EW{i}' for i in range(20)] + ['SLP', 'SLM', 'VDD', 'VSS'])


def top_instances():
    """(instance name, cell, connections in cell port order)."""
    P = {n: CELLS[n]()[1] for n in CELLS}
    out = []

    def add(inst, cell, m):
        out.append((inst, cell, [m.get(p, p) for p in P[cell]]))
    add('XCTL', 'wc_ctl', {})
    add('XFR', 'wc_front', {})
    add('XLN', 'wc_lane', {})
    add('XCN', 'wc_cnt', {})
    add('XSL0', 'wc_slot0', {})
    add('XSL1', 'wc_slot1', {})
    for i in range(20):
        add(f'XP{i}', 'wc_pair', dict(GCK=f'GCK{i}', DLN=f'DL{i % 4}', ELN=f'EL{i % 4}', DW=f'DW{i}', EW=f'EW{i}'))
    return out


def top_netlist(include_cells=True):
    txt = ''
    if include_cells:
        for n in CELLS:
            txt += subckt(n, *CELLS[n]()[1:])          # always the current intended netlists
    txt += f'.subckt pt_wrx_cap {" ".join(TOP_PORTS)}\n'
    for inst, cell, conns in top_instances():
        txt += f'{inst} {" ".join(conns)} {cell}\n'
    txt += '.ends pt_wrx_cap\n'
    return txt


if __name__ == '__main__':
    for n in sys.argv[1:] or CELLS:
        build_cell(n)


# ----------------------------------------------------------------------------------------- bench
def prbs(n, seed=0x5A):
    s, out = seed, []
    for _ in range(n):
        b = ((s >> 6) ^ (s >> 5)) & 1
        out.append((s >> 6) & 1)
        s = ((s << 1) | b) & 0x7F
    return out


def bench(bpc, f=625e6, words=12, psel=0, corner='typical', temp=27, vdd=3.3, d_lat=300e-12, slip_seq=None,
          ext_clock=False):
    """Ideal ring phases + ideal sampler outputs (S_j changes d_lat after its phase edge, value = line at
    the phase edge) driving pt_wrx_cap.  Line: PRBS7 at bpc bits per ring cycle, data sampler centred.
    ext_clock: only CKP0/CKP4 toggle (CKP1-3 = CKP0, CKP5-7 = CKP4), as in the WCLK_IN fallback."""
    T = 1 / f
    ncyc = {4: 5, 2: 10, 1: 20}[bpc] * words + 12
    ui = T / bpc
    bits = prbs(int(ncyc * bpc) + 64)
    # data sampler for bit m: quarter j=2*(m%4), half j=4*(m%2), full j=psel; edges half a UI later
    dj = {4: [0, 2, 4, 6], 2: [0, 4], 1: [psel]}[bpc]
    t0 = 2e-9
    def line(t):   # bit m centred on the data sampler instants
        m = (t - t0 - (dj[0] * T / 8)) / ui + 0.5
        return bits[int(m)] if m >= 0 else 0
    lines = []
    tr = 40e-12
    for k in range(8):
        kk = k if not ext_clock else (0 if k < 4 else 4)
        lines.append(f'VCK{k} ckp{k} 0 PULSE(0 {vdd} {t0 + kk * T / 8:.6e} {tr} {tr} {T / 2 - tr:.6e} {T:.6e})')
    for j in range(8):
        pts = [(0, 0.)]
        for n in range(ncyc):
            ts = t0 + n * T + j * T / 8 + 1e-12
            v = vdd * line(ts + 0.25 * ui if (j not in dj) else ts)   # edge samplers: right after the boundary
            tc = ts + d_lat
            pts += [(tc, pts[-1][1]), (tc + 30e-12, v)]
        lines.append(f'VS{j} s{j} 0 {sims_pwl(pts)}')
    nw = {4: 5, 2: 10, 1: 20}[bpc]
    lde = [(0, 0.)]
    for w in range(words + 2):
        a = t0 + (w * nw + 2) * T + 0.3e-9
        lde += [(a, 0.), (a + 30e-12, vdd), (a + T, vdd), (a + T + 30e-12, 0.)]
    lines.append(f'VLDE lde 0 {sims_pwl(lde)}')
    b2, b1 = {4: (0, 0), 2: (1, 0), 1: (0, 1)}[bpc]
    lines += [f'VDD vdd 0 {vdd}', f'VEN en 0 PWL(0 0 1n 0 1.05n {vdd})', f'VB2 b2 0 {b2 * vdd}', f'VB1 b1 0 {b1 * vdd}']
    lines += [f'VPS{b} psel{b} 0 {vdd * ((psel >> b) & 1)}' for b in range(3)] + ['VSP slipp 0 0', 'VSM slipm 0 0']
    conn = {p: p.lower() for p in TOP_PORTS}
    conn.update(VDD='vdd', VSS='0')
    lines.append('XCAP ' + ' '.join(conn[p] for p in TOP_PORTS) + ' pt_wrx_cap')
    lines += [f'CDW{i} dw{i} 0 20f' for i in range(20)] + [f'CEW{i} ew{i} 0 20f' for i in range(20)]
    T_end = t0 + ncyc * T
    outs = ' '.join(f'v(dw{i})' for i in range(20)) + ' ' + ' '.join(f'v(ew{i})' for i in range(20))
    ctl = '\n'.join([f'tran 2p {T_end:.4g} 0 10p', 'set wr_singlescale', f'wrdata out.txt v(lde) {outs}',
                     f'meas tran iavg avg i(VDD) from={t0 + 6 * T:.4g} to={T_end:.4g}'])

    def analyse(log, data):
        import numpy as np
        d = np.loadtxt(data)
        t = d[:, 0]
        # word update instants: clusters of output transitions (W flops all load on one edge)
        ch = np.zeros(len(t), bool)
        for col in range(2, 42):
            v = d[:, col] > vdd / 2
            ch[1:] |= v[1:] != v[:-1]
        tc = t[ch]
        groups = []
        for x in tc:
            if groups and x - groups[-1][-1] < 0.3 * nw * T:
                groups[-1].append(x)
            else:
                groups.append([x])
        up = [g[0] for g in groups]
        ws = []
        for a, b in zip(up, up[1:]):
            if abs(b - a - nw * T) > 0.2 * nw * T:   # start-up / no change in a word
                continue
            k = int(np.searchsorted(t, (a + b) / 2))
            ws.append(([int(v > vdd / 2) for v in d[k, 2:22]], [int(v > vdd / 2) for v in d[k, 22:42]]))
        ws = ws[2:]          # start-up: counter restart and the phase-select shadow need one word each
        stream = [b for w, _ in ws for b in w]
        # find the PRBS alignment of the first full word and count mismatches over the rest
        best = None
        for off in range(len(bits) - len(stream)):
            err = sum(1 for i, b in enumerate(stream) if bits[off + i] != b)
            if best is None or err < best[1]:
                best = (off, err)
        iavg = None
        for line_ in log.splitlines():
            if line_.strip().startswith('iavg'):
                iavg = -float(line_.split('=')[1].split()[0])
        return dict(words=len(ws), bits=len(stream), offset=best[0] if best else None,
                    bit_errors=best[1] if best else None, i_mA=iavg * 1e3 if iavg else None,
                    pass_=bool(ws and len(ws) >= words - 4 and best and best[1] == 0))
    return '\n'.join(lines), ctl, analyse


def sims_pwl(points):
    return 'PWL(' + ' '.join(f'{t:.9e} {v:.4g}' for t, v in points) + ')'


def run_bench(tag, bpc, ext=False, **kw):
    import wrx_flow as wf
    import sims
    work = SCRATCH / 'sim' / tag
    work.mkdir(parents=True, exist_ok=True)
    if ext:
        shutil.copy(HERE / 'generated' / 'wrx_cap.ext.spice', work / 'cap.spice')
    else:
        (work / 'cap.spice').write_text(top_netlist())
    body, ctl, an = bench(bpc, **kw)
    (work / 'tb.cir').write_text('\n'.join([f'* {tag}', sims.sim_header(kw.get('corner', 'typical'), kw.get('temp', 27)),
                                           '.include cap.spice', body, '.control', ctl, '.endc', '.end']))
    log = wf.ngspice(work, 'tb.cir', timeout=4 * 3600)
    try:
        r = an(log, work / 'out.txt')
    except Exception as exc:
        r = dict(error=repr(exc)[:300], log_tail=log[-400:])
    r.update(tag=tag, bpc=bpc, netlist='extracted' if ext else 'schematic', **{k: v for k, v in kw.items() if k != 'slip_seq'})
    (work / 'result.json').write_text(json.dumps(r, indent=1, default=str))
    return r


# ----------------------------------------------------------------------------------------- top layout
def build_top(rows=None, max_row_width=420.0):
    """Assemble the compact rows with timing's generic macro placer/router (layout_engine), from this
    directory's generated/fast cells.  Writes generated/wrx_cap.{mag,gds,ext.spice,lvs.spice}."""
    import netlist as tn
    import wrx_flow as wf
    for n in CELLS:
        tn.MACROS[n] = json.loads((FAST / f'{n}.pins.json').read_text())['ports']
    le.FAST = FAST
    work = SCRATCH / 'top'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    (work / 'top.spice').write_text(top_netlist(include_cells=False))
    ports, devices = tn.load(work / 'top.spice', 'pt_wrx_cap')
    if rows is None:
        rows = [['CTL'], ['FR'], ['LN'], ['CN', 'SL0'], ['SL1']] + \
               [[f'P{i}' for i in range(k, min(k + 4, 20))] for k in range(0, 20, 4)]
    rep = le.generate(work, 'pt_wrx_cap', ports, devices, rows=rows, max_row_width=max_row_width)
    defs = ''.join((FAST / f'{m}.spice').read_text() for m in CELLS)
    (work / 'schematic.spice').write_text(defs + tn.flat_spice(ports, devices, 'pt_wrx_cap'))
    lvs = le.netgen_lvs(work, 'pt_wrx_cap.lvs.spice', 'pt_wrx_cap', 'schematic.spice', 'pt_wrx_cap')
    gen = HERE / 'generated'
    for suf in ('.mag', '.ext.spice', '.lvs.spice'):
        f = work / f'pt_wrx_cap{suf}'
        if f.exists():
            shutil.copy(f, gen / f'wrx_cap{suf}')
    for n in CELLS:
        if (work / f'{n}.mag').exists():
            shutil.copy(work / f'{n}.mag', FAST / f'{n}.mag')
    try:
        gx = wf.export_gds(work, 'pt_wrx_cap', 0)
    except Exception as exc:
        gx = dict(error=repr(exc)[:300])
    res = dict(drc_errors=le.drc_errors(rep['drc_count_raw']), lvs=lvs, layout={k: v for k, v in rep.items() if k != 'cmds'},
               gds_export=gx, devices=len(devices))
    (gen / 'wrx_cap-layout.json').write_text(json.dumps(res, indent=1, default=str))
    return res
