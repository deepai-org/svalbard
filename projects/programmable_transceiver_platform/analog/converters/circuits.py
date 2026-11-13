"""Transistor-level circuits of the converter family (gf180mcuD devices only).

Each builder returns a convkit.Circuit whose device list is the schematic and
whose rows describe the layout floorplan. Sizes are deliberately conservative;
see README.md for the reasoning and the measured consequences.
"""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
from convkit import Mos, Cap, Res, Macro, Circuit  # noqa: E402

N, P = 'nfet_03v3', 'pfet_03v3'
HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------ small logic
def inv(p, a, y, vdd='VDD', vss='VSS', wn=1.0, wp=2.0, flip=False):
    return [Mos(p + 'N', N, wn, 0.28, y, a, vss, vss, flip=flip),
            Mos(p + 'P', P, wp, 0.28, y, a, vdd, vdd, flip=flip)]


def nand2(p, a, b, y, vdd='VDD', vss='VSS', wn=2.0, wp=2.0):
    return [Mos(p + 'NA', N, wn, 0.28, y, a, p + '_m', vss),
            Mos(p + 'NB', N, wn, 0.28, p + '_m', b, vss, vss),
            Mos(p + 'PA', P, wp, 0.28, y, a, vdd, vdd),
            Mos(p + 'PB', P, wp, 0.28, y, b, vdd, vdd)]


def nor2(p, a, b, y, vdd='VDD', vss='VSS', wn=1.0, wp=4.0):
    return [Mos(p + 'NA', N, wn, 0.28, y, a, vss, vss),
            Mos(p + 'NB', N, wn, 0.28, y, b, vss, vss),
            Mos(p + 'PA', P, wp, 0.28, p + '_m', a, vdd, vdd),
            Mos(p + 'PB', P, wp, 0.28, y, b, p + '_m', vdd)]


# ------------------------------------------------------------ refbuf
RES_UNIT = 70.7      # um; 10.0 pF per cap_mim_2f0 unit (1.99 fF/um2 + 0.238 fF/um)


def refbuf(name='pt_refbuf'):
    """Converter reference buffer.

    NMOS-input OTA (VREF0 vs VREF) -> dominant pole at X (10 pF) -> NMOS source
    follower with 500 uA mirrored sink, 100 pF MIM reservoir on VREF. ACT =
    EN & ~OVR; ACT=0 removes every current, pulls the follower gate to VSS and
    leaves VREF high impedance so ATB0 can force it (debug.bias_override.refbuf):
    the PMOS mirrors hang from a header (VDDA) that opens with ACT so no path
    remains through the input pairs.
    READY = ACT & (VREF > VREF0 - ~25 mV) from a deliberately unbalanced
    comparator.
    """
    d = []
    # control logic
    d += inv('IO', 'OVR', 'OVRB')
    d += nand2('NA', 'EN', 'OVRB', 'ACTB')
    d += inv('IA', 'ACTB', 'ACT')
    # bias: IBIAS -> switch -> diode NB (10 uA unit = W4/L2)
    d += [Mos('MSW', N, 4, 0.5, 'IBIAS', 'ACT', 'NB', 'VSS'),
          Mos('MD', N, 4, 2, 'NB', 'NB', 'VSS', 'VSS'),
          Mos('MPD', N, 1, 0.5, 'NB', 'ACTB', 'VSS', 'VSS')]
    # OTA: NMOS pair, PMOS mirror; X is the high-impedance output
    d += [Mos('MT', N, 8, 2, 'TN', 'NB', 'VSS', 'VSS'),
          Mos('M1', N, 10, 1, 'XA', 'VREF0', 'TN', 'VSS'),
          Mos('M2', N, 10, 1, 'X', 'VREF', 'TN', 'VSS'),
          Mos('MH', P, 8, 0.28, 'VDDA', 'ACTB', 'VDD', 'VDD'),
          Mos('M3', P, 4, 2, 'XA', 'XA', 'VDDA', 'VDD'),
          Mos('M4', P, 4, 2, 'X', 'XA', 'VDDA', 'VDD'),
          Mos('MXD', N, 1, 0.5, 'X', 'ACTB', 'VSS', 'VSS')]
    # follower and sink
    d += [Mos('MF', N, 10, 0.5, 'VDD', 'X', 'VREF', 'VSS', m=4),
          Mos('MS', N, 20, 2, 'VREF', 'NB', 'VSS', 'VSS', m=10)]
    # READY comparator (MA twice MB: trips ~25 mV below VREF0)
    d += [Mos('MTC', N, 4, 2, 'TC', 'NB', 'VSS', 'VSS'),
          Mos('MA', N, 8, 1, 'YA', 'VREF', 'TC', 'VSS', m=2),
          Mos('MB', N, 8, 1, 'Y', 'VREF0', 'TC', 'VSS'),
          Mos('MC3', P, 4, 1, 'YA', 'YA', 'VDDA', 'VDD'),
          Mos('MC4', P, 4, 1, 'Y', 'YA', 'VDDA', 'VDD'),
          Mos('MYD', N, 1, 0.5, 'Y', 'ACTB', 'VSS', 'VSS')]
    d += inv('IY', 'Y', 'YB')
    d += nor2('NR', 'YB', 'ACTB', 'READY')
    # compensation and reservoir
    d += [Cap('CC', RES_UNIT, RES_UNIT, 'X', 'VSS'),
          Cap('CRA', RES_UNIT, RES_UNIT, 'VREF', 'VSS', m=5),
          Cap('CRB', RES_UNIT, RES_UNIT, 'VREF', 'VSS', m=5)]
    logic = ['ION', 'IOP', 'NANA', 'NANB', 'NAPA', 'NAPB', 'IAN', 'IAP', 'IYN', 'IYP',
             'NRNA', 'NRNB', 'NRPA', 'NRPB']
    analog = ['MSW', 'MD', 'MPD', 'MT', 'M1', 'M2', 'MH', 'M3', 'M4', 'MXD', 'MTC', 'MA', 'MB',
              'MC3', 'MC4', 'MYD']
    rows = [['CRA'], ['CRB'], ['CC', 'MF', 'MS'], analog + logic]
    c = Circuit(name, ['VDD', 'VSS', 'VREF0', 'VREF', 'IBIAS', 'EN', 'OVR', 'READY'], d, rows=rows,
                wide_nets={'VDD': 2.0, 'VSS': 2.0, 'VREF': 2.0})
    return c


