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
                           'SW0', 'SW1', 'SW2', 'SW3', 'WCK0', 'WCK2', 'FCK', 'FCKB', 'RSTB', 'RST', 'VDD', 'VSS'],
             row_width=140)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('RI', INV4, A='SER', Y='RST', **V)
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
    # mode one-hots gated by SER: with the serializer off no window opens and
    # the window cells only see toggling gates (no switching outputs)
    c.inst('GQ', NAND, A='MQ', B='SER', Y='MQSB', **V)
    c.inst('GQI', INV2, A='MQSB', Y='MQS', **V)
    c.inst('GH', NAND, A='MH', B='SER', Y='MHSB', **V)
    c.inst('GHI', INV2, A='MHSB', Y='MHS', **V)
    c.inst('GF', NAND, A='MF', B='SER', Y='MFSB', **V)
    c.inst('GFI', INV2, A='MFSB', Y='MFS', **V)
    # window k (compact cells): S = MQ&(quarter pair) | MH&(half pair) | MF&(full pair)
    # identical, equally loaded phase buffers for the windows: each quarter
    # phase copy feeds exactly two window inputs; the half-rate windows get
    # their own PH0/PH180 copies (the raw phases also clock the counters)
    for ph in ('0', '90', '180', '270'):
        c.inst(f'PQ{ph}A', INV2, A=f'PH{ph}', Y=f'PQN{ph}', **V)
        c.inst(f'PQ{ph}B', INV8, A=f'PQN{ph}', Y=f'PQ{ph}', **V)
    for ph in ('0', '180'):
        c.inst(f'PH{ph}HA', INV2, A=f'PH{ph}', Y=f'PHN{ph}', **V)
        c.inst(f'PH{ph}HB', INV8, A=f'PHN{ph}', Y=f'PHH{ph}', **V)
    src = [(('PQ0', 'PQ270'), ('A0', 'PHH0'), ('J0B', 'J1B')),
           (('PQ90', 'PQ0'), ('A1', 'PHH180'), ('J0', 'J1B')),
           (('PQ180', 'PQ90'), ('A0B', 'PHH0'), ('J0', 'J1')),
           (('PQ270', 'PQ180'), ('A1B', 'PHH180'), ('J0B', 'J1'))]
    for k, (q, h, f) in enumerate(src):
        c.inst(f'WIN{k}', WIN, MQ='MQS', QA=q[0], QB=q[1], MH='MHS', HA=h[0], HB=h[1], MF='MFS', FA=f[0], FB=f[1],
               S=f'SW{k}', SX=f'SWN{k}', **V)
        # equal loads on every window: a retiming-clock inverter (used for
        # windows 0 and 2) and a latch-input NAND (dummy for windows 1 and 3)
        c.inst(f'WC{k}', INV4, A=f'SWN{k}', Y=f'WCK{k}', **V)
        if k in (0, 2):   # dummies matching the latch NOR inputs on windows 1 and 3
            c.inst(f'WD{k}', NOR2X, A=f'SW{k}', B='VSS', Y=f'WDN{k}', **V)
    # register clock: SR latch set by window 1 and reset by window 3 (or
    # RST): a 2-UI-wide clock rising ~0.8 ns after UI 1 in every mode, low
    # while SER=0.  The shift registers shift on it, so the streams change
    # roughly half a register period before the retiming capture at window 2
    c.inst('LA', NOR2X, A='SW3', B='LQB', Y='LQ', **V)
    c.inst('LB', NOR2X, A='SW1', B='LQ', Y='LQB', **V)
    c.dev('LRS', N, 'LQ', 'RST', 'VSS', 2)
    c.inst('RCA', INV4, A='LQ', Y='RCKN', **V)
    c.inst('RCB', INV24, A='RCKN', Y='FCK', **V)
    c.inst('RCC', INV4, A='LQB', Y='RCKM', **V)
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
    c = Cell('wtx_srbit', ['P', 'NXT', 'LD', 'LDB', 'CK', 'CKB', 'O', 'OT', 'VDD', 'VSS'])
    c.inst('M', MUXF, A='P', B='NXT', S='LD', SB='LDB', Y='X', VDD='VDD', VSS='VSS')
    c.inst('F', DFFS, D='X', CK='CK', CKB='CKB', Q='OT', QB='O', VDD='VDD', VSS='VSS')
    return c


