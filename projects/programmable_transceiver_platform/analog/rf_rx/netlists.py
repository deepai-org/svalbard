"""Write the transistor-level schematic netlists of the RF receive family.

Every file is self-contained (all subcircuits it needs), uses gf180mcuD
primitives only and is the LVS reference for the generated layout:

  lna.spice        pt_lna       pseudo-differential CS LNA, split I/Q cascodes, pre-LNA attenuator + bypass
  rxmix_i.spice    pt_rxmix_i   passive double-balanced mixer + TIA (I)
  rxmix_q.spice    pt_rxmix_q   same circuit, Q instance
  bbfilter_i.spice pt_bbfilter_i  shared RX/TX 5th-order active-RC filter with PGA biquad
  bbfilter_q.spice pt_bbfilter_q
  bb_tap.spice     pt_bb_tap    generic tristate observation buffer / inject switch

Run:  python3 netlists.py   (rewrites the .spice files next to this script)
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- design constants
R_UNIT_L = 40.0       # ppolyf_u_1k, w=1u: ~40 kohm unit resistor of the filter
CU = 9.6             # MIM side (um) of the unit filter capacitor, ~0.25 pF (some sizes trip MIMTM.2 in the PCell; checked by DRC)
CU0 = 9.0            # always-on integrator cap (smaller than the bank unit: widest corner up ~1.3x, narrowest unchanged)
CU2, CU4, CU8 = 2 * CU, 4 * CU, 8 * CU  # wider plates of the same height
CC_LEAD_GC = 6.0       # MIM side (um) of each of the two series extra lead caps switched in with a biquad's +12 dB gain
CC_LEAD = 6.0          # MIM side (um) of the Tow-Thomas excess-phase lead cap (0 = none)
Q1, Q2 = 1.0, 0.5       # biquad Qs: 1.618/0.618 Butterworth, pre-distorted for OTA excess phase and parasitics


class Sub:
    def __init__(self, name, ports):
        self.name, self.ports, self.lines, self.n = name, ports, [], {}

    def _id(self, p):
        self.n[p] = self.n.get(p, 0) + 1
        return f'{p}{self.n[p]}'

    @staticmethod
    def _fingers(w, fw=5.):
        # wide devices become parallel fingers of <= fw um (default 5); the layout flow merges
        # consecutive identical fingers into one multi-finger PCell
        m = 1 if w <= 1.2 * fw else -(-int(w * 100) // int(fw * 100))
        return m, round(w / m, 2)

    def nmos(self, d, g, s, w, l=.28, b='VSS', fw=5.):
        m, wf = self._fingers(w, fw)
        for _ in range(m):
            self.lines.append(f'X{self._id("MN")} {d} {g} {s} {b} nfet_03v3 w={wf:g}u l={l:g}u')

    def pmos(self, d, g, s, w, l=.28, b='VDD', fw=5.):
        m, wf = self._fingers(w, fw)
        for _ in range(m):
            self.lines.append(f'X{self._id("MP")} {d} {g} {s} {b} pfet_03v3 w={wf:g}u l={l:g}u')

    def nmos6(self, d, g, s, w, l=.7, b='VSS', fw=10.):
        # 6 V (nfet_06v0) device for pad-facing switches (PD29 HBM screen: 3.3 V oxide overstressed)
        m, wf = self._fingers(w, fw)
        for _ in range(m):
            self.lines.append(f'X{self._id("MH")} {d} {g} {s} {b} nfet_06v0 w={wf:g}u l={l:g}u')

    def nmos_m(self, d, g, s, w, m, l=.28, b='VSS'):
        for _ in range(m):
            self.nmos(d, g, s, w, l, b)

    def pmos_m(self, d, g, s, w, m, l=.28, b='VDD'):
        for _ in range(m):
            self.pmos(d, g, s, w, l, b)

    def res(self, a, b, l, w=1.0):
        # long resistors are folded into series segments of <= 20 um (compact rows)
        n = 1 if l <= 24 else -(-int(l * 100) // 2000)
        seg = round(l / n, 2)
        rid = self._id('R')
        nodes = [a] + [f'{rid.lower()}_s{k}' for k in range(1, n)] + [b]
        for k in range(n):
            name = rid if n == 1 else f'{rid}_{k}'
            self.lines.append(f'X{name} {nodes[k]} {nodes[k + 1]} VSS ppolyf_u_1k r_width={w:g}u r_length={seg:g}u')

    def cap(self, top, bot, side, length=None):
        length = side if length is None else length
        self.lines.append(f'X{self._id("C")} {top} {bot} cap_mim_2f0_m4m5_noshield c_width={side:g}u c_length={length:g}u')

    def x(self, cell, *nodes):
        self.lines.append(f'X{self._id("X")} {" ".join(nodes)} {cell}')

    def text(self):
        return '\n'.join([f'.subckt {self.name} {" ".join(self.ports)}'] + self.lines + ['.ends', ''])


# ---------------------------------------------------------------- shared cells
def inv():
    s = Sub('pt_rfrx_inv', ['a', 'y', 'VDD', 'VSS'])
    s.nmos('y', 'a', 'VSS', 1.)
    s.pmos('y', 'a', 'VDD', 2.)
    return s


def nor2():
    s = Sub('pt_rfrx_nor2', ['a', 'b', 'y', 'VDD', 'VSS'])
    s.nmos('y', 'a', 'VSS', 1.)
    s.nmos('y', 'b', 'VSS', 1.)
    s.pmos('m', 'a', 'VDD', 4.)
    s.pmos('y', 'b', 'm', 4.)
    return s


def nor3():
    s = Sub('pt_rfrx_nor3', ['a', 'b', 'c', 'y', 'VDD', 'VSS'])
    for g in 'abc':
        s.nmos('y', g, 'VSS', 1.)
    s.pmos('m1', 'a', 'VDD', 6.)
    s.pmos('m2', 'b', 'm1', 6.)
    s.pmos('y', 'c', 'm2', 6.)
    return s


TG_SIZES = {'s': (4., 8.), 'm': (10., 20.), 'l': (20., 40.)}


def tg(size):
    """CMOS transmission gate; `on`/`onb` come from shared block-level logic."""
    wn, wp = TG_SIZES[size]
    s = Sub(f'pt_rfrx_tg{size}', ['a', 'b', 'on', 'onb', 'VDD', 'VSS'])
    s.nmos_m('a', 'on', 'b', wn / (1 if wn <= 20 else 2), 1 if wn <= 20 else 2)
    s.pmos_m('a', 'onb', 'b', wp / (1 if wp <= 20 else 2), 1 if wp <= 20 else 2)
    return s


def nsw():
    """NMOS-only series switch for nodes shared with another power island (DAC in, ADC out):
    no PMOS drain/n-well junction, so a powered peer cannot forward-bias into this rail."""
    s = Sub('pt_rfrx_nsw', ['a', 'b', 'on', 'VSS'])
    s.nmos('a', 'on', 'b', 30.)
    return s


def ota(name='pt_rfrx_ota', tail=8., win=20., wl=4., w6=48., w7=48., cc=13.2, rz=2., l2=1., lin=.5, ll=1., fw=5.):
    """Two-stage Miller OTA, PMOS input, class-A output; pd=1 -> off, output high-Z.

    Bias: vbp from pt_rfrx_bias (10 uA in a W=2/L=1 PMOS diode): tail current
    = 10 uA x tail/2, output stage = 10 uA x w7/2.  Default (mixer TIA): 40 uA / 240 uA."""
    s = Sub(name, ['inp', 'inn', 'out', 'vbp', 'pd', 'VDD', 'VSS'])
    s.pmos('ts', 'pd', 'VDD', max(8., tail))      # supply switch, tail
    s.pmos('tail', 'vbp', 'ts', tail, 1., fw=fw)  # tail current source
    s.pmos('d1', 'inn', 'tail', win, lin, fw=fw)  # input pair
    s.pmos('d2', 'inp', 'tail', win, lin, fw=fw)
    s.nmos('d1', 'd1', 'VSS', wl, ll)             # mirror load
    s.nmos('d2', 'd1', 'VSS', wl, ll)
    s.nmos('out', 'd2', 'VSS', w6, l2)            # second stage
    s.pmos('os', 'pd', 'VDD', max(40., w7))       # supply switch, output stage
    s.pmos('out', 'vbp', 'os', w7, 1.)            # output current source (L=1: mirror of vbp)
    s.nmos('d2', 'pd', 'VSS', 1.)                 # pd: hold second stage off
    s.res('d2', 'cz', max(2., rz), max(2., rz) / rz)  # nulling resistor ~rz kohm (L >= 2 um: SAB area rule)
    s.cap('cz', 'out', cc)                        # Miller capacitor
    return s


def ota_fast():
    """Filter OTA: 2x tail, 1.5x output stage, smaller Miller cap (GBW for a >= 10 MHz corner)."""
    return ota('pt_rfrx_otaf', **OTAF)


def ota_lownoise():
    """Mixer TIA OTA: 3600/1 PMOS pair, NMOS load 20/2, 400 uA output stage, 5 pF Miller cap.  Tail 1.2 mA always plus
    OTAN_XTAIL (2.4 mA) switched in by hib = 1 (RX modes; fork P2: en 2.41 -> 1.38 nV/rtHz tt, chain DSB -1.6 dB at the
    ideal match).  hib = 0 (duplex, the validator ties it to NOT lna.bias.lo) keeps the 1.2 mA tail (power_budget duplex).
    A longer load (L 4/6 um, lower flicker) was rejected: out-of-band IIP3 -15.2/-19.0 dBm vs -11.2 at L 2."""
    s = ota('pt_rfrx_otan', **OTAN)
    if OTAN_XTAIL:
        s.ports.insert(5, 'pdx')                      # pdx = 1: extra tail off
        s.pmos('ts2', 'pd', 'VDD', OTAN_XTAIL / 3)    # supply switch (enable), extra tail
        s.pmos('ts3', 'pdx', 'ts2', OTAN_XTAIL / 3)   # supply switch (hib), extra tail
        s.pmos('tail', 'vbp', 'ts3', OTAN_XTAIL, 1., fw=OTAN['fw'])
    return s


# Coordinator decision 2026-11-13: the fork V TIA (pair 1200 um, tail 240 um = 1.2 mA, no hib pin; 35.4k um^2 per mixer) is the
# design until the LNA gain problem is solved.  The fork P2 x3 option (win 3600, OTAN_XTAIL 480, pin hib; 71.5k um^2, en 1.44
# nV/rtHz, measured +1.55 mA per OTA) and x2 (win 2400, OTAN_XTAIL 240; 52.1k um^2, en 1.75) stay selectable here.
OTAN = dict(tail=240., win=1200., lin=1., wl=20., ll=2., w6=13.3, w7=80., cc=48., rz=1., fw=20.)
OTAN_XTAIL = 0.                  # > 0: hib-switched extra tail; adds the rxmix pin hib and the OTA pin pdx
OTAF = dict(tail=16., win=30., wl=8., w6=36., w7=72., cc=12.2, rz=3., l2=.5)
# PGA stage-1 OTA: OTAF with every device doubled and the same Miller cap (~2x GBW, +~0.45 mA per OTA)
OTAG = dict(tail=32., win=60., wl=16., w6=72., w7=144., cc=12.2, rz=1.5, l2=.5)


def bias():
    """10 uA master reference in -> vbp for the block's OTAs.  en=0: everything off."""
    s = Sub('pt_rfrx_bias', ['ibias', 'en', 'enb', 'vbp', 'VDD', 'VSS'])
    s.nmos('ibias', 'ibias', 'VSS', 2., 1.)       # input diode
    s.nmos('ibias', 'enb', 'VSS', 2.)             # off: short the diode gate
    s.nmos('vbp', 'ibias', 'VSS', 2., 1.)         # 1:1 mirror
    s.pmos('vbp', 'vbp', 'VDD', 2., 1.)           # PMOS reference diode
    s.pmos('vbp', 'en', 'VDD', 2.)                # off: vbp -> VDD
    return s


