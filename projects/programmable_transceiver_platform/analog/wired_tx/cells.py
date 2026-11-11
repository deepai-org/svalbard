"""Transistor-level circuit definitions for the wired-TX family (single source).

Every schematic netlist (`wiredtx.spice`), the layout generator and the
testbenches read the cells defined here.  Only GF180 `gf180mcuD` 3.3 V MOS
devices are used (nfet_03v3 / pfet_03v3).

Block boundary (see README.md):
  * clock: four ring phases WTX_PH0/90/180/270 (CMOS, 50 % duty) from the
    timing family's shared ring PLL via the clockmux; MODE_H / MODE_F select
    2 or 1 bits per ring cycle (default 4);
  * data:  a 20-bit double word D0..D19 (two 10-bit line words, D0 first on
    the line) launched by rtl/pt_pattern.sv on the rising edge of WORD_CLK
    (bit rate / 20);
  * output: complementary CMOS gate commands CMD_<branch>_<leg> for the pads
    family's steering buffers, plus three tail-bias DACs for the MAIN, POST
    and TMDS tails of the pad output stage;
  * fallback: DX, the output of the shared differential receiver
    (pt_diff_clk_rx) on WTX_EXT_P/N, selected break-before-make in front of
    the pre-driver.
"""
from dataclasses import dataclass, field

N, P = 'nfet_03v3', 'pfet_03v3'


@dataclass
class Dev:
    name: str
    model: str
    w: float
    l: float
    nodes: tuple  # d g s b

    def spice(self):
        return f'X{self.name} {" ".join(self.nodes)} {self.model} w={self.w:g}u l={self.l:g}u'


class Macro:
    """A compact fast cell used as a black box (layout + intended netlist in
    generated/fast, from analog/timing or wtx_fast.py)."""
    def __init__(self, name):
        import json
        from pathlib import Path
        d = Path(__file__).resolve().parent / 'generated' / 'fast'
        self.name = name
        self.meta = json.loads((d / f'{name}.pins.json').read_text())
        self.ports = list(self.meta['ports'])
        self.text = (d / f'{name}.spice').read_text()

    def children(self):
        return []

    def spice(self):
        lines = [l for l in self.text.splitlines() if not l.startswith('*')]
        return '\n'.join(lines).strip()


@dataclass
class MacroDev:
    name: str
    model: str
    nodes: tuple
    w: float = 0.0
    l: float = 0.0


@dataclass
class Inst:
    name: str
    cell: 'Cell'
    conns: dict

    def spice(self):
        nets = [self.conns[p] for p in self.cell.ports]
        return f'X{self.name} {" ".join(nets)} {self.cell.name}'


@dataclass
class Cell:
    name: str
    ports: list
    items: list = field(default_factory=list)
    row_width: float = 70.0
    power_nets: tuple = ('VDD', 'VSS')

    def dev(self, name, model, d, g, s, w, l=0.28):
        b = 'VSS' if model == N else 'VDD'
        self.items.append(Dev(name, model, w, l, (d, g, s, b)))

    def inst(self, name, cell, **conns):
        missing = set(cell.ports) - set(conns)
        if missing:
            raise ValueError(f'{self.name}.{name}: unconnected {sorted(missing)}')
        self.items.append(Inst(name, cell, conns))

    def children(self):
        out = []
        for it in self.items:
            if isinstance(it, Inst):
                for c in it.cell.children():
                    if c not in out:
                        out.append(c)
                if it.cell not in out:
                    out.append(it.cell)
        return out

    def spice(self):
        lines = [f'.subckt {self.name} {" ".join(self.ports)}']
        lines += [it.spice() for it in self.items]
        lines.append(f'.ends {self.name}')
        return '\n'.join(lines)

    def flat_devices(self, prefix='', mapping=None):
        """Device list with hierarchical names and nets resolved to this cell."""
        mapping = mapping or {}
        net = lambda n: mapping.get(n, n if n in ('VDD', 'VSS') and not prefix else prefix + n)
        out = []
        for it in self.items:
            if isinstance(it, Dev):
                out.append(Dev(prefix + it.name, it.model, it.w, it.l, tuple(net(n) for n in it.nodes)))
            elif isinstance(it.cell, Macro):
                out.append(MacroDev(prefix + it.name, it.cell.name, tuple(net(it.conns[p]) for p in it.cell.ports)))
            else:
                sub = {p: net(n) for p, n in it.cell.ports.items()} if isinstance(it.cell.ports, dict) else \
                      {p: net(it.conns[p]) for p in it.cell.ports}
                out += it.cell.flat_devices(prefix + it.name + '/', sub)
        return out


def netlist(top):
    return '\n\n'.join([c.spice() for c in top.children()] + [top.spice()]) + '\n'


def finger(cell, name, model, d, g, s, w, l=0.28, max_w=16.0):
    """Split a wide device into equal parallel fingers of at most max_w."""
    n = 1
    while w / n > max_w:
        n += 1
    for i in range(n):
        cell.dev(f'{name}_{i}' if n > 1 else name, model, d, g, s, round(w / n, 3), l)


# ---------------------------------------------------------------- leaf cells
def inv(name, wn, wp, l=0.28):
    c = Cell(name, ['A', 'Y', 'VDD', 'VSS'])
    finger(c, 'MN', N, 'Y', 'A', 'VSS', wn, l)
    finger(c, 'MP', P, 'Y', 'A', 'VDD', wp, l)
    return c


def nand2(name='wtx_nand2', wn=2, wp=2):
    c = Cell(name, ['A', 'B', 'Y', 'VDD', 'VSS'])
    c.dev('MNA', N, 'Y', 'A', 'X', wn)
    c.dev('MNB', N, 'X', 'B', 'VSS', wn)
    c.dev('MPA', P, 'Y', 'A', 'VDD', wp)
    c.dev('MPB', P, 'Y', 'B', 'VDD', wp)
    return c


def nor2(name='wtx_nor2', wn=1, wp=4):
    c = Cell(name, ['A', 'B', 'Y', 'VDD', 'VSS'])
    c.dev('MPA', P, 'X', 'A', 'VDD', wp)
    c.dev('MPB', P, 'Y', 'B', 'X', wp)
    c.dev('MNA', N, 'Y', 'A', 'VSS', wn)
    c.dev('MNB', N, 'Y', 'B', 'VSS', wn)
    return c


def nand3(name, wn, wp):
    c = Cell(name, ['A', 'B', 'C', 'Y', 'VDD', 'VSS'])
    c.dev('MNA', N, 'Y', 'A', 'X1', wn); c.dev('MNB', N, 'X1', 'B', 'X2', wn); c.dev('MNC', N, 'X2', 'C', 'VSS', wn)
    for k, g in enumerate('ABC'):
        c.dev(f'MP{g}', P, 'Y', g, 'VDD', wp)
    return c


def nand4(name, wn, wp):
    c = Cell(name, ['A', 'B', 'C', 'D', 'Y', 'VDD', 'VSS'])
    prev = 'Y'
    for k, g in enumerate('ABCD'):
        nxt = 'VSS' if k == 3 else f'X{k}'
        finger(c, f'MN{g}', N, prev, g, nxt, wn)
        prev = nxt
    for g in 'ABCD':
        c.dev(f'MP{g}', P, 'Y', g, 'VDD', wp)
    return c


def mux2i(name='wtx_mux2i', wn=1, wp=2, wt=(1, 2)):
    """Y = NOT(S ? A : B), transmission-gate select, inverting output."""
    c = Cell(name, ['A', 'B', 'S', 'SB', 'Y', 'VDD', 'VSS'])
    c.dev('TA_N', N, 'X', 'S', 'A', wt[0])
    c.dev('TA_P', P, 'X', 'SB', 'A', wt[1])
    c.dev('TB_N', N, 'X', 'SB', 'B', wt[0])
    c.dev('TB_P', P, 'X', 'S', 'B', wt[1])
    finger(c, 'IN', N, 'Y', 'X', 'VSS', wn)
    finger(c, 'IP', P, 'Y', 'X', 'VDD', wp)
    return c