def sr5():
    """5:1 parallel-load shift register; P0 is sent first."""
    c = Cell('wtx_sr5', ['P0', 'P1', 'P2', 'P3', 'P4', 'LD', 'LDB', 'CK', 'CKB', 'O', 'OT', 'VDD', 'VSS'])
    for k in range(5):
        c.inst(f'B{k}', SRBIT, P=f'P{k}', NXT=('VSS' if k == 4 else f'O{k+1}'), LD='LD', LDB='LDB', CK='CK',
               CKB='CKB', O=('O' if k == 0 else f'O{k}'), OT=('OT' if k == 0 else f'OT{k}'), VDD='VDD', VSS='VSS')
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
TSPCD = Macro('ct_tspcd')
MUX4 = Macro('ct_mux4')
WIN = Macro('wtx_win')
INV8M = Macro('wtx_cinv8')
NAND3S = nand3('wtx_nand3s', 3, 2)
SEL3 = sel3()
SRBIT = srbit()
SR5 = sr5()
DIV5 = div5()
NAND_O = nand2('wtx_nand2o', wn=4, wp=4)


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
    """Data select (serializer / external) and per-branch gated complementary commands."""
    outs = ['CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P', 'CMD_POST_N', 'CMD_TMDS_P', 'CMD_TMDS_N']
    c = Cell('wtx_predrv', ['D', 'DB', 'DP', 'DPB', 'DX', 'SER', 'EXT', 'EN_MAIN', 'EN_POST',
                            'EN_TMDS', 'ISLAND_OFF', 'EXT_DATA'] + outs + ['VDD', 'VSS'], row_width=150)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('XB', INV1, A='DX', Y='DXB', **V)
    c.inst('XO', INV1, A='DXB', Y='EXT_DATA', **V)   # status copy of the external data
    # serializer / external select: two NAND levels (DS = D&SER | DX&EXT)
    c.inst('S1', NAND_O, A='D', B='SER', Y='NS1', **V)
    c.inst('X1', NAND_O, A='DX', B='EXT', Y='NX1', **V)
    c.inst('O1', NAND_O, A='NS1', B='NX1', Y='DS', **V)
    c.inst('S2', NAND_O, A='DB', B='SER', Y='NS2', **V)
    c.inst('X2', NAND_O, A='DXB', B='EXT', Y='NX2', **V)
    c.inst('O2', NAND_O, A='NS2', B='NX2', Y='DSB', **V)
    # postcursor (serializer only): the same two NAND levels, so it keeps
    # its one-UI offset from the main data at the outputs
    c.inst('P1', NAND_O, A='DP', B='SER', Y='NP1', **V)
    c.inst('P1O', NAND_O, A='NP1', B='VDD', Y='DPS', **V)
    c.inst('P2', NAND_O, A='DPB', B='SER', Y='NP2', **V)
    c.inst('P2O', NAND_O, A='NP2', B='VDD', Y='DPSB', **V)
    for br, (pos, neg, en) in {'MAIN': ('DSB', 'DS', 'EN_MAIN'), 'TMDS': ('DSB', 'DS', 'EN_TMDS'),
                               'POST': ('DPS', 'DPSB', 'EN_POST')}.items():
        for leg, data in (('P', pos), ('N', neg)):
            o = f'CMD_{br}_{leg}'
            c.inst(f'G_{br}_{leg}', NAND_O, A=data, B=en, Y=f'NB_{br}_{leg}', **V)
            c.inst(f'O_{br}_{leg}', INV4, A=f'NB_{br}_{leg}', Y=o, **V)
            c.dev(f'CL_{br}_{leg}', N, o, 'ISLAND_OFF', 'VSS', 2)
    return c