def vcm():
    """Local 1.65 V common-mode reference (2 x 50 kohm, ~33 uA), off when enb=1."""
    s = Sub('pt_rfrx_vcm', ['enb', 'vcm', 'VDD', 'VSS'])
    s.pmos('top', 'enb', 'VDD', 2.)
    s.res('top', 'vcm', 50.)
    s.res('vcm', 'VSS', 50.)
    s.cap('vcm', 'VSS', 31.6)                     # ~2 pF filter
    return s


def emit(path, subs):
    seen, out = set(), ['* generated by netlists.py -- gf180mcuD primitives only', '']
    for s in subs:
        if s.name not in seen:
            seen.add(s.name)
            out.append(s.text())
    Path(path).write_text('\n'.join(out))


# ---------------------------------------------------------------- LNA
# RC-16b..e (fork A/F/J, scratch/rf-lna, scratch/rf-lna-pub): single transconductance stage with split I/Q
# cascodes; compact hand-placed layout (lna_layout.py) <= 24.6k um^2.
LNA_PORTS = ['rf_in_p', 'rf_in_n', 'rf_out_p', 'rf_out_n', 'rf_outq_p', 'rf_outq_n', 'ibias', 'en', 'gain_lo', 'byp',
             'ct0', 'ct1', 'ct2', 'se', 'rt', 'island_off', 'atb_nbias', 'atb_vdcm', 'VDD', 'VSS',
             'ct3', 'att0', 'att1', 'att2', 'att3', 'att4', 'src_p', 'src_n', 'tank_p', 'tank_n', 'lobias']