# ------------------------------------------------------------ shared pieces
MACROS = HERE / 'generated' / 'macros'


def macro(cell, pins, name='XL', strap_dir='up', x=0.0):
    from convkit import macro_geometry
    m = Macro(name, cell, MACROS / f'{cell}.gds', MACROS / f'{cell}.lef', MACROS / f'{cell}.pnl.v',
              pins, strap_dir=strap_dir, x=x)
    return m


def pin_x(m, pin):
    from convkit import macro_geometry
    return macro_geometry(m)['pins'][pin][0]['x']


def bias(p, act, actb, nb='NB'):
    """IBIAS (10 uA in) -> enable switch -> diode NB (unit W4/L2); NB=0 when off."""
    return [Mos(p + 'SW', N, 4, 0.5, 'IBIAS', act, nb, 'VSS'),
            Mos(p + 'D', N, 4, 2, nb, nb, 'VSS', 'VSS'),
            Mos(p + 'PD', N, 1, 0.5, nb, actb, 'VSS', 'VSS')]


def clkrx(p, inp, inn, out, act, nb='NB'):
    """Low-swing differential clock (CM 1.65 V, 0.4 V peak) to CMOS; 40 uA tail.
    out = (inp > inn) & act; with act=0 the tail is off and out is held low."""
    d = [Mos(p + 'MT', N, 16, 2, p + 't', nb, 'VSS', 'VSS'),
         Mos(p + 'M1', N, 4, 0.5, p + 'a', inp, p + 't', 'VSS'),
         Mos(p + 'M2', N, 4, 0.5, p + 'x', inn, p + 't', 'VSS'),
         Mos(p + 'M3', P, 4, 0.5, p + 'a', p + 'a', 'VDD', 'VDD'),
         Mos(p + 'M4', P, 4, 0.5, p + 'x', p + 'a', 'VDD', 'VDD'),
         Mos(p + 'MU', P, 1, 0.28, p + 'x', act, 'VDD', 'VDD')]
    d += inv(p + 'I1', p + 'x', p + 'y1')
    d += inv(p + 'I2', p + 'y1', p + 'y2')
    d += nand2(p + 'G', p + 'y2', act, p + 'z')
    d += inv(p + 'I3', p + 'z', out, wn=2, wp=4)
    return d


def names(devs):
    return [d.name for d in devs]


# ------------------------------------------------------------ DAC
DAC_LSB_W = 0.391          # um of W/L=2 NMOS per LSB (0.9775 uA); diode W4 = 10 uA