def dff(name='wtx_dffp', k=2):
    """Fast rising-edge static master/slave flop, active-low reset RB (DIV2).

    Plain inverters in both loops.  Reset pulls the slave storage node high
    (Q=0); it is only asserted while the flop's clock is gated to its
    stopped state (CK=0, CKB=1): the master is then transparent and simply
    follows D, and the forced slave agrees with its own feedback, so no
    static current flows in reset (an earlier master pull-up fought D=0
    in the shift-chain flops: ~0.5 mA each)."""
    c = Cell(name, ['D', 'CK', 'CKB', 'RB', 'Q', 'QB', 'VDD', 'VSS'], row_width=80)
    c.dev('T1N', N, 'X1', 'CKB', 'D', k); c.dev('T1P', P, 'X1', 'CK', 'D', 2 * k)
    c.dev('MN', N, 'MB', 'X1', 'VSS', k); c.dev('MP', P, 'MB', 'X1', 'VDD', 2 * k)
    c.dev('MFN', N, 'MF', 'MB', 'VSS', 1); c.dev('MFP', P, 'MF', 'MB', 'VDD', 2)
    c.dev('T2N', N, 'X1', 'CK', 'MF', 1); c.dev('T2P', P, 'X1', 'CKB', 'MF', 1)
    c.dev('T3N', N, 'X2', 'CK', 'MB', k); c.dev('T3P', P, 'X2', 'CKB', 'MB', 2 * k)
    c.dev('SN', N, 'Q', 'X2', 'VSS', 2 * k); c.dev('SP', P, 'Q', 'X2', 'VDD', 4 * k)
    c.dev('QBN', N, 'QB', 'Q', 'VSS', 2 * k); c.dev('QBP', P, 'QB', 'Q', 'VDD', 4 * k)
    c.dev('T4N', N, 'X2', 'CKB', 'QB', 1); c.dev('T4P', P, 'X2', 'CK', 'QB', 1)
    c.dev('PR2', P, 'X2', 'RB', 'VDD', 6)  # overrides the T4 feedback when reset hits Q=1
    return c


def dffs(name='wtx_dffs', k=2):
    """Static master/slave flop without reset (shift registers)."""
    c = Cell(name, ['D', 'CK', 'CKB', 'Q', 'QB', 'VDD', 'VSS'], row_width=80)
    c.dev('T1N', N, 'X1', 'CKB', 'D', k); c.dev('T1P', P, 'X1', 'CK', 'D', 2 * k)
    c.dev('MN', N, 'MB', 'X1', 'VSS', k); c.dev('MP', P, 'MB', 'X1', 'VDD', 2 * k)
    c.dev('MFN', N, 'MF', 'MB', 'VSS', 1); c.dev('MFP', P, 'MF', 'MB', 'VDD', 2)
    c.dev('T2N', N, 'X1', 'CK', 'MF', 1); c.dev('T2P', P, 'X1', 'CKB', 'MF', 1)
    c.dev('T3N', N, 'X2', 'CK', 'MB', k); c.dev('T3P', P, 'X2', 'CKB', 'MB', 2 * k)
    c.dev('SN', N, 'Q', 'X2', 'VSS', 2 * k); c.dev('SP', P, 'Q', 'X2', 'VDD', 4 * k)
    c.dev('QBN', N, 'QB', 'Q', 'VSS', 2 * k); c.dev('QBP', P, 'QB', 'Q', 'VDD', 4 * k)
    c.dev('T4N', N, 'X2', 'CKB', 'QB', 1); c.dev('T4P', P, 'X2', 'CK', 'QB', 1)
    return c


# ------------------------------------------------------------ composite cells
MUX = mux2i()
MUXF = mux2i('wtx_mux2i_x2', wn=2, wp=4)
DFF = dff()
DFFS = dffs()
NOR2X = nor2('wtx_nor2x', wn=4, wp=16)
NAND2E = nand2('wtx_nand2e', wn=8, wp=8)
NAND = nand2()
NOR = nor2()
INV1 = inv('wtx_inv1', 1, 2)
INV2 = inv('wtx_inv2', 2, 4)
INV4 = inv('wtx_inv4', 4, 8)
INV8 = inv('wtx_inv8', 8, 16)
INV16 = inv('wtx_inv16', 16, 32)
INVD = inv('wtx_invd', 1, 2, l=1.0)  # slow inverter for break-before-make delay
INV6 = inv('wtx_inv6', 6, 12)
INV24 = inv('wtx_inv24', 24, 48)


def sel3(name='wtx_sel3'):
    """Static one-hot 3:1 select: Y = Q&A | H&B | F&C (NAND-NAND)."""
    c = Cell(name, ['A', 'B', 'C', 'Q', 'H', 'F', 'Y', 'VDD', 'VSS'])
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('NA', NAND, A='A', B='Q', Y='XA', **V)
    c.inst('NB', NAND, A='B', B='H', Y='XB', **V)
    c.inst('NC', NAND, A='C', B='F', Y='XC', **V)
    c.inst('O', NAND3S, A='XA', B='XB', C='XC', Y='Y', **V)
    return c