# D-RX-1 shunt-C trim, 4 bits (RC-16e): LSB 25 um^2 MIM per leg (5 um = minimum MIM side), range 15 LSB
# (the old 3-bit trim had 7 LSB of 31 um^2); board match derived at code 7 (reset); envelope corners land at 3..12.
LNA_CT_SIDE = (9.2, 13.01, 18.4, 26.02)   # RC-16j: ct0..ct3 = LC-tank tune trim (MIM per side 85..677 um^2), reset 7; spans L -15 %..+10 %
LNA_TANK_FIX = 0                # fixed tank MIM across tank_p/tank_n (side, um)
LNA_RFEED_L, LNA_RFEED_W = 0, 12.   # RC-16j: no resistive feed (the two tank spirals carry the DC)
LNA_CMIX = 16.0                  # tank -> mixer coupling MIM side (um), per mixer per leg
LNA_WCT = 90.                    # bit-0 differential switch width (x2, x4, x8)
LNA_WSE, LNA_WRT = 60., 10.      # SE switch (D-RX-2), termination switch (RC-9)
# pre-LNA attenuator (fork P): 5-bit binary-weighted NMOS switches directly across the two stage-1 gates
# (gates sit at the same DC bias vg), behind the input coupling MIMs: 6 bits att0..att4 + gain_lo (MSB).
# Width of bit k = LNA_ATT_W0 * LNA_ATT_WEIGHTS[k]: first step <= 6 dB, >= 30 dB at code 63 at every corner (lna-evidence).
LNA_ATT_W0 = 3.4
LNA_ATT_FW = 10.
LNA_ATT_BITS = ('att0', 'att1', 'att2', 'att3', 'att4', 'gain_lo')
LNA_ATT_WEIGHTS = (1, 3, 7, 16, 40, 120)  # RC-16h: >= 30 dB at extpp ss, level gaps <= 6 dB at every corner (MSB = gain_lo)
# input stage (fork P, in-band match): wider CS pair at the same current lowers the input Q
LNA_WCS, LNA_WREP, LNA_CIN, LNA_SE_SIDE = 450., 5.5, 47.0, 11.6   # RC-16j: denser device, ~14 mA
LNA_RGS_L, LNA_RGS_W = 1.0, 99.   # ~10 ohm ppoly series gate resistor per leg (fork P2: 15 -> 10 ohm with Ls 0.6 nH, stable, NF -0.3 dB)
LNA_WREP_LO = 5.2                # extra replica width switched in by lobias (duplex: ~11.7 mA)
LNA_FW = 5.
LNA_ATT_AT, LNA_BYP_AT, LNA_BYP_W = 'steer', 'pad', 10.
LNA_BYP_C = 20.0                 # bypass series MIM side (um), ~0.8 pF   # RC-16j probes: 'tank' / 'pad' move them off the gate
LNA_SE_DUMMY = False             # full se-path replica on rf_in_p (area); else a fixed MIM of LNA_DUM_SIDE
LNA_DUM_SIDE = 5.5
LNA_WCAS = 300.                  # RC-16j: single cascode per side
LNA_CASREP = False               # cascoded bias replica (tried, fork P: no effect on the 10-13.6 mA process spread; off)
LNA_RSEG = 10.                   # resistor fold length for the compact layout