def dac(name='pt_dac_i'):
    """10-bit segmented (63 x 16-LSB thermometer + 8/4/2/1 binary) NMOS current-
    steering DAC, 1 mA full scale, registered in dac_logic (std cells).
    Loads: VDD -> PMOS header -> RS (1.1k) -> T -> 1k to each internal leg, so
    the common mode is VDD - 1.65 V and the differential swing +/-1 V.
    OUT_EN NMOS series switches isolate OUTP/OUTN (rf_tx_external_baseband).
    """
    pins = {'clk': 'CK', 'en': 'EN', 'hold_zero': 'HOLD_ZERO', 'out_en': 'OUT_EN',
            'load_en_b': 'LOAD_ENB', 'VDD': 'VDD', 'VSS': 'VSS'}
    pins.update({f'code_tc[{i}]': f'CODE{i}' for i in range(10)})
    pins.update({f'th[{k}]': f'TH{k}' for k in range(63)})
    pins.update({f'thb[{k}]': f'THB{k}' for k in range(63)})
    pins.update({f'bn[{j}]': f'BN{j}' for j in range(4)})
    pins.update({f'bnb[{j}]': f'BNB{j}' for j in range(4)})
    m = macro('dac_logic', pins)
    d = [m]
    d += inv('IE', 'EN', 'ENB')
    d += bias('B', 'EN', 'ENB', nb='ATB_BIAS')
    d += clkrx('K', 'CLKP', 'CLKN', 'CK', 'EN', nb='ATB_BIAS')
    sw, cs, cc = [], [], []
    cells = [(f'TH{k}', f'THB{k}', f'th[{k}]', 16) for k in range(63)]
    cells += [(f'BN{j}', f'BNB{j}', f'bn[{j}]', 1 << j) for j in (0, 1, 2, 3)]
    for i, (a, b, pa, wgt) in enumerate(cells):
        xa = pin_x(m, pa)
        xb = pin_x(m, pa.replace('th[', 'thb[').replace('bn[', 'bnb['))
        node = f'CS{i}'
        sw += [Mos(f'SA{i}', N, 1, 0.28, 'ONI', a, node, 'VSS', flip=True, x=xa),
               Mos(f'SB{i}', N, 1, 0.28, 'OPI', b, node, 'VSS', flip=True, x=xb)]
        cs += [Mos(f'CS{i}', N, round(DAC_LSB_W * wgt, 3), 2, f'CD{i}', 'ATB_BIAS', 'VSS', 'VSS', x=xa - 0.8)]
        # v3: low-voltage cascode per cell (CS Vds ~0.5 V). v2 cells saw the full
        # ~1 V leg swing on an L=2 source: odd-order static error up to ~10 LSB.
        cc += [Mos(f'CC{i}', N, round(2 * DAC_LSB_W * wgt, 3), 0.5, node, 'VCASC', f'CD{i}', 'VSS', x=xa - 0.8)]
    d += sw + cs + cc
    # Cascode bias: 10 uA (PMOS mirror of the NB reference) into a W1/L3 diode.
    cb = [Mos('KBN', N, 4, 2, 'KPG', 'ATB_BIAS', 'VSS', 'VSS'),
          Mos('KBP1', P, 4, 1, 'KPG', 'KPG', 'VDD', 'VDD'),
          Mos('KBP2', P, 4, 1, 'VCASC', 'KPG', 'VDD', 'VDD'),
          Mos('KBD', N, 1, 3, 'VCASC', 'VCASC', 'VSS', 'VSS'),
          Mos('KPD', N, 1, 0.5, 'VCASC', 'ENB', 'VSS', 'VSS'),
          # v4 (CNV-03): 1 pF MIM decaps on the current-source gate (ATB_BIAS) and the cascode
          # gate. Extracted v3: CK/CLKN couple 21 fF onto ATB_BIAS and 7.6 fF onto HG, giving a
          # +/-5.5% FS 40 MHz ripple and a 4.36 LSB static bow (schematic with decaps <= 1.7 LSB).
          # Mitigation, not isolation: the 21 fF divider only drops ~1.7 -> 2.7 pF (ripple -37 %);
          # shielding CK/CLKN from ATB_BIAS/HG is the real fix. Cost: bias + CM loop settle
          # ~0.9 us after EN at ss 22-32C 3.10 V (bench DAC_T0 900 ns).
          Cap('CDAB', 22, 22, 'ATB_BIAS', 'VSS'),
          Cap('CDVC', 22, 22, 'VCASC', 'VSS')]
    # v3 common-mode loop (v2: passive RS, CM 1.43 V tt, 0.99-1.83 V corners):
    # sense R 2 x 20k -> CMS; reference VDD/2 (2 x 50k); 5T NMOS OTA
    # (40 uA tail) drives the PMOS header gate HG; Miller cap HG-T (~1 pF) splits
    # the HG and T poles (T is high-impedance: header ro || sense R). CMS high -> HG
    # up -> header weaker -> T and the CM fall. Disabled: HG pulled to VDD.
    cm = [Res('RCP', 1, 20, 'OPI', 'CMS', 'VSS'), Res('RCN', 1, 20, 'ONI', 'CMS', 'VSS'),
          Res('RDA', 1, 50, 'VDD', 'CMR', 'VSS'), Res('RDB', 1, 50, 'CMR', 'CMRF', 'VSS'),
          # v4: footer so the VDD/2 divider (3.3 V / 100k = 33 uA) is off at EN=0 ('safe' test).
          Mos('MDF', N, 4, 0.28, 'CMRF', 'EN', 'VSS', 'VSS'),
          Mos('OTT', N, 16, 2, 'OTS', 'ATB_BIAS', 'VSS', 'VSS'),
          Mos('OT1', N, 4, 1, 'OTD', 'CMS', 'OTS', 'VSS'),
          Mos('OT2', N, 4, 1, 'HG', 'CMR', 'OTS', 'VSS'),
          Mos('OT3', P, 4, 1, 'OTD', 'OTD', 'VDD', 'VDD'),
          Mos('OT4', P, 4, 1, 'HG', 'OTD', 'VDD', 'VDD'),
          Mos('OTU', P, 2, 0.28, 'HG', 'LOAD_EN', 'VDD', 'VDD'),
          Cap('OTC', 22, 22, 'HG', 'T')]
    cm += inv('ILE', 'LOAD_ENB', 'LOAD_EN')
    loads = [Mos('MHDR', P, 10, 0.5, 'T', 'HG', 'VDD', 'VDD', m=4),
             Res('RLP', 4, 4, 'T', 'OPI', 'VSS'),
             Res('RLN', 4, 4, 'T', 'ONI', 'VSS'),
             Mos('MOP', N, 10, 0.28, 'OPI', 'OUT_EN', 'OUTP', 'VSS', m=2),
             Mos('MON', N, 10, 0.28, 'ONI', 'OUT_EN', 'OUTN', 'VSS', m=2)]
    d += cb + cm + loads
    misc = [x for x in d if x is not m and x not in sw and x not in cs and x not in cc and not isinstance(x, Cap)]
    caps = [x for x in d if isinstance(x, Cap)]
    rows = [names(misc), names(caps), names(cs), names(cc), names(sw), [m.name]]
    ports = ['VDD', 'VSS', 'OUTP', 'OUTN', 'IBIAS', 'CLKP', 'CLKN', 'EN', 'HOLD_ZERO'] + \
            [f'CODE{i}' for i in range(10)] + ['ATB_BIAS']
    return Circuit(name, ports, d, rows=rows, wide_nets={'VDD': 2.0, 'VSS': 2.0, 'OPI': 1.0, 'ONI': 1.0, 'T': 1.0})