def phbuf():
    """Ring-phase handling for 4, 2 or 1 bits per ring cycle (MODE_H/MODE_F).

    The ring supplies PH0/90/180/270 (CMOS, 50 % duty).  Every mode produces
    the same internal timing: a register clock FCK/FCKB of period 4 UI and
    four window pairs (WAk, WBk) with window k = WAk & WBk = UI k of that
    period, so the shift registers, retiming flops and 4:1 muxes are shared.
      quarter (default): FCK = PH0;  windows from the phases (PH k, PH k-1)
      half (MODE_H):     FCK = A1 (PH0/2);  windows A0&PH0, A1&PH180,
                         !A0&PH0, !A1&PH180 (A0 toggles on PH180, A1 = A0
                         re-sampled on PH0, so each selector is stable over
                         the half-cycles where it is used)
      full (MODE_F):     Johnson counter J0 <- !J1, J1 <- J0 on PH0 (one bit
                         changes per cycle); windows are its four states,
                         FCK = !J1
    All counters and the register clock are held in reset (clocks gated to
    the stopped state) while SER=0."""
    c = Cell('wtx_phbuf', ['PH0', 'PH90', 'PH180', 'PH270', 'SER', 'MODE_H', 'MODE_F',
                           'WA0', 'WB0', 'WA1', 'WB1', 'WA2', 'WB2', 'WA3', 'WB3', 'FCK', 'FCKB', 'RSTB',
                           'VDD', 'VSS'], row_width=140)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('RI', INV2, A='SER', Y='RST', **V)
    c.inst('RJ', INV4, A='RST', Y='RSTB', **V)
    # mode one-hots: F has priority over H; quarter when neither
    c.inst('MFI', INV1, A='MODE_F', Y='MFB', **V)
    c.inst('MHN', NAND, A='MODE_H', B='MFB', Y='MHB', **V)
    c.inst('MHI', INV2, A='MHB', Y='MH', **V)
    c.inst('MQN', NOR, A='MODE_H', B='MODE_F', Y='MQ', **V)
    c.inst('MFJ', INV2, A='MFB', Y='MF', **V)
    # gated ring clocks for the counters (stopped state: G0=0, G0B=1 / G180=0, G180B=1)
    c.inst('G0N', NAND2E, A='PH0', B='SER', Y='G0B', **V)
    c.inst('G0I', INV8, A='G0B', Y='G0', **V)
    c.inst('G1N', NAND2E, A='PH180', B='SER', Y='G180B', **V)
    c.inst('G1I', INV8, A='G180B', Y='G180', **V)
    # half-rate selectors: A0 toggles on PH180, A1 = A0 on PH0
    c.inst('FA0', DFF, D='A0B', CK='G180', CKB='G180B', RB='RSTB', Q='A0', QB='A0B', **V)
    c.inst('FA1', DFF, D='A0', CK='G0', CKB='G0B', RB='RSTB', Q='A1', QB='A1B', **V)
    # full-rate Johnson counter on PH0
    c.inst('FJ0', DFF, D='J1B', CK='G0', CKB='G0B', RB='RSTB', Q='J0', QB='J0B', **V)
    c.inst('FJ1', DFF, D='J0', CK='G0', CKB='G0B', RB='RSTB', Q='J1', QB='J1B', **V)
    # window selects: (quarter, half, full) sources per window input
    # ring phases gated by SER before the window selects: with the
    # serializer off (ring running) nothing downstream toggles
    for ph in ('0', '90', '180', '270'):
        c.inst(f'PG{ph}', NAND, A=f'PH{ph}', B='SER', Y=f'PGN{ph}', **V)
        c.inst(f'PGI{ph}', INV2, A=f'PGN{ph}', Y=f'PHG{ph}', **V)
    src = {'WA0': ('PHG0', 'A0', 'J0B'), 'WB0': ('PHG270', 'PHG0', 'J1B'),
           'WA1': ('PHG90', 'A1', 'J0'), 'WB1': ('PHG0', 'PHG180', 'J1B'),
           'WA2': ('PHG180', 'A0B', 'J0'), 'WB2': ('PHG90', 'PHG0', 'J1'),
           'WA3': ('PHG270', 'A1B', 'J0B'), 'WB3': ('PHG180', 'PHG180', 'J1')}
    for out, (q, h, f) in src.items():
        c.inst(f'S{out}', SEL3, A=q, B=h, C=f, Q='MQ', H='MH', F='MF', Y=f'{out}R', **V)
        c.inst(f'B{out}A', INV2, A=f'{out}R', Y=f'{out}N', **V)
        c.inst(f'B{out}', INV8, A=f'{out}N', Y=out, **V)
    # register clock: quarter PH0, half A1, full !J1 (all stopped low in reset)
    c.inst('SCK', SEL3, A='G0', B='A1', C='J1B', Q='MQ', H='MH', F='MF', Y='RCKR', **V)
    c.inst('RCA', INV4, A='RCKR', Y='RCKN', **V)
    c.inst('RCB', INV24, A='RCKN', Y='FCK', **V)
    c.inst('RCC', INV2, A='RCKR', Y='RCKN2', **V)
    c.inst('RCD', INV4, A='RCKN2', Y='RCKM', **V)
    c.inst('RCE', INV24, A='RCKM', Y='FCKB', **V)
    c.inst('XC1', INV4, A='FCK', Y='FCKB', **V)
    c.inst('XC2', INV4, A='FCKB', Y='FCK', **V)
    return c


def mux4p(name='wtx_mux4p'):
    """4:1 window mux: Y = D_k during window k = WAk & WBk (NAND3 / NAND4)."""
    c = Cell(name, ['D0', 'D1', 'D2', 'D3', 'WA0', 'WB0', 'WA1', 'WB1', 'WA2', 'WB2', 'WA3', 'WB3', 'Y', 'VDD', 'VSS'],
             row_width=90)
    V = dict(VDD='VDD', VSS='VSS')
    for k in range(4):
        c.inst(f'N{k}', NAND3M, A=f'D{k}', B=f'WA{k}', C=f'WB{k}', Y=f'T{k}', **V)
    c.inst('O', NAND4M, A='T0', B='T1', C='T2', D='T3', Y='Y', **V)
    return c


def srbit():
    """One bit of a parallel-load shift register: Q <= LD ? P : NXT (O = Q)."""
    c = Cell('wtx_srbit', ['P', 'NXT', 'LD', 'LDB', 'CK', 'CKB', 'O', 'VDD', 'VSS'])
    c.inst('M', MUXF, A='P', B='NXT', S='LD', SB='LDB', Y='X', VDD='VDD', VSS='VSS')
    c.inst('F', DFFS, D='X', CK='CK', CKB='CKB', Q='XQ', QB='O', VDD='VDD', VSS='VSS')
    return c


def sr5():
    """5:1 parallel-load shift register; P0 is sent first."""
    c = Cell('wtx_sr5', ['P0', 'P1', 'P2', 'P3', 'P4', 'LD', 'LDB', 'CK', 'CKB', 'O', 'VDD', 'VSS'])
    for k in range(5):
        c.inst(f'B{k}', SRBIT, P=f'P{k}', NXT=('VSS' if k == 4 else f'O{k+1}'), LD='LD', LDB='LDB', CK='CK',
               CKB='CKB', O=('O' if k == 0 else f'O{k}'), VDD='VDD', VSS='VSS')
    return c


def div5():
    """Self-starting divide-by-5 on the quarter-rate clock (a <- NOR(b,c), b <- a, c <- b).

    States abc: 000 -> 100 -> 110 -> 011 -> 001.  LD is high in state 000, so
    the registers load at the edge that ends it.  WORD_CLK = c rises three
    quarter-rate periods before that load edge and the next launch is two
    periods after it.  Reset (RB=0, clock static) forces 000."""
    c = Cell('wtx_div5', ['CK', 'CKB', 'RB', 'LD', 'LDB', 'WORD_CLK', 'VDD', 'VSS'])
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('NA', NOR2X, A='B', B='C', Y='AN', **V)
    c.inst('FA', DFF, D='AN', CK='CK', CKB='CKB', RB='RB', Q='A', QB='AB', **V)
    c.inst('FB', DFF, D='A', CK='CK', CKB='CKB', RB='RB', Q='B', QB='BB', **V)
    c.inst('FC', DFF, D='B', CK='CK', CKB='CKB', RB='RB', Q='C', QB='CB', **V)
    c.inst('NL', NOR, A='A', B='C', Y='L0', **V)
    c.inst('LA', INV2, A='L0', Y='L1', **V)
    c.inst('LB', INV8, A='L1', Y='LD', **V)
    c.inst('LC', INV8, A='L0', Y='LDB', **V)
    c.inst('WA', INV4, A='C', Y='WN', **V)
    c.inst('WB', INV16, A='WN', Y='WORD_CLK', **V)
    return c




NAND3M = nand3('wtx_nand3m', 8, 8)
NAND4M = nand4('wtx_nand4m', 16, 8)
NAND2F = nand2('wtx_nand2f', wn=16, wp=16)
MUX4P = mux4p()
NAND3S = nand3('wtx_nand3s', 3, 2)
SEL3 = sel3()
SRBIT = srbit()
SR5 = sr5()
DIV5 = div5()
NAND_O = nand2('wtx_nand2o', wn=4, wp=4)
NANDG = nand2('wtx_nand2g', wn=8, wp=8)
NAND3_O = nand3('wtx_nand3o', 6, 4)
# window gates of the compact quarter core: fast rise at the NAND output and fast fall at
# the inverter output make the window close early relative to its opening, so adjacent
# windows do not overlap (the AND-OR mux would OR two bits)
NAND2W = nand2('wtx_nand2w', wn=8, wp=8)
INVW = inv('wtx_invw', 8, 20)