def idac(diode_fingers):
    """8-bit binary PMOS current DAC into a diode that mirrors into a pad tail.

    LSB = 5 uA into the diode (unit PMOS W=1/L=1 against a W=2/L=1 reference
    diode carrying 10 uA).  The diode (W=20/L=1 per finger) is 1/16 of the
    selected pad tail for that branch, so the tail LSB is about 80 uA.
    """
    codes = [f'C{k}' for k in range(8)]
    c = Cell(f'wtx_idac{diode_fingers}', ['NB', 'EN', 'ISLAND_OFF'] + codes + ['BIAS', 'PB', 'VDD', 'VSS'],
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
            c.dev(f'MS{k}_{f}' if nf > 1 else f'MS{k}', P, f'S{k}', 'PB', 'VDD', min(w, 16), 1.0)
        c.dev(f'SW{k}', P, 'BIAS', f'CB{k}', f'S{k}', 2 if k < 5 else 4 * 2 ** (k - 5))
    for f in range(diode_fingers):
        c.dev(f'MD{f}' if diode_fingers > 1 else 'MD', N, 'BIAS', 'BIAS', 'VSS', 20, 1.0)
    c.dev('PDE', N, 'BIAS', 'ENB', 'VSS', 2)
    c.dev('PDI', N, 'BIAS', 'ISLAND_OFF', 'VSS', 2)
    return c


IDAC2 = idac(2)
IDAC1 = idac(1)


def serq():
    """20:1 serializer behind the window generator.

    Two 10-bit line words per WORD_CLK period (D0..D9 first, D0 first on the
    line) load four 5:1 shift registers (stream s = D[s], D[s+4], ..D[s+16])
    on the register clock FCK (period 4 UI in every mode).  TSPC retiming
    flops (timing's ct_tspcd) on FCK fall (A*) and FCK rise (B*, C3) keep
    each stream stable over its window(s); four ct_mux4 one-hot muxes
    select with SW0..SW3.  Main: A0, A1, B2, B3; postcursor (main delayed one
    UI): C3, A0, B1, B2."""
    ports = [f'D{i}' for i in range(20)] + ['SW0', 'SW1', 'SW2', 'SW3', 'WCK0', 'WCK2', 'FCK', 'FCKB', 'RSTB', 'RST',
                                             'WORD_CLK',
                                             'Y', 'YB', 'DP', 'DPB', 'VDD', 'VSS']
    c = Cell('wtx_serq', ports, row_width=260)
    V = dict(VDD='VDD', VSS='VSS')
    S = {f'S{k}': f'SW{k}' for k in range(4)}
    c.inst('D5', DIV5, CK='FCK', CKB='FCKB', RB='RSTB', LD='LD', LDB='LDB', WORD_CLK='WORD_CLK', **V)
    # input inverters: the word inputs see MOS gates only (no diffusion path
    # into the island rail when the island is off and the source is high)
    for i in range(20):
        c.inst(f'DI{i}', INV1, A=f'D{i}', Y=f'DN{i}', **V)
    for st in range(4):
        c.inst(f'R{st}', SR5, **{f'P{k}': f'DN{st + 4*k}' for k in range(5)}, LD='LD', LDB='LDB', CK='FCK',
               CKB='FCKB', O=f'S{st}', OT=f'ST{st}', **V)
    # dual-rail retiming (TSPC, timing's ct_tspcd) clocked by the window
    # pulses: A at window 2, B at window 0, C3 at window 2, so every stream
    # changes after the windows that use it.  S* carry inverted data, ST*
    # true data; no inverter sits between the flops and the muxes.
    for pol, src in (('', 'S'), ('T', 'ST')):
        for st in range(4):
            c.inst(f'A{pol}{st}', TSPCD, CK='WCK2', D=f'{src}{st}', Q=f'A{pol}{st}', ENB='RST', **V)
        for st in (1, 2, 3):
            c.inst(f'B{pol}{st}', TSPCD, CK='WCK0', D=f'A{pol}{st}', Q=f'B{pol}{st}', ENB='RST', **V)
        c.inst(f'C{pol}3', TSPCD, CK='WCK2', D=f'B{pol}3', Q=f'C{pol}3', ENB='RST', **V)
    c.inst('MY', MUX4, A0='AT0', A1='AT1', A2='BT2', A3='BT3', Y='Y', **S, **V)
    c.inst('MYB', MUX4, A0='A0', A1='A1', A2='B2', A3='B3', Y='YB', **S, **V)
    c.inst('MD', MUX4, A0='CT3', A1='AT0', A2='BT1', A3='BT2', Y='DP', **S, **V)
    c.inst('MDB', MUX4, A0='C3', A1='A0', A2='B1', A3='B2', Y='DPB', **S, **V)
    return c


def wiredtx():
    codes = {b: [f'{b}_CODE{k}' for k in range(8)] for b in ('MAIN', 'POST', 'TMDS')}
    ports = (['WTX_PH0', 'WTX_PH90', 'WTX_PH180', 'WTX_PH270', 'MODE_H', 'MODE_F'] + [f'D{i}' for i in range(20)] + ['WORD_CLK', 'SER_EN', 'WTX_EXT', 'DX',
             'EN_MAIN', 'EN_POST', 'EN_TMDS', 'ISLAND_OFF', 'IBIAS']
             + codes['MAIN'] + codes['POST'] + codes['TMDS']
             + ['CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P', 'CMD_POST_N', 'CMD_TMDS_P', 'CMD_TMDS_N',
                'MAIN_BIAS', 'POST_BIAS', 'TMDS_BIAS', 'WTX_EXT_DATA', 'ATB_NBIAS', 'ATB_PBIAS', 'VDD', 'VSS'])
    c = Cell('pt_wiredtx', ports, row_width=420)
    V = dict(VDD='VDD', VSS='VSS')
    c.inst('BBM', BBM, SER_EN='SER_EN', WTX_EXT='WTX_EXT', SER='SER', EXT='EXT', **V)
    W = {f'SW{k}': f'SW{k}' for k in range(4)}
    W.update(WCK0='WCK0', WCK2='WCK2')
    c.inst('CG', PHBUF, PH0='WTX_PH0', PH90='WTX_PH90', PH180='WTX_PH180', PH270='WTX_PH270', SER='SER',
           MODE_H='MODE_H', MODE_F='MODE_F', FCK='FCK', FCKB='FCKB', RSTB='RSTB', RST='RST', **W, **V)
    c.inst('SR', SERQ, **{f'D{i}': f'D{i}' for i in range(20)}, **W, FCK='FCK', FCKB='FCKB', RSTB='RSTB', RST='RST',
           WORD_CLK='WORD_CLK', Y='SD', YB='SDB', DP='SDP', DPB='SDPB', **V)
    c.inst('PD', PREDRV, D='SD', DB='SDB', DP='SDP', DPB='SDPB', DX='DX', SER='SER', EXT='EXT',
           EN_MAIN='EN_MAIN', EN_POST='EN_POST', EN_TMDS='EN_TMDS', ISLAND_OFF='ISLAND_OFF',
           EXT_DATA='WTX_EXT_DATA', **{o: o for o in ['CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P',
                                                      'CMD_POST_N', 'CMD_TMDS_P', 'CMD_TMDS_N']}, **V)
    # bias reference: 10 uA sourced into IBIAS by the island bias output
    c.inst('BE', BIASEN, A='EN_MAIN', B='EN_POST', C='EN_TMDS', Y='BEN', YB='BENB', **V)
    c.dev('SWI', N, 'IBIAS', 'BEN', 'ATB_NBIAS', 4)
    c.dev('MN0', N, 'ATB_NBIAS', 'ATB_NBIAS', 'VSS', 2, 2.0)
    c.dev('PDN', N, 'ATB_NBIAS', 'BENB', 'VSS', 2)
    for b, cell, en in (('MAIN', IDAC2, 'EN_MAIN'), ('POST', IDAC2, 'EN_POST'), ('TMDS', IDAC1, 'EN_TMDS')):
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
SERQ = serq()
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
LAYOUT_ORDER = ['BBM/', 'CG/', 'SR/MY', 'SR/MD', 'SR/C', 'SR/B', 'SR/A', 'SR/D5/',
                'SR/R0/', 'SR/R1/', 'SR/R2/', 'SR/R3/', 'SR/DI', 'PD/', '']


def layout_devices(cell=None):
    devs = (cell or TOP).flat_devices()
    rank = lambda d: next(i for i, p in enumerate(LAYOUT_ORDER) if d.name.startswith(p))
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