# ------------------------------------------------------------ ADC
MIM_CA, MIM_CP = 1.99, 0.238      # fF/um2, fF/um (PDK cap_mim_2f0_m4m5_noshield model)


def mim_side(c_ff):
    """Square MIM side (um) giving c_ff with the PDK area+perimeter model."""
    a, b = MIM_CA, 4 * MIM_CP
    return round((-b + (b * b + 4 * a * c_ff) ** 0.5) / (2 * a) / 0.005) * 0.005


CU = MIM_CA * 25 + MIM_CP * 20      # 5x5 um unit, 54.51 fF
ADC_SW_W = {8: 4, 7: 2, 6: 1, 5: 10, 4: 5, 3: 2.5, 2: 1.2, 1: 1, 0: 1}


def bootstrap(p, vin, out, on, onb):
    """Bootstrapped NMOS input switch (all input-side junctions are NMOS in
    p-substrate, so an unpowered or disabled ADC does not load the input)."""
    tb, bb, g, h, gx = p + 'tb', p + 'bb', p + 'g', p + 'h', p + 'gx'
    return [Mos(p + 'MS', N, 8, 0.28, vin, g, out, 'VSS'),
            Cap(p + 'CB', 10, 10, tb, bb, tdir='down', bdir='down'),
            Mos(p + 'M1', N, 2, 0.28, bb, onb, 'VSS', 'VSS'),
            Mos(p + 'M2', P, 2, 0.28, tb, g, 'VDD', tb),
            Mos(p + 'M3', P, 4, 0.28, g, h, tb, tb),
            Mos(p + 'M4', N, 1, 0.28, h, on, bb, 'VSS'),
            Mos(p + 'M5', P, 1, 0.28, h, on, 'VDD', 'VDD'),
            Mos(p + 'M6', N, 4, 0.28, bb, g, vin, 'VSS'),
            Mos(p + 'M7', N, 2, 0.28, g, 'VDD', gx, 'VSS'),
            Mos(p + 'M8', N, 2, 0.28, gx, onb, 'VSS', 'VSS')]


# v3 (2026-11): latch, reset and clock-buffer widths doubled / tail 1.5x. The
# extracted v2 loop spent ~1.3-2.8 ns regenerating (latch 4 um loaded by the
# 6/12 um output inverters) and ~1.0-1.7 ns resetting (2 um reset PMOS).
CMP_SIZE = dict(b1=3, b2=12, tail=12, latch=8, rst=4)


def comparator(p, inp, inn, clk, dp, dn):
    """StrongARM latch (clk high evaluates); dp = inp > inn, both low in reset."""
    cn1, cn2, ct, qp, qn = p + 'cn1', p + 'cn2', p + 'ct', p + 'qp', p + 'qn'
    # Local two-stage clock buffer: the std-cell output alone gave ~3 ns edges on
    # the routed comparator clock and could not reset the latch (extracted run).
    ck = p + 'ck'
    z = CMP_SIZE
    d = inv(p + 'B1', clk, p + 'ckb', wn=z['b1'], wp=2 * z['b1']) + \
        inv(p + 'B2', p + 'ckb', ck, wn=z['b2'], wp=2 * z['b2'])
    clk = ck
    d += [Mos(p + 'MT', N, z['tail'], 0.28, ct, clk, 'VSS', 'VSS'),
         Mos(p + 'MIP', N, 8, 0.28, cn1, inp, ct, 'VSS', flip=True),
         Mos(p + 'MIN', N, 8, 0.28, cn2, inn, ct, 'VSS', flip=True),
         Mos(p + 'MNP', N, z['latch'], 0.28, qn, qp, cn1, 'VSS'),
         Mos(p + 'MNN', N, z['latch'], 0.28, qp, qn, cn2, 'VSS'),
         Mos(p + 'MPP', P, z['latch'], 0.28, qn, qp, 'VDD', 'VDD'),
         Mos(p + 'MPN', P, z['latch'], 0.28, qp, qn, 'VDD', 'VDD'),
         Mos(p + 'MR1', P, z['rst'], 0.28, cn1, clk, 'VDD', 'VDD'),
         Mos(p + 'MR2', P, z['rst'], 0.28, cn2, clk, 'VDD', 'VDD'),
         Mos(p + 'MRP', P, z['rst'], 0.28, qp, clk, 'VDD', 'VDD'),
         Mos(p + 'MRN', P, z['rst'], 0.28, qn, clk, 'VDD', 'VDD')]
    d += inv(p + 'IP', qn, dp, wn=6, wp=12)     # drive the routed DP/DN to the SAR logic
    d += inv(p + 'IN', qp, dn, wn=6, wp=12)
    return d