def bbm():
    """Break-before-make selection between serializer (SER) and external (EXT)."""
    c = Cell('wtx_bbm', ['SER_EN', 'WTX_EXT', 'SER', 'EXT', 'VDD', 'VSS'], row_width=90)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('XI', INV1, A='WTX_EXT', Y='XRB', **V)
    c.inst('SR', NAND, A='SER_EN', B='XRB', Y='SRB', **V)       # SRB = NOT(SER_EN & !EXT)
    c.inst('SN', NOR, A='SRB', B='EXTD', Y='SER', **V)          # SER = req & !EXT_delayed
    c.inst('EN', NOR, A='XRB', B='SERD', Y='EXT', **V)          # EXT = WTX_EXT & !SER_delayed
    prev = 'SER'
    for i in range(4):
        nxt = 'SERD' if i == 3 else f'SD{i}'
        c.inst(f'DS{i}', INVD, A=prev, Y=nxt, **V); prev = nxt
    prev = 'EXT'
    for i in range(4):
        nxt = 'EXTD' if i == 3 else f'ED{i}'
        c.inst(f'DE{i}', INVD, A=prev, Y=nxt, **V); prev = nxt
    return c


def predrv():
    """Data select (compact quarter-rate core / external) and per-branch gated complementary commands.

    Session 6: the generic serializer (rate code 11) is removed (path A, the CMOS core + WT12 repetition,
    covers every rate it served at every envelope corner), so the select is two-way.
    IX-9 (coordinator, 2026-11-10): POST_POL selects the postcursor polarity.  POST_POL = 0: the POST
    tail steers opposite to MAIN one UI later (de-emphasis, as before); POST_POL = 1: same sign, so
    MAIN + POST sum (MLT-3 / PAM-3 / duobinary).  Every leg (MAIN, TMDS, POST) passes the same two
    NAND levels between the select and the enable gate (MAIN / TMDS with the select input tied), so the
    one-UI MAIN -> POST offset is unchanged."""
    outs = ['CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P', 'CMD_POST_N', 'CMD_TMDS_P', 'CMD_TMDS_N']
    c = Cell('wtx_predrv', ['DQ', 'DQB', 'DPQ', 'DPQB', 'DX', 'SERQ', 'EXT', 'POST_POL',
                            'EN_MAIN', 'EN_POST', 'EN_TMDS', 'ISLAND_OFF', 'EXT_DATA'] + outs + ['VDD', 'VSS'],
             row_width=150)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('XB', INV1, A='DX', Y='DXB', **V)
    # status copy of the external data, gated with EXT: it toggles only in WTX_EXT mode (it coupled
    # ~0.6 V glitches onto the adjacent word input D13 while DX toggled in serializer mode)
    c.inst('XN', NAND, A='DX', B='EXT', Y='EXDN', **V)
    c.inst('XO', INV1, A='EXDN', Y='EXT_DATA', **V)
    # Session 8: four dynamic levels on every leg (was five plus an INV4 after IX-9; extracted ss/32/3.15
    # 2.5 Gb/s: 20/141 errors, 340-420 ps edges at CMD).  Level 1/2: NAND-NAND select (MAIN/TMDS: core or
    # external data; POST: DP or DPB by POST_POL, the polarity folded into static enables SP = SERQ & !POL,
    # SPP = SERQ & POL); level 3: NAND with the branch enable; level 4: INV16 onto the CMD route.
    c.inst('PPI', INV1, A='POST_POL', Y='POLB', **V)
    c.inst('SPA', NAND, A='SERQ', B='POLB', Y='SPN', **V)
    c.inst('SPB', INV2, A='SPN', Y='SP', **V)
    c.inst('SQA', NAND, A='SERQ', B='POST_POL', Y='SQN', **V)
    c.inst('SQB', INV2, A='SQN', Y='SPP', **V)
    c.inst('Q1', NAND_O, A='DQ', B='SERQ', Y='NQ1', **V)
    c.inst('X1', NAND_O, A='DX', B='EXT', Y='NX1', **V)
    c.inst('O1', NANDG, A='NQ1', B='NX1', Y='DS', **V)
    c.inst('Q2', NAND_O, A='DQB', B='SERQ', Y='NQ2', **V)
    c.inst('X2', NAND_O, A='DXB', B='EXT', Y='NX2', **V)
    c.inst('O2', NANDG, A='NQ2', B='NX2', Y='DSB', **V)
    for leg, a_, b_ in (('P', 'DPQ', 'DPQB'), ('N', 'DPQB', 'DPQ')):
        c.inst(f'PA{leg}', NAND_O, A=a_, B='SP', Y=f'NPA{leg}', **V)
        c.inst(f'PB{leg}', NAND_O, A=b_, B='SPP', Y=f'NPB{leg}', **V)
        c.inst(f'PO{leg}', NANDG, A=f'NPA{leg}', B=f'NPB{leg}', Y=f'PS{leg}', **V)
    for br, (pos, neg, en) in {'MAIN': ('DSB', 'DS', 'EN_MAIN'), 'TMDS': ('DSB', 'DS', 'EN_TMDS'),
                               'POST': ('PSP', 'PSN', 'EN_POST')}.items():
        for leg, data in (('P', pos), ('N', neg)):
            o = f'CMD_{br}_{leg}'
            c.inst(f'G_{br}_{leg}', NANDG, A=data, B=en, Y=f'NB_{br}_{leg}', **V)
            c.inst(f'O_{br}_{leg}', INV16, A=f'NB_{br}_{leg}', Y=o, **V)
            c.dev(f'CL_{br}_{leg}', N, o, 'ISLAND_OFF', 'VSS', 2)
    return c