def _res_fold(s, a, b, l, w=1.):
    n = 1 if l <= LNA_RSEG else -(-int(round(l * 100)) // int(LNA_RSEG * 100))
    seg = round(l / n, 3)
    rid = s._id('R')
    nodes = [a] + [f'{rid.lower()}_s{k}' for k in range(1, n)] + [b]
    for k in range(n):
        name = rid if n == 1 else f'{rid}_{k}'
        s.lines.append(f'X{name} {nodes[k]} {nodes[k + 1]} VSS ppolyf_u_1k r_width={w:g}u r_length={seg:g}u')


def lna():
    """Pseudo-differential CS input pair (LNA_WCS = 1000/0.28 per side, no tail, replica-biased from a
    25 um diode: same current as the 400/9 version, lower density), AC-coupled from the pad through a
    50 um MIM (~5 pF) and feeding separate I and Q cascodes (200/0.28 each, 3.6 um x 1 um ppoly loads).
    Fork P (in-band match): the wide device, the larger coupling MIM and the removal of fixed pad-side C
    (se cap 30 -> 12 um, MIM-attenuator removed) lower the input quality factor |X/R| from ~95 to ~35,
    which a board ladder (B18/B25) can match across 2.40-2.4835 GHz (Bode-Fano: Q <= ~80 is required
    even for an ideal network; see scratch/reviews/physical-limits.md RX-MATCH).
    Pre-LNA attenuator: 6 weighted NMOS switches (1,2,4,8,16,48 x 3.4 um) across the two stage-1 gates (att0..att4, gain_lo
    = MSB), 0..>=30 dB, steps <= 6 dB; the input match is not held while attenuating.
    ct0..ct3: 4-bit shunt-C package/process trim at the pads.  se: RF_RX_N AC-grounded through a 12 um MIM
    (RF_RX_P carries an identical dummy MIM + off switch for leg balance).  rt: Q-spoil, ~1.5 kohm per leg (3 kohm diff) across the
    gates.  byp: gates straight to both mixer feeds."""
    s = Sub('pt_lna', LNA_PORTS)
    # bias: ibias mirror -> replica gate bias vg, cascode bias vcas (both MIM-decoupled)
    s.x('pt_rfrx_inv', 'en', 'enb', 'VDD', 'VSS')
    s.nmos('atb_nbias', 'atb_nbias', 'VSS', 2., .5)
    s.nmos('atb_nbias', 'enb', 'VSS', 2.)
    _res_fold(s, 'ibias', 'atb_nbias', 2., 2.)
    s.nmos('pb', 'atb_nbias', 'VSS', 20., .5)
    s.pmos('pb', 'pb', 'VDD', 10., .5)
    s.pmos('pb', 'en', 'VDD', 1.)
    s.pmos('vgr', 'pb', 'VDD', 10., .5)
    if LNA_CASREP:   # fork P: cascoded replica, its drain at the CS drain voltage (x): current tracks across process
        s.nmos('vgr', 'vcas', 'xr', LNA_WREP * LNA_WCAS / LNA_WCS * 2)
        s.nmos('xr', 'vgr', 'VSS', LNA_WREP)
    else:
        s.nmos('vgr', 'vgr', 'VSS', LNA_WREP)
    # RC-16j programmable bias: lobias = 1 adds replica width -> CS current ~11.7 mA (duplex), else ~14.3 mA (RX)
    s.nmos('vgr', 'vgr', 'vlo', LNA_WREP_LO)
    s.nmos('vlo', 'lobias', 'VSS', 4.)
    s.nmos('vgr', 'enb', 'VSS', 2.)
    _res_fold(s, 'vgr', 'vg', 10., 1.)
    s.cap('vg', 'VSS', 10.)
    s.pmos('vtop', 'enb', 'VDD', 4.)
    _res_fold(s, 'vtop', 'vcas', 7., 1.)
    _res_fold(s, 'vcas', 'VSS', 23., 1.)
    s.cap('vcas', 'VSS', 10.)
    # core
    for sd in 'pn':
        g, x = (f'rf_in_{sd}' if not LNA_CIN else f'g_{sd}'), f'x_{sd}'   # LNA_CIN = 0: gate on the pad (board DC block)
        _res_fold(s, 'vg', g, 60., 1.)
        gi = f'gi_{sd}'
        _res_fold(s, g, gi, LNA_RGS_L, LNA_RGS_W)   # RC-16j stability: ~15 ohm series gate R (capacitive-source negative R above ~8 GHz)
        s.nmos(x, gi, f'src_{sd}', LNA_WCS, fw=LNA_FW, b='VSS')   # RC-16i: source to its own pad (bond = Ls)
        if LNA_CIN:
            s.cap(g, f'rf_in_{sd}', LNA_CIN)
        # RC-16j LNTA: ONE cascode per leg into the LC tank node tank_{sd} (spiral across tank_p/tank_n, placed at
        # assembly as the QVCO spirals); DC feed by a ppoly resistor; both mixers AC-coupled from the tank node.
        t = f'tank_{sd}'
        if LNA_ATT_AT == 'steer':
            # RC-16j current-steering attenuator: cascode = 64 units; unit 0 always to the tank, units 2^k (k = 0..5)
            # steered to the tank (bit 0) or dumped to VDD (bit 1) by switching their gates between vcas and VSS.
            u = LNA_WCAS / 64.
            s.nmos(t, 'vcas', x, u)
            for k, bit in enumerate(LNA_ATT_BITS):
                s.nmos(t, f'cgk{k}', x, u * (1 << k))
                s.nmos('VDD', f'cgd{k}', x, u * (1 << k))
        else:
            s.nmos(t, 'vcas', x, LNA_WCAS)
        if LNA_RFEED_L:
            _res_fold(s, 'VDD', t, LNA_RFEED_L, LNA_RFEED_W)
        for out in (f'rf_out_{sd}', f'rf_outq_{sd}'):
            s.cap(t, out, LNA_CMIX)
            s.nmos(out, 'island_off', 'VSS', 1., 10.)
        _res_fold(s, t, 'atb_vdcm', 10.)
        bsrc = g if LNA_BYP_AT == 'gate' else f'rf_in_{sd}'
        if LNA_BYP_AT == 'pad':     # RC-16j: series MIM pad -> bypass switch (no DC path from RF_RX; safe test)
            s.cap(f'bpc_{sd}', f'rf_in_{sd}', LNA_BYP_C)
            bsrc = f'bpc_{sd}'
        s.nmos(bsrc, 'byp', f'rf_out_{sd}', LNA_BYP_W)
        s.nmos(bsrc, 'byp', f'rf_outq_{sd}', LNA_BYP_W)
    # pre-LNA attenuator: binary-weighted switches across the gates
    for k, bit in enumerate(LNA_ATT_BITS):
        if LNA_ATT_AT == 'steer':
            s.x('pt_rfrx_inv', bit, f'{bit}_b', 'VDD', 'VSS')
            s.nmos(f'cgk{k}', f'{bit}_b', 'vcas', 2.)     # keep: gate = vcas
            s.nmos(f'cgk{k}', bit, 'VSS', 1.)
            s.nmos(f'cgd{k}', bit, 'vcas', 2.)            # dump: gate = vcas
            s.nmos(f'cgd{k}', f'{bit}_b', 'VSS', 1.)
            continue
        a, b = (('g_p', 'g_n') if LNA_CIN else ('rf_in_p', 'rf_in_n')) if LNA_ATT_AT == 'gate' else ('tank_p', 'tank_n')
        s.nmos(a, bit, b, LNA_ATT_W0 * LNA_ATT_WEIGHTS[k], fw=LNA_ATT_FW)
    if not LNA_CT_SIDE:
        for k in range(4):
            s.x('pt_rfrx_inv', f'ct{k}', f'ct{k}_b', 'VDD', 'VSS')   # inert load on the legacy trim inputs
    for k, side in enumerate(LNA_CT_SIDE):
        s.x('pt_rfrx_inv', f'ct{k}', f'ct{k}_b', 'VDD', 'VSS')
        for sd in 'pn':
            s.cap(f'tank_{sd}', f'x{k}c_{sd}', side)     # RC-16j: ct = tank tune trim
            s.nmos(f'x{k}c_{sd}', 'VSS', f'ct{k}_b', 1., 1.)
        s.nmos(f'x{k}c_p', f'ct{k}', f'x{k}c_n', LNA_WCT * (1 << k))
    if LNA_TANK_FIX:
        s.cap('tank_p', 'tank_n', LNA_TANK_FIX)
    s.x('pt_rfrx_inv', 'se', 'se_b', 'VDD', 'VSS')
    s.cap('rf_in_n', 'se_x', LNA_SE_SIDE)
    s.nmos('se_x', 'VSS', 'se_b', 1., 1.)
    s.nmos('se_x', 'se', 'VSS', LNA_WSE)
    if LNA_SE_DUMMY:
        s.cap('rf_in_p', 'sd_x', LNA_SE_SIDE)          # leg-balance dummy of the se path (switch held off)
        s.nmos('sd_x', 'VSS', 'VSS', 1., 1.)
        s.nmos('sd_x', 'VSS', 'VSS', LNA_WSE)
    else:
        s.cap('rf_in_p', 'VSS', LNA_DUM_SIDE)    # fixed MIM balancing the se path's off-state C on rf_in_n
    _res_fold(s, 'g_p' if LNA_CIN else 'rf_in_p', 'rt_p', 3., 2.)    # fork P (RC-16h): rt = Q-spoil, ~1.5 kohm per leg (was ~200 ohm termination)
    _res_fold(s, 'g_n' if LNA_CIN else 'rf_in_n', 'rt_n', 3., 2.)
    s.nmos('rt_p', 'rt', 'rt_n', LNA_WRT)
    return [inv(), s]


# ---------------------------------------------------------------- mixer
def quad():
    """Double-balanced passive switching quad (hand-drawn symmetric layout, rfrx_flow.layout_quad).
    Device order A..D is fixed: A rf_p/x_p/lo_p, B rf_n/x_n/lo_p, C rf_p/x_n/lo_n, D rf_n/x_p/lo_n."""
    s = Sub('pt_rxmix_quad', ['rf_p', 'rf_n', 'lo_p', 'lo_n', 'x_p', 'x_n', 'VSS'])
    for a, b, lo in (('rf_p', 'x_p', 'lo_p'), ('rf_n', 'x_n', 'lo_p'), ('rf_p', 'x_n', 'lo_n'), ('rf_n', 'x_p', 'lo_n')):
        s.nmos(a, lo, b, 30.)
    return s


def ofsdac():
    """TIA offset-correction DAC: sign-magnitude, 5 bits x 0.4 uA sunk from x_p or x_n.
    10 uA (PMOS mirror of vbp) into an NMOS diode; binary NMOS mirrors (L = 3.125 um)."""
    s = Sub('pt_rxmix_ofsdac', ['x_p', 'x_n', 'vbp', 'ofs0', 'ofs1', 'ofs2', 'ofs3', 'ofs4', 'ofs_sign',
                                'VDD', 'VSS'])
    s.pmos('nd', 'vbp', 'VDD', 2., 1.)             # 10 uA reference (off when vbp is pulled to VDD)
    s.nmos('nd', 'nd', 'VSS', 25., 3.125)          # diode, W/L = 8
    for k in range(5):
        s.nmos(f'm{k}', 'nd', 'VSS', 2 ** k, 3.125)   # 0.4 uA x 2^k
        s.nmos('idac', f'ofs{k}', f'm{k}', 2.)        # bit switch
    s.x('pt_rfrx_inv', 'ofs_sign', 'sgn_b', 'VDD', 'VSS')
    s.nmos('x_p', 'sgn_b', 'idac', 4.)             # sign 0: sink from x_p (bb_n rises)
    s.nmos('x_n', 'ofs_sign', 'idac', 4.)          # sign 1: sink from x_n (bb_p rises)
    return s


def rxmix(name):
    s = Sub(name, ['rf_p', 'rf_n', 'lo_p', 'lo_n', 'bb_p', 'bb_n', 'ibias', 'en', 'ofs0', 'ofs1', 'ofs2', 'ofs3',
                   'ofs4', 'ofs_sign', 'island_off', 'atb_vcm', 'atb_vbp', *(('hib',) if OTAN_XTAIL else ()), 'VDD', 'VSS'])
    s.x('pt_rfrx_inv', 'en', 'enb', 'VDD', 'VSS')
    if OTAN_XTAIL:
        s.x('pt_rfrx_inv', 'hib', 'hibb', 'VDD', 'VSS')   # fork P2 option: hib = 1 -> extra TIA OTA tail on (RX); 0 in duplex
    s.x('pt_rfrx_bias', 'ibias', 'en', 'enb', 'atb_vbp', 'VDD', 'VSS')
    s.x('pt_rfrx_vcm', 'enb', 'atb_vcm', 'VDD', 'VSS')
    s.x('pt_rxmix_quad', 'rf_p', 'rf_n', 'lo_p', 'lo_n', 'x_p', 'x_n', 'VSS')
    s.res('atb_vbp', 'vbpf', 100.)                # bias noise filter (~0.8 MHz with 2 pF)
    s.cap('VDD', 'vbpf', 31.6)
    s.x('pt_rxmix_ofsdac', 'x_p', 'x_n', 'vbpf', 'ofs0', 'ofs1', 'ofs2', 'ofs3', 'ofs4', 'ofs_sign', 'VDD', 'VSS')
    s.cap('x_p', 'x_n', 44.7)                     # ~4 pF RF/LO residue shunt at the TIA input
    for sd in 'pn':
        out = f'bb_{"n" if sd == "p" else "p"}'   # TIA inverts: x_p drives bb_n
        s.x('pt_rfrx_otan', 'atb_vcm', f'x_{sd}', out, 'vbpf', 'enb', *(('hibb',) if OTAN_XTAIL else ()), 'VDD', 'VSS')
        s.res(f'x_{sd}', out, 11.6)               # Rtia ~11.6 kohm (fork V: -4.7 dB cancels the gain rise of the 2x OTA)
        s.cap(f'x_{sd}', out, 18.4)               # Ctia ~0.68 pF (same ~20 MHz pole)
        s.nmos(out, 'island_off', 'VSS', 1., 10.)   # weak clamp (~tens of uA)
    return [inv(), bias(), vcm(), ota_lownoise(), quad(), ofsdac(), s]


# ---------------------------------------------------------------- shared RX/TX baseband filter
def bbfilter(name):
    """Fully differential filter/PGA with CMFB, fine DCOC DAC and fine cutoff trim (fork S): bbf_fd.py."""
    import bbf_fd
    return bbf_fd.bbfilter(name)


def _bbfilter_pseudo_diff(name):
    """Previous pseudo-differential filter (two single-ended halves); kept for reference, not emitted."""
    ports = ['rx_in_p', 'rx_in_n', 'tx_in_p', 'tx_in_n', 'inj_p', 'inj_n',
             'out_rx_p', 'out_rx_n', 'out_tx_p', 'out_tx_n', 'obs_p', 'obs_n',
             'ibias', 'en', 'dir_tx', 'inj', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1',
             'bw0', 'bw1', 'bw2', 'bw3', 'gain0', 'gain1', 'gain2', 'gain3', 'gain4', 'gain5',
             'gainc0', 'gainc1', 'qt0', 'qt1', 'island_off',
             'atb_vcm', 'atb_vbp', 'VDD', 'VSS']
    s = Sub(name, ports)
    I = lambda a, y: s.x('pt_rfrx_inv', a, y, 'VDD', 'VSS')
    N2 = lambda a, b, y: s.x('pt_rfrx_nor2', a, b, y, 'VDD', 'VSS')
    N3 = lambda a, b, c, y: s.x('pt_rfrx_nor3', a, b, c, y, 'VDD', 'VSS')
    # ---- control decode (island-powered; all off when en=0 or island unpowered)
    for c in ('en', 'dir_tx', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1',
              'bw0', 'bw1', 'bw2', 'bw3', 'gain0', 'gain1', 'gain2', 'gain3', 'gain4', 'gain5',
              'gainc0', 'gainc1', 'qt0', 'qt1'):
        I(c, c + '_b')
    N3('en_b', 'dir_tx', 'inj', 'k_inrx')          # rx_in -> core
    N3('en_b', 'dir_tx_b', 'inj', 'k_intx')        # tx_in -> core
    N3('en_b', 'dir_tx', 'rx_direct', 'k_orx')     # core -> out_rx
    N2('en_b', 'dir_tx_b', 'k_otx')                # core -> out_tx
    N2('en_b', 'rx_direct_b', 'k_rxd')             # rx_in -> out_rx (filter-less RX)
    N2('en_b', 'byp_s1', 'k_s1run')
    N2('en_b', 'byp_s1_b', 'k_s1byp')
    N2('en_b', 'byp_s23', 'k_s23run')
    N2('en_b', 'byp_s23_b', 'k_s23byp')
    N3('en_b', 'obs_sel1', 'obs_sel0_b', 'k_obs1')  # 01: after mixer (rx_in)
    N3('en_b', 'obs_sel1_b', 'obs_sel0', 'k_obs2')  # 10: after PGA stage
    N3('en_b', 'obs_sel1_b', 'obs_sel0_b', 'k_obs3')  # 11: filter output
    for k in ('k_inrx', 'k_otx', 'k_s1byp', 'k_s23byp', 'k_obs1', 'k_obs2', 'k_obs3'):
        I(k, k + 'b')
    I('k_s1run', 'pd1')
    I('k_s23run', 'pd23')
    s.x('pt_rfrx_bias', 'ibias', 'en', 'en_b', 'atb_vbp', 'VDD', 'VSS')
    # every OTA references the input common mode (atb_vcm = mean of the core inputs), so an
    # input-CM error passes with gain 1 instead of being multiplied by the PGA gain
    for h in 'pn':
        s.res(f'inj_{h}', 'atb_vcm', 200.)
    s.cap('atb_vcm', 'VSS', 31.6)                  # ~2 pF: keeps residual differential ripple off the reference
    BW = ['bw0', 'bw0_b', 'bw1', 'bw1_b', 'bw2', 'bw2_b', 'bw3', 'bw3_b']
    GN = [x for k in range(6) for x in (f'gain{k}', f'gain{k}_b')]
    COM = ['atb_vcm', 'atb_vbp']
    QT = ['qt0', 'qt0_b', 'qt1', 'qt1_b']

    def T(size, a, b, k):
        s.x(f'pt_rfrx_tg{size}', a, b, k, k + 'b' if k.startswith('k_') else k + '_b', 'VDD', 'VSS')

    for h in 'pn':
        o = 'n' if h == 'p' else 'p'
        ci, s1 = f'inj_{h}', f's1_{h}'
        T('m', f'rx_in_{h}', ci, 'k_inrx')
        s.x('pt_rfrx_nsw', f'tx_in_{h}', ci, 'k_intx', 'VSS')   # DAC (conv island) input
        # stage 1: PGA real pole (gain 1..16 = Rf/R1, pole 1/(Rf C) independent of gain); it
        # inverts, so half h drives s1 of the other half
        s.x('pt_bbf_gpole', ci, f's1_{o}', *COM, 'pd1', *GN, *BW, 'VDD', 'VSS')
        T('m', ci, s1, 'k_s1byp')
        # stages 2 and 3: Tow-Thomas biquads (Q1, Q2), non-inverting low-pass outputs
        s.x('pt_bbf_tt1', s1, f'bp1_{h}', f'lp1_{h}', *COM, 'pd23', 'gainc0', 'gainc0_b', *QT, *BW, 'VDD', 'VSS')
        s.x('pt_bbf_tt2', f'lp1_{h}', f'bp2_{h}', f'co_{h}', *COM, 'pd23', 'gainc1', 'gainc1_b', *QT, *BW,
            'VDD', 'VSS')
        T('m', s1, f'co_{h}', 'k_s23byp')          # bypass keeps the differential sign
        # outputs and direction
        s.x('pt_rfrx_nsw', f'co_{h}', f'out_rx_{h}', 'k_orx', 'VSS')   # to ADC (conv island)
        T('m', f'co_{h}', f'out_tx_{h}', 'k_otx')
        s.x('pt_rfrx_nsw', f'rx_in_{h}', f'out_rx_{h}', 'k_rxd', 'VSS')
        # observation mux -> bb_tap
        T('s', f'rx_in_{h}', f'obs_{h}', 'k_obs1')
        T('s', s1, f'obs_{h}', 'k_obs2')
        T('s', f'co_{h}', f'obs_{h}', 'k_obs3')
        for node in (f'out_rx_{h}', f'out_tx_{h}', f'obs_{h}'):
            s.nmos(node, 'island_off', 'VSS', 1., 10.)   # weak clamp (~tens of uA)
    stages = [bbf_int(), bbf_int('pt_bbf_intg', 'pt_rfrx_otag'), bbf_tt('pt_bbf_tt1', Q1), bbf_tt('pt_bbf_tt2', Q2), bbf_gpole()]
    inline(s, stages)   # flatten the filter stages into the block (layout packs better flat)
    return [inv(), nor2(), nor3(), tg('s'), tg('m'), tg('l'), nsw(), bias(), ota_fast(), ota('pt_rfrx_otag', **OTAG), s]


def inline(sub, cells):
    """Expand instances of `cells` (repeatedly) into `sub`, prefixing internal nets and names."""
    lib = {c.name: c for c in cells}
    changed = True
    while changed:
        changed, out = False, []
        for line in sub.lines:
            tok = line.split()
            pos = [t for t in tok[1:] if '=' not in t]
            if tok[0].startswith('X') and pos and pos[-1] in lib:
                cell, inst = lib[pos[-1]], tok[0][1:]
                amap = dict(zip(cell.ports, pos[:-1]))
                for cl in cell.lines:
                    ct = cl.split()
                    cpos = [t for t in ct[1:] if '=' not in t]
                    params = [t for t in ct[1:] if '=' in t]
                    nodes = [amap.get(n, n if n in ('VDD', 'VSS') else f'{inst}_{n}') for n in cpos[:-1]]
                    out.append(' '.join([f'X{inst}_{ct[0][1:]}'] + nodes + [cpos[-1]] + params))
                changed = True
            else:
                out.append(line)
        sub.lines = out


BWP = ['bw0', 'bw0_b', 'bw1', 'bw1_b', 'bw2', 'bw2_b', 'bw3', 'bw3_b']


def bbf_int(name='pt_bbf_int', ota_cell='pt_rfrx_otaf'):
    """Integrator: OTA + switched capacitor bank (unit + 1/2/4/8 x unit on bw0..3)."""
    s = Sub(name, ['a', 'out', 'vcm', 'vbp', 'pd', *BWP, 'VDD', 'VSS'])
    s.x(ota_cell, 'vcm', 'a', 'out', 'vbp', 'pd', 'VDD', 'VSS')
    s.cap('a', 'out', CU0)                         # always-on unit (widest bandwidth)
    for bit, side in (('bw0', CU), ('bw1', CU2), ('bw2', CU4), ('bw3', CU8)):
        s.x('pt_rfrx_tgs', 'a', f'c_{bit}', bit, bit + '_b', 'VDD', 'VSS')  # switch on the virtual-ground side
        s.cap(f'c_{bit}', 'out', side, CU)
    return s


QT_MULT = (4.0, 2.0)   # Q-trim: qt0 adds 4*Rq, qt1 adds 2*Rq in parallel with Rq -> Q x 1, 0.8, 0.67, 0.57


def _tt(s, vin, v1, v2, q, trim=True):
    """Tow-Thomas core: A1 lossy integrator (Rq = q R), A2 integrator, A3 inverter.
    Q-trim (qt1:qt0): switched damping resistors in parallel with Rq; the TG sits on the virtual-ground side."""
    s.res('v3', 'a', R_UNIT_L)
    s.res(v1, 'a', q * R_UNIT_L)
    for bit, mult in (zip(('qt0', 'qt1'), QT_MULT) if trim else ()):
        s.res(v1, f'q_{bit}', mult * q * R_UNIT_L)
        s.x('pt_rfrx_tgs', f'q_{bit}', 'a', bit, bit + '_b', 'VDD', 'VSS')
    s.x('pt_bbf_int', 'a', v1, 'vcm', 'vbp', 'pd', *BWP, 'VDD', 'VSS')
    s.res(v1, 'b', R_UNIT_L)
    if CC_LEAD:
        # phase lead in the two-integrator loop cancels the OTAs' excess phase. It sits at an
        # integrator input (capacitive feedback: no extra feedback pole), not at the A3 inverter
        # (resistive feedback: a cap there made A3 peak in the extracted netlist).
        s.cap(v1, 'b', CC_LEAD)
    s.x('pt_bbf_int', 'b', v2, 'vcm', 'vbp', 'pd', *BWP, 'VDD', 'VSS')
    s.res(v2, 'c', R_UNIT_L)
    s.res('v3', 'c', R_UNIT_L)
    s.x('pt_rfrx_otaf', 'vcm', 'c', 'v3', 'vbp', 'pd', 'VDD', 'VSS')


def bbf_tt(name, q):
    """Tow-Thomas biquad (v1 band-pass, v2 low-pass); passband gain 1, or 4 (+12 dB) with gc:
    an extra R/3 input branch.  Input resistors set only the gain, not w0 or Q."""
    s = Sub(name, ['vin', 'v1', 'v2', 'vcm', 'vbp', 'pd', 'gc', 'gc_b', 'qt0', 'qt0_b', 'qt1', 'qt1_b', *BWP, 'VDD', 'VSS'])
    s.res('vin', 'a', R_UNIT_L)
    s.res('vin', 'gx', R_UNIT_L / 3)
    s.x('pt_rfrx_tgm', 'gx', 'a', 'gc', 'gc_b', 'VDD', 'VSS')
    if CC_LEAD_GC:   # extra lead with the +12 dB input: A1's noise gain (and excess phase) rises
        s.x('pt_rfrx_tgs', 'v1', 'lx', 'gc', 'gc_b', 'VDD', 'VSS')
        s.cap('lx', 'ly', CC_LEAD_GC)            # two in series: a single ~30 fF MIM is below the DRC-clean PCell sizes
        s.cap('ly', 'b', CC_LEAD_GC)
    _tt(s, 'vin', 'v1', 'v2', q, trim=(q == Q1))
    return s


def bbf_gpole():
    """PGA stage: inverting real pole, gain = Rf/Rin = k/4, k = sum(2^j gain_j), j = 0..5 (binary
    conductance bank of 4R/2^j; k = 0 mutes).  The pole 1/(Rf C) does not move with gain and has no
    Q to enhance.  With the +12 dB steps of the two biquads (gainc0/1) the chain covers -6..42 dB
    in 3 dB steps (+-0.5 dB worst, see GAIN_TABLE)."""
    gn = [x for k in range(6) for x in (f'gain{k}', f'gain{k}_b')]
    s = Sub('pt_bbf_gpole', ['vin', 'out', 'vcm', 'vbp', 'pd', *gn, *BWP, 'VDD', 'VSS'])
    for j, size in enumerate(('s', 's', 's', 'm', 'm', 'l')):
        s.res('vin', f'g{j}', 4 * R_UNIT_L / (1 << j))
        s.x(f'pt_rfrx_tg{size}', f'g{j}', 'a', f'gain{j}', f'gain{j}_b', 'VDD', 'VSS')
    s.res('a', 'out', R_UNIT_L)
    # 2x OTA: at the top stage-1 gain (k = 32, noise gain 9) the loop must still be >> the pole
    s.x('pt_bbf_intg', 'a', 'out', 'vcm', 'vbp', 'pd', *BWP, 'VDD', 'VSS')
    return s


def _gain_table():
    """dB code (-6..42, 3 dB steps) -> (k, gainc0, gainc1): coarse steps used from +21 dB so
    stage 1 keeps >= +9 dB in front of the biquads (noise)."""
    t = {}
    for db in range(-6, 43, 3):
        nc = 0 if db <= 18 else 1 if db <= 30 else 2
        ki = 4 * 10 ** ((db - 12 * nc) / 20)
        # schematic-measured gain loss (TG Ron, finite OTA gain): ~0.023 dB per k unit, ~0.15 dB per coarse step
        k = max(1, min(63, round(ki * 10 ** ((0.023 * ki + 0.15 * nc) / 20))))
        t[db] = (k, int(nc >= 1), int(nc >= 2))
    return t


GAIN_TABLE = _gain_table()


# ---------------------------------------------------------------- generic observation buffer
TAP_SW_W, TAP_OBS_M, TAP_INJ_M = 20., 5, 3   # nfet_06v0 20/0.7 fingers per leg (observe 100 um, inject 60 um)
TAP_RG = 100.   # gate resistor length (um of ppolyf_u_1k, ~1 kohm/um): with TAP_CC the switch gates track the pad under HBM (PD29)
TAP_CC = 8.   # gate->pad coupling MIM side (um, cap_mim_2f0 ~2 fF/um2 -> ~130 fF); 0 = none
TAP_RG_INJ = None   # inject-switch gate resistor (None: TAP_RG). Screen ss/0 C sch: R100+C60f 5.66 V, R50+C60f 6.03 V (fail); no C: R300 5.92 V


def _res_segs(s, a, b, l, seg=50.):
    n = max(1, -(-int(l * 100) // int(seg * 100)))
    rid = s._id('R')
    nodes = [a] + [f'{rid.lower()}_s{k}' for k in range(1, n)] + [b]
    for k in range(n):
        s.lines.append(f'X{rid}_{k} {nodes[k]} {nodes[k + 1]} VSS ppolyf_u_1k r_width=1u r_length={l / n:g}u')


def bb_tap():
    s = Sub('pt_bb_tap', ['in_p', 'in_n', 'pad_p', 'pad_n', 'inj_p', 'inj_n', 'ibias',
                          'obs_en', 'inj_en', 'island_off', 'atb_nbias', 'VDD', 'VSS'])
    I = lambda a, y: s.x('pt_rfrx_inv', a, y, 'VDD', 'VSS')
    I('obs_en', 'obs_enb')
    s.x('pt_rfrx_nor2', 'obs_enb', 'inj_en', 'obs_on', 'VDD', 'VSS')  # inject wins
    I('obs_on', 'obs_off')
    I('inj_en', 'inj_enb')
    I('inj_enb', 'inj_on')                         # island-powered: 0 whenever the island is off
    s.res('ibias', 'atb_nbias', 2., 2.)
    s.nmos('atb_nbias', 'atb_nbias', 'VSS', 2., .5)
    s.nmos('atb_nbias', 'obs_off', 'VSS', 2.)
    for h in 'pn':
        g, src = f'in_{h}', f'sf_{h}'
        s.pmos(f'dr_{h}', 'obs_off', 'VDD', 40.)   # follower supply switch: no current when off
        s.nmos_m(f'dr_{h}', g, src, 20., 4)        # NMOS source follower 80/0.28
        s.nmos_m(src, 'atb_nbias', 'VSS', 20., 5, .5)  # 0.5 mA sink (50:1)
        s.nmos(src, 'obs_off', 'VSS', 2.)          # clamp follower output when off
        s.nmos(src, 'island_off', 'VSS', 1., 10.)   # weak clamp (~tens of uA)
        # PD29: pad-facing series switches are nfet_06v0 (HBM screen put 6.1-6.8 V on the 3.3 V oxide).
        # NMOS-only: no PN path from pad to VDD.  Gates driven through RG (bootstrap under HBM, static control).
        for k in range(TAP_OBS_M):
            s.nmos6(src, f'obs_g{h}', f'pad_{h}', TAP_SW_W)
        for k in range(TAP_INJ_M):
            s.nmos6(f'pad_{h}', f'inj_g{h}', f'inj_{h}', TAP_SW_W)   # inject: pad -> chain node
        if TAP_RG:
            # few long segments (each fold node costs a routed net in the bank)
            _res_segs(s, 'obs_on', f'obs_g{h}', TAP_RG)
            _res_segs(s, 'inj_on', f'inj_g{h}', TAP_RG if TAP_RG_INJ is None else TAP_RG_INJ)
            if TAP_CC:   # gate -> pad coupling MIM (bottom plate on the low-impedance pad): gate tracks the pad under HBM
                s.cap(f'obs_g{h}', f'pad_{h}', TAP_CC)
                s.cap(f'inj_g{h}', f'pad_{h}', TAP_CC)
        else:
            s.lines = [l.replace(f'obs_g{h}', 'obs_on').replace(f'inj_g{h}', 'inj_on') for l in s.lines]
    return [inv(), nor2(), s]


def main():
    emit(HERE / 'lna.spice', lna())
    emit(HERE / 'rxmix_i.spice', rxmix('pt_rxmix_i'))
    emit(HERE / 'rxmix_q.spice', rxmix('pt_rxmix_q'))
    emit(HERE / 'bbfilter_i.spice', bbfilter('pt_bbfilter_i'))
    emit(HERE / 'bbfilter_q.spice', bbfilter('pt_bbfilter_q'))
    emit(HERE / 'bb_tap.spice', bb_tap())


if __name__ == '__main__':
    main()