def adc(name='pt_adc_i'):
    """10-bit differential SAR, top-plate bootstrapped sampling, monotonic
    (downward) bottom-plate switching, split CDAC (MSB 4/2/1 unit caps on the
    sampling node, bridge, LSB 32..1 sized caps + dummy), StrongARM comparator,
    asynchronous sequencer in adc_sar_logic (std cells)."""
    pins = {'sample': 'SAMPLE', 'en': 'EN', 'input_test[0]': 'TEST0', 'input_test[1]': 'TEST1',
            'dp': 'DP', 'dn': 'DN', 'cmp_clk': 'CMPCLK', 'boot_on': 'NC_BOOT', 'boot_onb': 'NC_BOOTB',
            'vcm_top': 'NC_VCMT', 'lsb_rst': 'NC_LSBR', 'done': 'DONE', 'overload': 'OVERLOAD',
            'VDD': 'VDD', 'VSS': 'VSS'}
    pins.update({f'code_tc[{i}]': f'CODE{i}' for i in range(10)})
    for s in 'pn':
        for k in range(9):
            pins[f'g{s}[{k}]'] = f'G{s.upper()}{k}'
            pins[f'r{s}[{k}]'] = f'R{s.upper()}{k}'
    m = macro('adc_sar_logic', pins)
    d = [m]
    front = inv('IE', 'EN', 'ENB')
    front += bias('B', 'EN', 'ENB', nb='ATB_BIAS')
    front += clkrx('K', 'CLKP', 'CLKN', 'SAMPLE', 'EN', nb='ATB_BIAS')
    sw, caps = [], []
    # Sampling-phase switch controls are decoded locally from SAMPLE (clock
    # receiver), EN and TEST1:0 with PCell gates. The macro's boot_on/boot_onb/
    # vcm_top/lsb_rst outputs (same logic) are left unconnected: routed from the
    # macro they arrived up to ~10 ns late at ss/32C/3.15V (extracted), so the
    # top plates were never sampled.
    front += nor2('GTZ', 'TEST0', 'TEST1', 'TZ')                 # input_test == 0
    front += inv('GTZB', 'TZ', 'TZB')
    front += nand2('GSE', 'SAMPLE', 'EN', 'SEB')
    front += inv('GSEI', 'SEB', 'SEN', wn=2, wp=4)                # SAMPLE & EN
    front += nand2('GBT', 'SEN', 'TZ', 'BOOTBL', wn=4, wp=4)       # bootstrap off phase
    front += inv('GBTI', 'BOOTBL', 'BOOTL', wn=4, wp=8)
    front += nand2('GVT', 'SEN', 'TZB', 'VCMTB')
    front += inv('GVTI', 'VCMTB', 'VCMTL', wn=2, wp=4)
    front += inv('GLRA', 'SEN', 'LSBRB')
    front += inv('GLRB', 'LSBRB', 'LSBRL', wn=2, wp=4)
    for s in 'PN':
        top, lsb = 'TOP' + s, 'LSB' + s
        front += bootstrap('S' + s, 'IN' + s, top, 'BOOTL', 'BOOTBL')
        front += [Mos('VT' + s, N, 2, 0.28, top, 'VCMTL', 'VCM', 'VSS'),
                  Mos('LR' + s, N, 1, 0.28, lsb, 'LSBRL', 'VCM', 'VSS')]
        for k in range(9):
            bot = f'BOT{s}{k}'
            sw += [Mos(f'MG{s}{k}', N, ADC_SW_W[k], 0.28, bot, f'G{s}{k}', 'VSS', 'VSS', flip=True,
                       x=pin_x(m, f'g{s.lower()}[{k}]')),
                   Mos(f'MR{s}{k}', N, ADC_SW_W[k], 0.28, bot, f'R{s}{k}', 'VREF', 'VSS', flip=True,
                       x=pin_x(m, f'r{s.lower()}[{k}]'))]
        side = []
        for k, units in ((8, 4), (7, 2), (6, 1)):
            side.append(Cap(f'C{s}{k}', 5, 5, top, f'BOT{s}{k}', m=units, tdir='down', bdir='up'))
        side.append(Cap(f'CB{s}', mim_side(CU * 64 / 63), mim_side(CU * 64 / 63), lsb, top,
                        tdir='down', bdir='down'))
        for k in range(5, -1, -1):
            sd = mim_side(CU * (1 << k))
            side.append(Cap(f'C{s}{k}', sd, sd, lsb, f'BOT{s}{k}', tdir='down', bdir='up'))
        side.append(Cap(f'CD{s}', 5, 5, lsb, 'VSS', tdir='down', bdir='up'))
        caps += side
    front += comparator('Q', 'TOPP', 'TOPN', 'CMPCLK', 'DP', 'DN')
    d += front + sw + caps
    bcaps = [x for x in front if isinstance(x, Cap)]       # bootstrap caps join the CDAC row
    front = [x for x in front if not isinstance(x, Cap)]  # so row 0 stays MOS-only (jumpers)
    rows = [names(front), names(bcaps + caps), names(sw), [m.name]]
    ports = ['VDD', 'VSS', 'INP', 'INN', 'VCM', 'VREF', 'IBIAS', 'CLKP', 'CLKN', 'EN', 'TEST0', 'TEST1'] + \
            [f'CODE{i}' for i in range(10)] + ['DONE', 'OVERLOAD', 'ATB_BIAS']
    return Circuit(name, ports, d, rows=rows,
                   wide_nets={'VDD': 2.0, 'VSS': 2.0, 'VREF': 1.0})