def idac(diode_fingers, scale=1.0, name=None):
    """8-bit binary PMOS current DAC into a diode that mirrors into a pad tail.

    LSB = 5 uA into the diode (unit PMOS W=1/L=1 against a W=2/L=1 reference
    diode carrying 10 uA).  The diode (W=20/L=1 per finger) is 1/16 of the
    selected pad tail for that branch, so the tail LSB is about 80 uA.
    """
    codes = [f'C{k}' for k in range(8)]
    c = Cell(name or f'wtx_idac{diode_fingers}', ['NB', 'EN', 'ISLAND_OFF'] + codes + ['BIAS', 'PB', 'VDD', 'VSS'],
             row_width=150)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('EI', INV1, A='EN', Y='ENB', **V)
    c.dev('MN1', N, 'M1', 'NB', 'VSS', 2, 2.0)
    c.dev('SWN', N, 'PB', 'EN', 'M1', 2)
    c.dev('MP0', P, 'PB', 'PB', 'VDD', 2, 1.0)
    c.dev('PBU', P, 'PB', 'EN', 'VDD', 1)
    for k in range(8):
        c.inst(f'CI{k}', INV1, A=f'C{k}', Y=f'CB{k}', **V)
        w = 2 ** k
        nf = max(1, w // 16)
        for f in range(nf):
            c.dev(f'MS{k}_{f}' if nf > 1 else f'MS{k}', P, f'S{k}', 'PB', 'VDD', round(min(w, 16) * scale, 3), 1.0)
        c.dev(f'SW{k}', P, 'BIAS', f'CB{k}', f'S{k}', 2 if k < 5 else 4 * 2 ** (k - 5))
    for f in range(diode_fingers):
        c.dev(f'MD{f}' if diode_fingers > 1 else 'MD', N, 'BIAS', 'BIAS', 'VSS', 20, 1.0)
    c.dev('PDE', N, 'BIAS', 'ENB', 'VSS', 2)
    c.dev('PDI', N, 'BIAS', 'ISLAND_OFF', 'VSS', 2)
    return c


IDAC2 = idac(2)
# MAIN tail DAC with 1.2x unit sources (package demand D-WT-2: >= 24 mA): LSB 6 uA -> tail LSB ~100 uA,
# code 255 -> ~25.4 mA, code 200 -> ~19.9 mA, code 240 -> ~23.9 mA (POST / TMDS unchanged)
IDAC2M = idac(2, scale=1.2, name='wtx_idac2m')
IDAC1 = idac(1)


def serq():
    """20:1 quarter-rate serializer.

    Two 10-bit line words per WORD_CLK period (D0..D9 first, D0 first on the
    line) load four 5:1 shift registers (stream s = D[s], D[s+4], ..D[s+16])
    on the PH0 flop clock.  Retiming flops on PH180 (A*) and PH0 (B*, C3)
    keep each stream stable over its 4:1-mux window(s); every flop-to-flop
    path has half a quarter-rate period (two UI) of budget.
    Main mux windows: A0, A1, B2, B3.  Postcursor (main delayed one UI):
    C3, A0, B1, B2."""
    W = [f'W{ab}{k}' for k in range(4) for ab in 'AB']
    ports = [f'D{i}' for i in range(20)] + W + ['FCK', 'FCKB', 'RSTB', 'WORD_CLK', 'Y', 'YB', 'DP', 'DPB', 'VDD', 'VSS']
    c = Cell('wtx_serq', ports, row_width=260)
    V = dict(VDD='VDD', VSS='VSS')
    M = {w: w for w in W}
    c.inst('D5', DIV5, CK='FCK', CKB='FCKB', RB='RSTB', LD='LD', LDB='LDB', WORD_CLK='WORD_CLK', **V)
    # input inverters: the word inputs see MOS gates only (no diffusion path
    # into the island rail when the island is off and the source is high);
    # the registers therefore carry inverted data, undone at the muxes
    for i in range(20):
        c.inst(f'DI{i}', INV1, A=f'D{i}', Y=f'DN{i}', **V)
    for st in range(4):
        c.inst(f'R{st}', SR5, **{f'P{k}': f'DN{st + 4*k}' for k in range(5)}, LD='LD', LDB='LDB', CK='FCK',
               CKB='FCKB', O=f'S{st}', **V)
    for st in range(4):   # PH180 retime
        c.inst(f'A{st}', DFFS, D=f'S{st}', CK='FCKB', CKB='FCK', Q=f'A{st}', QB=f'A{st}B', **V)
    for st in (1, 2, 3):  # PH0 retime
        c.inst(f'B{st}', DFFS, D=f'A{st}', CK='FCK', CKB='FCKB', Q=f'B{st}', QB=f'B{st}B', **V)
    c.inst('C3', DFFS, D='B3', CK='FCKB', CKB='FCK', Q='C3', QB='C3B', **V)
    c.inst('MY', MUX4P, D0='A0B', D1='A1B', D2='B2B', D3='B3B', Y='Y', **M, **V)
    c.inst('MYB', MUX4P, D0='A0', D1='A1', D2='B2', D3='B3', Y='YB', **M, **V)
    c.inst('MD', MUX4P, D0='C3B', D1='A0B', D2='B1B', D3='B2B', Y='DP', **M, **V)
    c.inst('MDB', MUX4P, D0='C3', D1='A0', D2='B1', D3='B2', Y='DPB', **M, **V)
    return c


DIV_PHASE = 'C2R'


def serq4():
    """Compact quarter-rate 20:1 core (MODE_H = MODE_F = 0), all timing on
    the four gated ring phases Q0..Q3 (Q k rises at k UI); no derived clock.

    * Four 5-bit parallel-load shift registers (stream s = D[s], D[s+4], ..
      D[s+16]) of timing's TSPC flops (ct_tspcd), all on Q2, loaded by
      LD0 = NOR(A, C) of a ct_div5 on Q2: one clock domain, so the load
      needs no phase crossing.
    * Each stream then reaches the phase that centres it on its 4:1-mux
      window k = Q(k) & Q(k-1) through retiming hops of +3 UI or +4 UI only,
      so every crossing has >= 4 UI - 3 UI ... i.e. (hop - tcq) >= 1.7 UI of
      margin with tcq ~ 1.3 UI (0.4 ns) at 3.24 Gb/s:
        stream 0: Q2 -> Q2 -> Q2          (+4 +4)
        stream 1: Q2 -> Q1 -> Q0 -> Q3    (+3 +3 +3)
        stream 2: Q2 -> Q1 -> Q0 -> Q0    (+3 +3 +4)
        stream 3: Q2 -> Q1 -> Q1 -> Q1    (+3 +4 +4)
      All four streams reach the line 3 register periods after the load, in
      order, and each final stream F k changes about tcq after phase k+2:
      2 UI - tcq before window k opens, and it holds through window k+1.
    * The postcursor mux uses F(k-1) in window k (the main bit one UI
      later): no extra flops.
    Reset: SERQ = 0 stops Q0..Q3 low and resets every TSPC flop (outputs 0)."""
    ports = [f'D{i}' for i in range(20)] + ['PH0', 'PH90', 'PH180', 'PH270', 'SERQ', 'MQ', 'MH', 'MF',
                                             'Y', 'YB', 'DP', 'DPB', 'WCKQ', 'VDD', 'VSS']
    c = Cell('wtx_serq4', ports, row_width=260)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('RI', INV2, A='SERQ', Y='QRA', **V)
    c.inst('RJ', INV4, A='QRA', Y='QRB', **V)
    c.inst('RK', INV8, A='QRB', Y='QRST', **V)        # ENB of every TSPC flop (1 = reset)
    # Four equally spaced core phases C0..C3 (one UI apart) in every mode, one-hot MQ/MH/MF:
    #   quarter: the ring phases;
    #   half:    ring/2 from TSPC flops on the gated ring: a toggles on PH0, b = a @PH0
    #            (= !a), c = a @PH180 (90 deg), d = c @PH180 (= !c); every phase is a flop Q,
    #            so all four carry the same clock-to-Q;
    #   full:    ring/4 twisted ring on PH0: j0 <- !j1, j1 <- j0, j2 <- j1 (= !j0), j3 <- j2 (= !j1).
    c.inst('G0N', NAND2E, A='PH0', B='SERQ', Y='G0B', **V)
    c.inst('G0I', INV8, A='G0B', Y='G0', **V)
    c.inst('G2N', NAND2E, A='PH180', B='SERQ', Y='G2B', **V)
    c.inst('G2I', INV8, A='G2B', Y='G2', **V)
    # equal load on every ring-phase input: dummies matching G0N/G2N on PH90/PH270
    c.inst('G1N', NAND2E, A='PH90', B='SERQ', Y='G1B', **V)
    c.inst('G1I', INV8, A='G1B', Y='G1X', **V)
    c.inst('G3N', NAND2E, A='PH270', B='SERQ', Y='G3B', **V)
    c.inst('G3I', INV8, A='G3B', Y='G3X', **V)
    c.inst('HA', TSPCD, CK='G0', D='HAB', Q='HA_', ENB='QRST', **V)
    c.inst('HAI', INV1, A='HA_', Y='HAB', **V)
    c.inst('HB', TSPCD, CK='G0', D='HA_', Q='HB_', ENB='QRST', **V)
    c.inst('HC', TSPCD, CK='G2', D='HA_', Q='HC_', ENB='QRST', **V)
    c.inst('HD', TSPCD, CK='G2', D='HC_', Q='HD_', ENB='QRST', **V)
    c.inst('JA', TSPCD, CK='G0', D='JBB', Q='JA_', ENB='QRST', **V)
    c.inst('JB', TSPCD, CK='G0', D='JA_', Q='JB_', ENB='QRST', **V)
    c.inst('JBI', INV1, A='JB_', Y='JBB', **V)
    c.inst('JC', TSPCD, CK='G0', D='JB_', Q='JC_', ENB='QRST', **V)
    c.inst('JD', TSPCD, CK='G0', D='JC_', Q='JD_', ENB='QRST', **V)
    for k, (q, h, f) in enumerate((('PH0', 'HA_', 'JA_'), ('PH90', 'HC_', 'JB_'), ('PH180', 'HB_', 'JC_'),
                                   ('PH270', 'HD_', 'JD_'))):
        c.inst(f'CS{k}', SEL3, A=q, B=h, C=f, Q='MQ', H='MH', F='MF', Y=f'CR{k}', **V)
        c.inst(f'CB{k}', INV4, A=f'CR{k}', Y=f'CN{k}', **V)     # SEL3 is weak: buffer before
        c.inst(f'CC{k}', INV16, A=f'CN{k}', Y=f'C{k}', **V)     # the phase drivers
        # second, identical copy per phase: C2's copy (C2R) clocks the register bank and the
        # divider; the other copies are equal-load dummies, so C0..C3 stay balanced
        c.inst(f'CD{k}', INV4, A=f'CR{k}', Y=f'CRN{k}', **V)
        c.inst(f'CE{k}', INV16, A=f'CRN{k}', Y=f'C{k}R', **V)
        if k != 2:
            for d in range(3):
                c.inst(f'CX{k}_{d}', NAND2E, A=f'C{k}R', B='SERQ', Y=f'CXN{k}_{d}', **V)
    ph = ['C0', 'C1', 'C2', 'C3']
    # gated phases (stopped low), three sets so that loads are balanced:
    #   QW k: window gates only (each drives exactly two NAND2E inputs)
    #   Q k : retiming hops;  QR: the 20 register flops and the divider (PH180)
    for k in range(4):
        c.inst(f'PW{k}', NAND2E, A=ph[k], B='SERQ', Y=f'QWN{k}', **V)
        c.inst(f'PX{k}', INV8, A=f'QWN{k}', Y=f'QW{k}', **V)
        c.inst(f'PG{k}', NAND2E, A=ph[k], B='SERQ', Y=f'QN{k}', **V)
        c.inst(f'PB{k}', INV8, A=f'QN{k}', Y=f'Q{k}', **V)
    # register bank on PH180: two drivers (streams 0-1 / 2-3, ten flops each).  The
    # divider has its own light driver (a slow shared edge let ct_div5 race to /4 at
    # ff).  LD/LDB are buffered; measured at 3.24 Gb/s LD changes 1.2-2.1 UI after a
    # register edge and 1.9-2.8 UI before the next (ss/tt/ff, schematic).
    for h in '01':
        c.inst(f'PR{h}', NAND2E, A='C2R', B='SERQ', Y=f'QKN{h}', **V)
        c.inst(f'PRB{h}', INV16, A=f'QKN{h}', Y=f'QK{h}', **V)
    c.inst('PD', NAND2E, A=DIV_PHASE, B='SERQ', Y='QDN', **V)
    c.inst('PDB', INV8, A='QDN', Y='QD', **V)
    c.inst('DV', DIV5C, CK='QD', ENB='QRST', A='DA', B='DB', C='DC', **V)
    # LD / LDB each drive 20 NAND2 inputs: buffered (a minimum NOR alone put LD
    # 2-2.8 UI after the divider clock at 3.24 Gb/s)
    c.inst('LN', NOR2X, A='DA', B='DC', Y='LD0', **V)
    c.inst('LI', INV8, A='LD0', Y='LDB', **V)
    c.inst('LJ', INV16, A='LDB', Y='LD', **V)
    c.inst('WA', INV4, A='DC', Y='WCN', **V)
    c.inst('WB', INV16, A='WCN', Y='WCKQ', **V)
    for k in range(4):
        for j in range(5):
            nxt = 'VSS' if j == 4 else f'B{k}_{j+1}'
            c.inst(f'M{k}_{j}A', NAND, A=f'D{k + 4*j}', B='LD', Y=f'MA{k}_{j}', **V)
            c.inst(f'M{k}_{j}B', NAND, A=nxt, B='LDB', Y=f'MB{k}_{j}', **V)
            c.inst(f'M{k}_{j}O', NAND, A=f'MA{k}_{j}', B=f'MB{k}_{j}', Y=f'X{k}_{j}', **V)
            c.inst(f'F{k}_{j}', TSPCD, CK='QK0' if k < 2 else 'QK1', D=f'X{k}_{j}', Q=f'B{k}_{j}', ENB='QRST', **V)
    hops = {0: (2, 2), 1: (1, 0, 3), 2: (1, 0, 0), 3: (1, 1, 1)}
    for k, seq in hops.items():
        prev = f'B{k}_0'
        for i, q in enumerate(seq):
            out = f'F{k}' if i == len(seq) - 1 else f'R{k}_{i}'
            c.inst(f'H{k}_{i}', TSPCD, CK=f'Q{q}', D=prev, Q=out, ENB='QRST', **V)
            prev = out
    c.inst('CI', CINV8, **{f'A{k}': f'F{k}' for k in range(4)}, **{f'A{k+4}': 'VSS' for k in range(4)},
           **{f'Y{k}': f'FN{k}' for k in range(4)}, **{f'Y{k+4}': f'CU{k}' for k in range(4)}, **V)
    for k in range(4):                                  # windows k = Q(k) & Q(k-1)
        c.inst(f'WN{k}', NAND2W, A=f'QW{k}', B=f'QW{(k - 1) % 4}', Y=f'SN{k}', **V)
        c.inst(f'WI{k}', INVW, A=f'SN{k}', Y=f'S{k}', **V)
    S = {f'S{k}': f'S{k}' for k in range(4)}
    c.inst('MY', MUX4W, **{f'A{k}': f'F{k}' for k in range(4)}, Y='Y', **S, **V)
    c.inst('MYB', MUX4W, **{f'A{k}': f'FN{k}' for k in range(4)}, Y='YB', **S, **V)
    c.inst('MD', MUX4W, **{f'A{k}': f'F{(k - 1) % 4}' for k in range(4)}, Y='DP', **S, **V)
    c.inst('MDB', MUX4W, **{f'A{k}': f'FN{(k - 1) % 4}' for k in range(4)}, Y='DPB', **S, **V)
    return c


def w40():
    """WORD_CLK40 toggle: SEL toggles on every WORD_CLK rising edge; reset (RB = SER_EN low, WORD_CLK
    stopped low) gives SEL = 0, so the first WORD_CLK edge sets SEL = 1 (D0..D19) and WORD_CLK40 rises."""
    c = Cell('wtx_w40', ['CK', 'RB', 'SEL', 'SELB', 'W40', 'VDD', 'VSS'])
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('CI', INV1, A='CK', Y='CKB', **V)
    c.inst('F', DFF, D='SELB', CK='CK', CKB='CKB', RB='RB', Q='SEL', QB='SELB', **V)
    c.inst('O1', INV2, A='SEL', Y='W40N', **V)
    c.inst('O2', INV4, A='W40N', Y='W40', **V)
    return c


# WT12 (approved 2026-11-10): the compact core always runs at quarter rate; half / full rate are 2x / 4x
# bit repetition of the 40-bit user word inside the block.  Johnson counter on WORD_CLK (core line/20):
#   rep1 (quarter core / generic fallback): 1 stage, J0 toggles            -> 2 loads per 40-bit word
#   rep2 (MODE 10):                         J0 <- !J1                       -> 4 loads, 10 user bits each
#   rep4 (MODE 01):                         J0 <- !J3, J1..J3 shift         -> 8 loads,  5 user bits each
# J0 is high for the first half of every user word in every mode, so it is both the half-word select
# (D0..D19 vs D20..D39, as the earlier WORD_CLK40 toggle) and WORD_CLK40 (= user line/40, 50 % duty,
# rises on the first WORD_CLK edge after SER_EN).  Within a half word the sub-chunk is one-hot from
# adjacent Johnson stages: rep2 q0 = J0^J1, q1 = !(J0^J1); rep4 q0 = J0^J1, q1 = J1^J2, q2 = J2^J3,
# q3 = !(J3^J0).  Static CMOS at <= 162 MHz (WORD_CLK at 3.24 Gb/s), conventional cells only.
def xor2(name='wtx_xor2'):
    """Y = A ^ B, YB = !(A ^ B) (four NAND2 + inverter)."""
    c = Cell(name, ['A', 'B', 'Y', 'YB', 'VDD', 'VSS'])
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('N1', NAND, A='A', B='B', Y='M', **V)
    c.inst('N2', NAND, A='A', B='M', Y='U', **V)
    c.inst('N3', NAND, A='B', B='M', Y='W', **V)
    c.inst('N4', NAND, A='U', B='W', Y='Y', **V)
    c.inst('I', INV1, A='Y', Y='YB', **V)
    return c


def rep():
    """Johnson counter + one-hot select lines for the WT12 repetition expander."""
    T = ['T1', 'T2A', 'T2B', 'T4A', 'T4B', 'T4C', 'T4D']
    c = Cell('wtx_rep', ['CK', 'RB', 'R2', 'R4', 'SEL', 'SELB', 'W40'] + T + [t + 'N' for t in T] + ['VDD', 'VSS'])
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('CI', INV1, A='CK', Y='CKB', **V)
    # mode decode: R1 = !R2 & !R4
    c.inst('R1N', NOR, A='R2', B='R4', Y='R1', **V)
    c.inst('R2I', INV1, A='R2', Y='R2B', **V)
    c.inst('R4I', INV1, A='R4', Y='R4B', **V)
    # J0 feedback: rep1 !J0, rep2 !J1, rep4 !J3 (AOI from the flops' QB outputs)
    c.inst('FA', NAND, A='R1', B='J0B', Y='FAN', **V)
    c.inst('FB', NAND, A='R2', B='J1B', Y='FBN', **V)
    c.inst('FC', NAND, A='R4', B='J3B', Y='FCN', **V)
    c.dev('FPA', P, 'JD', 'FAN', 'VDD', 2); c.dev('FPB', P, 'JD', 'FBN', 'VDD', 2); c.dev('FPC', P, 'JD', 'FCN', 'VDD', 2)
    c.dev('FNA', N, 'JD', 'FAN', 'FX1', 2); c.dev('FNB', N, 'FX1', 'FBN', 'FX2', 2); c.dev('FNC', N, 'FX2', 'FCN', 'VSS', 2)
    c.inst('J0', DFF, D='JD', CK='CK', CKB='CKB', RB='RB', Q='J0', QB='J0B', **V)
    c.inst('J1', DFF, D='J0', CK='CK', CKB='CKB', RB='RB', Q='J1', QB='J1B', **V)
    c.inst('J2', DFF, D='J1', CK='CK', CKB='CKB', RB='RB', Q='J2', QB='J2B', **V)
    c.inst('J3', DFF, D='J2', CK='CK', CKB='CKB', RB='RB', Q='J3', QB='J3B', **V)
    c.inst('X01', XOR2, A='J0', B='J1', Y='Q01', YB='Q01B', **V)
    c.inst('X12', XOR2, A='J1', B='J2', Y='Q12', YB='Q12B', **V)
    c.inst('X23', XOR2, A='J2', B='J3', Y='Q23', YB='Q23B', **V)
    c.inst('X30', XOR2, A='J3', B='J0', Y='Q30', YB='Q30B', **V)
    terms = dict(T1=('R1', 'VDD'), T2A=('R2', 'Q01'), T2B=('R2', 'Q01B'), T4A=('R4', 'Q01'), T4B=('R4', 'Q12'),
                 T4C=('R4', 'Q23'), T4D=('R4', 'Q30B'))
    for t, (a, b) in terms.items():
        c.inst(f'S{t}', NAND, A=a, B=b, Y=f'{t}X', **V)          # {t}X = !T
        c.inst(f'B{t}N', INV2, A=f'{t}X', Y=f'{t}I', **V)
        c.inst(f'B{t}', INV4, A=f'{t}I', Y=f'{t}N', **V)          # TN = !T (buffered)
        c.inst(f'B{t}P', INV4, A=f'{t}X', Y=t, **V)               # T (buffered)
    c.inst('O1', INV2, A='J0', Y='W40N', **V)
    c.inst('O2', INV4, A='W40N', Y='W40', **V)
    c.inst('SB1', INV2, A='J0', Y='SELB', **V)
    c.inst('SB2', INV2, A='J0', Y='SELN', **V)
    c.inst('SB3', INV4, A='SELN', Y='SEL', **V)
    return c


def rep_src(i):
    """Half-word bit feeding core bit i under each select line (WT12)."""
    return dict(T1=i, T2A=i // 2, T2B=10 + i // 2, T4A=i // 4, T4B=5 + i // 4, T4C=10 + i // 4, T4D=15 + i // 4)


def wiredtx():
    codes = {b: [f'{b}_CODE{k}' for k in range(8)] for b in ('MAIN', 'POST', 'TMDS')}
    ports = (['WTX_PH0', 'WTX_PH90', 'WTX_PH180', 'WTX_PH270', 'MODE_H', 'MODE_F'] + [f'D{i}' for i in range(40)]
             + ['WORD_CLK', 'WORD_CLK40', 'SER_EN', 'WTX_EXT', 'DX', 'POST_POL',
             'EN_MAIN', 'EN_POST', 'EN_TMDS', 'ISLAND_OFF', 'IBIAS']
             + codes['MAIN'] + codes['POST'] + codes['TMDS']
             + ['CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P', 'CMD_POST_N', 'CMD_TMDS_P', 'CMD_TMDS_N',
                'MAIN_BIAS', 'POST_BIAS', 'TMDS_BIAS', 'WTX_EXT_DATA', 'ATB_NBIAS', 'ATB_PBIAS', 'VDD', 'VSS'])
    c = Cell('pt_wiredtx', ports, row_width=420)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('BBM', BBM, SER_EN='SER_EN', WTX_EXT='WTX_EXT', SER='SER', EXT='EXT', **V)
    # rate field (MODE_H, MODE_F), WT12: the compact CMOS core (wtx_serq4c, path A) always runs at quarter
    # rate; 00 = quarter (rep1), 10 = half (rep2), 01 = full (rep4); 11 = half (rep2).  Session 6: the
    # generic static-CMOS serializer that code 11 used to select is removed (interface WT13).
    c.inst('MFI', INV1, A='MODE_F', Y='MFB', **V)
    c.inst('MFN', NOR, A='MODE_H', B='MFB', Y='MFC', **V)          # R4 = !MODE_H & MODE_F
    c.inst('SQN', INV1, A='SER', Y='SERQN', **V)
    c.inst('SQI', INV4, A='SERQN', Y='SERQ', **V)
    # 40-bit boundary (S3 / interface WT5): the digital launches a 40-bit quad word D0..D39 (D0 first on
    # the line) on WORD_CLK40 rising (line/40, 50 % duty).  A toggle flop on WORD_CLK (line/20) selects
    # D0..D19 for the load after WORD_CLK40 rises and D20..D39 for the next one; both serializers see
    # the selected 20-bit word DW0..DW19 at the same timing as the earlier 20-bit port.
    # WT19 (session 8, approved): the bit repetition of half / full rate is done by the digital; the
    # block always takes 40 CORE bits per WORD_CLK40 (= core line / 40 in every mode).  The toggle flop
    # on WORD_CLK selects D0..D19, then D20..D39 (WT8).  MODE still tells the core the repetition factor
    # (R2 / R4) for its postcursor latch (one LINE bit, not one core bit, late).
    c.inst('WS', W40, CK='WORD_CLK', RB='SER_EN', SEL='WSEL', SELB='WSELB', W40='WORD_CLK40', **V)
    for i in range(20):
        c.inst(f'WM{i}', MUXF, A=f'D{i}', B=f'D{i + 20}', S='WSEL', SB='WSELB', Y=f'DWB{i}', **V)
        c.inst(f'WI{i}', INV4, A=f'DWB{i}', Y=f'DW{i}', **V)
    c.inst('SQ', SERQ4, **{f'D{i}': f'DW{i}' for i in range(20)}, PH0='WTX_PH0', PH90='WTX_PH90',
           PH180='WTX_PH180', PH270='WTX_PH270', SERQ='SERQ', MQ='VDD', MH='VSS', MF='VSS', R2='MODE_H', R4='MFC', Y='QD', YB='QDB', DP='QDP', DPB='QDPB',
           WCKQ='WCKQ', **V)
    c.inst('WCO', INV2, A='WCKQ', Y='WCKN', **V)
    c.inst('WCB', INV16, A='WCKN', Y='WORD_CLK', **V)
    c.inst('PD', PREDRV, DQ='QD', DQB='QDB', DPQ='QDP', DPQB='QDPB',
           DX='DX', SERQ='SERQ', EXT='EXT', POST_POL='POST_POL',
           EN_MAIN='EN_MAIN', EN_POST='EN_POST', EN_TMDS='EN_TMDS', ISLAND_OFF='ISLAND_OFF',
           EXT_DATA='WTX_EXT_DATA', **{o: o for o in ['CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P',
                                                      'CMD_POST_N', 'CMD_TMDS_P', 'CMD_TMDS_N']}, **V)
    # bias reference: 10 uA sourced into IBIAS by the island bias output
    c.inst('BE', BIASEN, A='EN_MAIN', B='EN_POST', C='EN_TMDS', Y='BEN', YB='BENB', **V)
    c.dev('SWI', N, 'IBIAS', 'BEN', 'ATB_NBIAS', 4)
    c.dev('MN0', N, 'ATB_NBIAS', 'ATB_NBIAS', 'VSS', 2, 2.0)
    c.dev('PDN', N, 'ATB_NBIAS', 'BENB', 'VSS', 2)
    for b, cell, en in (('MAIN', IDAC2M, 'EN_MAIN'), ('POST', IDAC2M, 'EN_POST'), ('TMDS', IDAC1, 'EN_TMDS')):
        c.inst(f'DAC_{b}', cell, NB='ATB_NBIAS', EN=en, ISLAND_OFF='ISLAND_OFF', BIAS=f'{b}_BIAS',
               PB='ATB_PBIAS' if b == 'MAIN' else f'PB_{b}',
               **{f'C{k}': codes[b][k] for k in range(8)}, **V)
    return c


def biasen():
    """Y = EN_MAIN | EN_POST | EN_TMDS (and complement)."""
    c = Cell('wtx_or3', ['A', 'B', 'C', 'Y', 'YB', 'VDD', 'VSS'])
    c.dev('PA', P, 'X1', 'A', 'VDD', 4); c.dev('PB', P, 'X2', 'B', 'X1', 4); c.dev('PC', P, 'YB', 'C', 'X2', 4)
    c.dev('NA', N, 'YB', 'A', 'VSS', 1); c.dev('NB', N, 'YB', 'B', 'VSS', 1); c.dev('NC', N, 'YB', 'C', 'VSS', 1)
    c.dev('IN', N, 'Y', 'YB', 'VSS', 1); c.dev('IP', P, 'Y', 'YB', 'VDD', 2)
    return c


BBM = bbm()
TSPCD = Macro('ct_tspcd')
DIV5C = Macro('ct_div5')
MUX4W = Macro('wtx_mux4')
CINV8 = Macro('wtx_cinv8')
W40 = w40()
XOR2 = xor2()
W40 = w40()
SERQ = serq()
# The compact core is the hand-placed macro built by serq4_macro.py (generated/fast/wtx_serq4.*):
# schematic, layout and LVS read its intended netlist.  serq4() above is the earlier gate-level core
# (kept for reference; it failed extracted, see README).
SERQ4 = Macro('wtx_serq4c')   # path A: CMOS quarter-rate core (serq4c_macro.py)
PHBUF = phbuf()
PREDRV = predrv()
BIASEN = biasen()
TOP = wiredtx()

def hsbias():
    """USB HS bias DAC (P3-12): HS_PBIAS for the pads wirepad HS current mirror.

    10 uA in IBIAS -> NMOS diode/mirror -> PMOS reference diode (W2/L1);
    8 binary PMOS sources of W/L = (2^k)/4 (unit ~1.25 uA) switched into OUT,
    loaded by an NMOS triode resistor (W2.5/L1, gate at VDD while enabled,
    ~2 kOhm) to VSS: 0 ... ~0.6 V.  Disabled (EN=0): sources off, the load
    released and HS_PBIAS pulled to VDD (wirepad HS devices off).  No
    calibration of the absolute value (per-board trim)."""
    codes = [f'C{k}' for k in range(8)]
    c = Cell('pt_wtx_hsbias', ['IBIAS', 'EN'] + codes + ['HS_PBIAS', 'VDD', 'VSS'], row_width=150)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('EI', INV1, A='EN', Y='ENB', **V)
    c.dev('SWI', N, 'IBIAS', 'EN', 'NB', 4)
    c.dev('MN0', N, 'NB', 'NB', 'VSS', 2, 2.0)
    c.dev('PDN', N, 'NB', 'ENB', 'VSS', 2)
    c.dev('MN1', N, 'PB', 'NB', 'VSS', 2, 2.0)
    c.dev('MP0', P, 'PB', 'PB', 'VDD', 2, 1.0)
    c.dev('PBU', P, 'PB', 'EN', 'VDD', 1)
    for k in range(8):
        c.inst(f'CI{k}', INV1, A=f'C{k}', Y=f'CB{k}', **V)
        w = 2 ** k
        nf = max(1, w // 16)
        for f in range(nf):
            c.dev(f'MS{k}_{f}' if nf > 1 else f'MS{k}', P, f'S{k}', 'PB', 'VDD', min(w, 16), 4.0)
        c.dev(f'SW{k}', P, 'HS_PBIAS', f'CB{k}', f'S{k}', 2)
    c.dev('RL', N, 'HS_PBIAS', 'EN', 'VSS', 2.5, 1.0)   # triode load ~2 kOhm
    c.dev('PU', P, 'HS_PBIAS', 'EN', 'VDD', 4)         # disabled -> VDD
    return c


HSBIAS = hsbias()

# Placement order for the device-level layout (prefix match, first wins):
# each clock divider sits between the stage it is clocked with and the
# stage it clocks.
LAYOUT_ORDER = ['BBM/', 'CG/', 'SR/MY/', 'SR/MYB/', 'SR/MD/', 'SR/MDB/', 'SR/C3/', 'SR/B', 'SR/A', 'SR/D5/',
                'SR/R0/', 'SR/R1/', 'SR/R2/', 'SR/R3/', 'SR/DI', 'SQ/', 'PD/', '']


def layout_devices(cell=None):
    devs = (cell or TOP).flat_devices()
    # the hand-placed core macro (SQ) alone in row 0: no parent metal crosses it
    rank = lambda d: -1 if d.name == 'SQ' else next(i for i, p in enumerate(LAYOUT_ORDER) if d.name.startswith(p))
    return sorted(devs, key=rank)

if __name__ == '__main__':
    import sys
    from pathlib import Path
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('wiredtx.spice')
    (out.parent / 'hsbias.spice').write_text('* pt_wtx_hsbias: USB HS bias DAC for the pads wirepad HS_PBIAS node\n'
                                             '* Generated by cells.py. GF180 gf180mcuD 3.3 V MOS only.\n' + netlist(HSBIAS))
    out.write_text('* pt_wiredtx: wired-TX serializer, final DDR mux, pre-driver and tail-bias DACs\n'
                   '* Generated by cells.py (single source of truth). GF180 gf180mcuD 3.3 V MOS only.\n'
                   + netlist(TOP))
    print(out, len(TOP.flat_devices()), 'devices')