# ------------------------------------------------------------ ADC v2: custom 3.3 V SAR loop
def nand3(p, a, b, c, y, wn=3.0, wp=2.0):
    return [Mos(p + 'NA', N, wn, 0.28, y, a, p + '_m1', 'VSS'),
            Mos(p + 'NB', N, wn, 0.28, p + '_m1', b, p + '_m2', 'VSS'),
            Mos(p + 'NC', N, wn, 0.28, p + '_m2', c, 'VSS', 'VSS'),
            Mos(p + 'PA', P, wp, 0.28, y, a, 'VDD', 'VDD'),
            Mos(p + 'PB', P, wp, 0.28, y, b, 'VDD', 'VDD'),
            Mos(p + 'PC', P, wp, 0.28, y, c, 'VDD', 'VDD')]


def nor3(p, a, b, c, y, wn=1.0, wp=6.0):
    return [Mos(p + 'NA', N, wn, 0.28, y, a, 'VSS', 'VSS'),
            Mos(p + 'NB', N, wn, 0.28, y, b, 'VSS', 'VSS'),
            Mos(p + 'NC', N, wn, 0.28, y, c, 'VSS', 'VSS'),
            Mos(p + 'PA', P, wp, 0.28, p + '_m1', a, 'VDD', 'VDD'),
            Mos(p + 'PB', P, wp, 0.28, p + '_m2', b, p + '_m1', 'VDD'),
            Mos(p + 'PC', P, wp, 0.28, y, c, p + '_m2', 'VDD')]


def delay(p, a, z, stages, l=1.0):
    """Inverter chain of long-channel stages (even count: non-inverting)."""
    d, prev = [], a
    for i in range(stages):
        nxt = z if i == stages - 1 else f'{p}_{i}'
        d += [Mos(f'{p}N{i}', N, 1, l, nxt, prev, 'VSS', 'VSS'),
              Mos(f'{p}P{i}', P, 2, l, nxt, prev, 'VDD', 'VDD')]
        prev = nxt
    return d


SAR_LOGIC_SCALE = 2.5
SAR_DIRECT_CMPCLK = True
SAR_DLY = dict(trk=(2, 0.28))   # (stages, L um): sample-end delays (force release, first compare)


def sar_core():
    """Asynchronous SAR sequencer in 3.3 V static CMOS (replaces the std-cell
    loop of v1). Per decision k (0 = MSB): an 'armed' NAND latch A_k that sets
    once decision k-1 is in and the comparator has reset (VALID low); while
    armed and undecided, a comparator decision sets the P or N NOR latch; their
    OR (D_k) disarms the slice. The comparator clock falls a short delay (d1)
    after VALID and re-arms d1+d2 after VALID falls (CDAC settling window).
    Bottom-plate drivers take both latch outputs (no extra inversion).
    Returns (devices, bit nets for the output register)."""
    d = []
    # control: R (latch reset) = sampling or disabled
    d += nand2('CR', 'SEB', 'EN', 'R')                 # R = SEN | ~EN
    d += inv('CRB', 'R', 'RB')
    # sampling-end delays: TD1 releases the +-VREF/4 force, TD2 starts comparing
    d += delay('DT1', 'SEN', 'SEN_d1', *SAR_DLY['trk'])
    d += nor2('OT1', 'SEN', 'SEN_d1', 'TD1B')         # TD1 = SEN | SEN_d1 (active low out)
    d += delay('DT2', 'SEN_d1', 'SEN_d2', *SAR_DLY['trk'])
    d += nor3('OT2', 'SEN', 'SEN_d1', 'SEN_d2', 'TD2B')
    d += inv('IT2', 'TD2B', 'TD2')
    # RUN = ~(TD2 | D9 | ~EN)
    d += nor3('ORN', 'TD2', 'D9', 'ENB', 'RUN')
    d += inv('IRN', 'RUN', 'RUNB')
    # comparator outputs
    d += nor2('OV', 'DP', 'DN', 'VALIDB', wn=2, wp=8)
    d += inv('IV', 'VALIDB', 'VALID', wn=2, wp=4)
    d += inv('IDP', 'DP', 'DPB', wn=2, wp=4)
    d += inv('IDN', 'DN', 'DNB', wn=2, wp=4)
    # comparator clock: CMPCLK = RUN & ~VALID. No explicit delay elements: the
    # reset path (NOR, INV, NOR, comparator clock buffer, latch reset) is longer
    # than the capture path (NOR3 -> NOR latch), and the CDAC settles while the
    # comparator resets (extracted: delay cells only cost ~0.8 ns per half cycle).
    if SAR_DIRECT_CMPCLK:
        # v3: CMPCLK = NOR3(DP, DN, RUNB) = RUN & ~VALID in one stage. v2 went
        # DP -> NOR (VALIDB) -> INV (VALID) -> NOR: two extra stages in both the
        # decide and the reset half-cycle (~1 ns of a ~3 ns tt cycle, extracted).
        # Capture (DP -> IDP -> NOR3 -> NOR latch, 3 stages) still precedes the
        # reset (NOR3 -> 2 clock buffers -> latch reset -> output inverter, 5);
        # a slice armed late only re-compares the unchanged CDAC (extra cycle).
        d += nor3('OK', 'DP', 'DN', 'RUNB', 'CMPCLK', wn=2, wp=12)
    else:
        d += nor2('OK', 'VALID', 'RUNB', 'CMPCLK', wn=2, wp=8)
    # +/-VREF/4 diagnostic force on the weight-128 plate (cap 7) while TD1
    d += inv('IT0', 'TEST0', 'TEST0B')
    d += inv('IT1', 'TEST1', 'TEST1B')
    d += nor3('OFP', 'TD1B', 'TEST1B', 'TEST0', 'FP')
    d += nor3('OFN', 'TD1B', 'TEST1B', 'TEST0B', 'FN')
    bits = []
    for k in range(10):
        p = f'K{k}_'
        prev = 'RUN' if k == 0 else f'D{k - 1}'
        a, ab, qp, qpb, qn, qnb = (p + n for n in ('A', 'AB', 'QP', 'QPB', 'QN', 'QNB'))
        d += nand2(p + 'S', prev, 'VALIDB', p + 'SAB')
        d += nand2(p + 'LA', p + 'SAB', ab, a)
        d += nand2(p + 'LB', a, 'RB', ab)
        d += nor3(p + 'SP', ab, f'D{k}', 'DPB', p + 'SETP')
        d += nor3(p + 'SN', ab, f'D{k}', 'DNB', p + 'SETN')
        d += nor2(p + 'PA', 'R', qpb, qp)
        d += nor2(p + 'PB', p + 'SETP', qp, qpb)
        d += nor2(p + 'NA', 'R', qnb, qn)
        d += nor2(p + 'NB', p + 'SETN', qn, qnb)
        d += nand2(p + 'D', qpb, qnb, f'D{k}')
        bits.append(qp)
        if k < 9:
            c = 8 - k
            w = ADC_SW_W[c]
            wn, wp = (2, 4) if w >= 4 else (1, 2)
            for s, q, qb, f in (('P', qp, qpb, 'FP'), ('N', qn, qnb, 'FN')):
                if c == 7:     # forced plate: R = ~(Q | F), G = ~R
                    d += nor2(f'DR{s}{c}', q, f, f'R{s}{c}', wn=wn, wp=2 * wp)
                    d += inv(f'DG{s}{c}', f'R{s}{c}', f'G{s}{c}', wn=wn, wp=wp)
                else:
                    d += inv(f'DG{s}{c}', qb, f'G{s}{c}', wn=wn, wp=wp)
                    d += inv(f'DR{s}{c}', q, f'R{s}{c}', wn=wn, wp=wp)
    # Extracted runs showed the routed nets dominate: scale the logic (not the
    # long-channel delay stages) up so edges stay fast on ~100-300 um wires.
    for x in d:
        if isinstance(x, Mos) and x.l == 0.28:
            x.w = round(x.w * SAR_LOGIC_SCALE, 2)
    return d, bits


def adc2(name='pt_adc_i'):
    """v2: same analog core as adc(); the SAR loop is sar_core() (custom 3.3 V
    static CMOS), the std-cell macro adc_code_reg only registers the code."""
    base = adc(name)
    keep = [x for x in base.devices if not isinstance(x, Macro)]
    core, bits = sar_core()
    pins = {'done': 'D9', 'en': 'EN', 'VDD': 'VDD', 'VSS': 'VSS', 'overload': 'OVERLOAD', 'done_o': 'DONE'}
    pins.update({f'bp[{k}]': bits[k] for k in range(10)})
    pins.update({f'code_tc[{i}]': f'CODE{i}' for i in range(10)})
    m = macro('adc_code_reg', pins)
    # switch x positions are no longer tied to macro pins: pack them
    for x in keep:
        if x.name.startswith(('MG', 'MR')) and isinstance(x, Mos):
            x.x = None
    front = [x for x in keep if x.name in base.rows[0]]
    caps = [x for x in keep if x.name in base.rows[1]]
    sw = [x for x in keep if x.name in base.rows[2]]
    drv = [x for x in core if x.name.startswith(('DG', 'DR'))]
    logic = [x for x in core if x not in drv]
    for x in drv:
        x.flip = True                       # outputs (S/D) face the switch row below
    nl = 5
    per = -(-len(logic) // nl)
    rows = [names(front), names(caps), names(sw), names(drv)] + \
        [names(logic[i * per:(i + 1) * per]) for i in range(nl)] + [[m.name]]
    c = Circuit(name, base.ports, keep + core + [m], rows=rows, wide_nets=base.wide_nets)
    c.notes = ['v2: custom 3.3 V asynchronous SAR loop (circuits.sar_core); adc_code_reg macro = output register']
    c.device_gap = 1.2
    return c


# ------------------------------------------------------------ ADC v3: 2-way time-interleaved
ADC_SHARED = ('VDD', 'VSS', 'INP', 'INN', 'VCM', 'VREF', 'IBIAS', 'ATB_BIAS', 'TEST0', 'TEST1')


def _rename(dev, sfx, netmap):
    """Copy of a device with its name suffixed and private nets renamed."""
    import copy
    d = copy.deepcopy(dev)
    d.name = dev.name + sfx
    f = lambda n: netmap.get(n, n if n in ADC_SHARED else n + sfx)
    if isinstance(d, Mos):
        d.d, d.g, d.s, d.b = f(d.d), f(d.g), f(d.s), f(d.b)
    elif isinstance(d, Cap):
        d.top, d.bot = f(d.top), f(d.bot)
    elif isinstance(d, Macro):
        d.pins = {k: f(v) for k, v in d.pins.items()}
    d.x = None
    return d


def dff_clr(p, d_, ck, clr, q, qb):
    """Static positive-edge D flip-flop (7474 structure, no preset); clr low -> q=0."""
    o1, o2, o3, o4 = (p + x for x in ('o1', 'o2', 'o3', 'o4'))
    return (nand2(p + 'G1', o4, o2, o1) + nand3(p + 'G2', o1, clr, ck, o2) +
            nand3(p + 'G3', o2, ck, o4, o3) + nand3(p + 'G4', o3, clr, d_, o4) +
            nand2(p + 'G5', o2, qb, q, wn=3, wp=3) + nand3(p + 'G6', q, o3, clr, qb))


def adc_il(name='pt_adc_i'):
    """v3: two v2 SAR cores (comparator v3) behind one clock receiver. A toggle
    flip-flop clocked at the end of each acquisition steers alternate SAMPLE
    pulses to core A and core B, so each core has 2 x T_clk per conversion:
    40 MS/s per channel from 20 MS/s cores. ILEN=0 (reset value) holds the
    toggle at core A and disables core B: the block then behaves exactly like
    the single-core v2 ADC on CODE*/DONE/OVERLOAD (fallback / debug mode).
    Core A keeps the v2 port names; core B adds CODEB*, DONEB, OVERLOADB."""
    base = adc2(name)
    shared_names = set(names(inv('IE', 'EN', 'ENB') + bias('B', 'EN', 'ENB', nb='ATB_BIAS') +
                             clkrx('K', 'CLKP', 'CLKN', 'SAMPLE', 'EN', nb='ATB_BIAS')))
    shared = [x for x in base.devices if x.name in shared_names]
    core = [x for x in base.devices if x.name not in shared_names]
    assert len(shared) == len(shared_names)
    # The clock receiver emits a ~1.5-2.5 ns SAMPLE pulse when EN rises (its
    # internal node starts high); in v2 that was one spurious conversion, here it
    # would also flip the A/B order. Gate the receiver output with EN delayed by
    # ~5-10 ns (long-channel chain): first SAMPLE after enable -> core A.
    for x in shared:
        if x.name in ('KGNB', 'KGPB'):
            assert x.g == 'EN'
            x.g = 'EN_D'
    ctl = delay('EDL', 'EN', 'EN_D', 4, l=4.0)
    ctl += nand2('ILG', 'EN', 'ILEN', 'ENB_B')            # core B enable = EN & ILEN
    ctl += inv('ILI', 'ENB_B', 'EN_B', wn=2, wp=4)
    ctl += inv('TCK', 'SAMPLE', 'SCK', wn=2, wp=4)        # toggle on the acquisition end
    ctl += dff_clr('TF', 'PHB', 'SCK', 'EN_B', 'PH', 'PHB')
    ctl += nand2('SGA', 'SAMPLE', 'PHB', 'SAB_A', wn=4, wp=4)   # matched A/B sample gating
    ctl += inv('SIA', 'SAB_A', 'SAMPLE_A', wn=4, wp=8)
    ctl += nand2('SGB', 'SAMPLE', 'PH', 'SAB_B', wn=4, wp=4)
    ctl += inv('SIB', 'SAB_B', 'SAMPLE_B', wn=4, wp=8)
    maps = {
        '_A': dict(EN='EN', ENB='ENB', SAMPLE='SAMPLE_A', DONE='DONE', OVERLOAD='OVERLOAD',
                   **{f'CODE{i}': f'CODE{i}' for i in range(10)}),
        '_B': dict(EN='EN_B', ENB='ENB_B', SAMPLE='SAMPLE_B', DONE='DONEB', OVERLOAD='OVERLOADB',
                   **{f'CODE{i}': f'CODEB{i}' for i in range(10)}),
    }
    devs = shared + ctl
    rows = [names(shared + ctl)]
    for sfx, nm in maps.items():
        cd = [_rename(x, sfx, nm) for x in core]
        devs += cd
        for r in base.rows:
            rr = [x + sfx for x in r if x not in shared_names]
            if rr:
                rows.append(rr)
    ports = ['VDD', 'VSS', 'INP', 'INN', 'VCM', 'VREF', 'IBIAS', 'CLKP', 'CLKN', 'EN', 'ILEN', 'TEST0', 'TEST1'] + \
            [f'CODE{i}' for i in range(10)] + ['DONE', 'OVERLOAD'] + \
            [f'CODEB{i}' for i in range(10)] + ['DONEB', 'OVERLOADB', 'ATB_BIAS']
    c = Circuit(name, ports, devs, rows=rows, wide_nets=base.wide_nets)
    c.notes = ['v3: 2-way time-interleaved v2 cores; ILEN=0 = single core A (v2 behaviour)']
    c.device_gap = getattr(base, 'device_gap', 1.2)
    return c
