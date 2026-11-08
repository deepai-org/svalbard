"""Write the transistor-level schematic netlists of the RF receive family.

Every file is self-contained (all subcircuits it needs), uses gf180mcuD
primitives only and is the LVS reference for the generated layout:

  lna.spice        pt_lna       differential resistive-feedback LNA + bypass switch
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
CU2, CU4, CU8 = 2 * CU, 4 * CU, 8 * CU  # wider plates of the same height
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
    """Mixer TIA OTA: 600 uA tail, 600/1 PMOS pair, long low-gm NMOS load (20/2), 400 uA output
    stage, 5 pF Miller cap.  Input noise ~7 nV/rtHz at 5 MHz (was ~29 nV/rtHz)."""
    return ota('pt_rfrx_otan', **OTAN)


OTAN = dict(tail=120., win=600., lin=1., wl=20., ll=2., w6=13.3, w7=80., cc=48., rz=1., fw=20.)
OTAF = dict(tail=16., win=30., wl=8., w6=36., w7=72., cc=12.2, rz=3., l2=.5)


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
def lna():
    s = Sub('pt_lna', ['rf_in_p', 'rf_in_n', 'rf_out_p', 'rf_out_n', 'ibias', 'en', 'gain_lo', 'byp',
                       'island_off', 'atb_nbias', 'atb_vdcm', 'VDD', 'VSS'])
    s.x('pt_rfrx_inv', 'en', 'enb', 'VDD', 'VSS')
    s.x('pt_rfrx_inv', 'gain_lo', 'glb', 'VDD', 'VSS')
    # bias: ibias diode, 280:1 tail (2.8 mA)
    s.nmos('atb_nbias', 'atb_nbias', 'VSS', 2., .5)
    s.nmos('atb_nbias', 'enb', 'VSS', 2.)
    s.res('ibias', 'atb_nbias', 2., 2.)           # ~1 kohm series: separates the ATB tap name from the pin
    s.nmos_m('tail', 'atb_nbias', 'VSS', 20., 28, .5)
    s.pmos_m('vtop', 'enb', 'VDD', 20., 3)        # load supply switch (no current when off)
    for sd in 'pn':
        g, d = f'g_{sd}', f'd_{sd}'
        s.cap(g, f'rf_in_{sd}', 32.)              # input coupling ~2 pF (bottom plate on pad side)
        s.nmos_m(d, g, 'tail', 20., 5)            # input device 100/0.28
        s.res('vtop', d, 2., 2.)                  # RL ~1 kohm
        s.res(d, g, 4., 1.)                       # RF ~4 kohm feedback (NF/gain optimum with a board match)
        s.cap(f'rf_out_{sd}', d, 32.)             # output coupling ~2 pF
        s.nmos_m(g, 'byp', f'rf_out_{sd}', 20., 3)  # bypass: pad -> Cin -> g -> mixer input
        s.nmos(f'rf_out_{sd}', 'island_off', 'VSS', 1., 10.)   # weak clamp (~tens of uA)
        s.res(d, 'atb_vdcm', 20.)                 # drain common-mode sense for the ATB
    s.pmos('g_n', 'glb', 'g_p', 100.)             # gain_lo: differential input shunt (~35 ohm switch)
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
                   'ofs4', 'ofs_sign', 'island_off', 'atb_vcm', 'atb_vbp', 'VDD', 'VSS'])
    s.x('pt_rfrx_inv', 'en', 'enb', 'VDD', 'VSS')
    s.x('pt_rfrx_bias', 'ibias', 'en', 'enb', 'atb_vbp', 'VDD', 'VSS')
    s.x('pt_rfrx_vcm', 'enb', 'atb_vcm', 'VDD', 'VSS')
    s.x('pt_rxmix_quad', 'rf_p', 'rf_n', 'lo_p', 'lo_n', 'x_p', 'x_n', 'VSS')
    s.res('atb_vbp', 'vbpf', 100.)                # bias noise filter (~0.8 MHz with 2 pF)
    s.cap('VDD', 'vbpf', 31.6)
    s.x('pt_rxmix_ofsdac', 'x_p', 'x_n', 'vbpf', 'ofs0', 'ofs1', 'ofs2', 'ofs3', 'ofs4', 'ofs_sign', 'VDD', 'VSS')
    s.cap('x_p', 'x_n', 44.7)                     # ~4 pF RF/LO residue shunt at the TIA input
    for sd in 'pn':
        out = f'bb_{"n" if sd == "p" else "p"}'   # TIA inverts: x_p drives bb_n
        s.x('pt_rfrx_otan', 'atb_vcm', f'x_{sd}', out, 'vbpf', 'enb', 'VDD', 'VSS')
        s.res(f'x_{sd}', out, 20.)                # Rtia ~20 kohm
        s.cap(f'x_{sd}', out, 14.)                # Ctia ~0.4 pF (~20 MHz pole)
        s.nmos(out, 'island_off', 'VSS', 1., 10.)   # weak clamp (~tens of uA)
    return [inv(), bias(), vcm(), ota_lownoise(), quad(), ofsdac(), s]


# ---------------------------------------------------------------- shared RX/TX baseband filter
def bbfilter(name):
    ports = ['rx_in_p', 'rx_in_n', 'tx_in_p', 'tx_in_n', 'inj_p', 'inj_n',
             'out_rx_p', 'out_rx_n', 'out_tx_p', 'out_tx_n', 'obs_p', 'obs_n',
             'ibias', 'en', 'dir_tx', 'inj', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1',
             'bw0', 'bw1', 'bw2', 'bw3', 'gain0', 'gain1', 'gain2', 'gain3', 'island_off',
             'atb_vcm', 'atb_vbp', 'VDD', 'VSS']
    s = Sub(name, ports)
    I = lambda a, y: s.x('pt_rfrx_inv', a, y, 'VDD', 'VSS')
    N2 = lambda a, b, y: s.x('pt_rfrx_nor2', a, b, y, 'VDD', 'VSS')
    N3 = lambda a, b, c, y: s.x('pt_rfrx_nor3', a, b, c, y, 'VDD', 'VSS')
    # ---- control decode (island-powered; all off when en=0 or island unpowered)
    for c in ('en', 'dir_tx', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1',
              'bw0', 'bw1', 'bw2', 'bw3', 'gain0', 'gain1', 'gain2', 'gain3'):
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
    GN = ['gain0', 'gain0_b', 'gain1', 'gain1_b', 'gain2', 'gain2_b', 'gain3', 'gain3_b']
    COM = ['atb_vcm', 'atb_vbp']

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
        s.x('pt_bbf_tt1', s1, f'bp1_{h}', f'lp1_{h}', *COM, 'pd23', *BW, 'VDD', 'VSS')
        s.x('pt_bbf_tt2', f'lp1_{h}', f'bp2_{h}', f'co_{h}', *COM, 'pd23', *BW, 'VDD', 'VSS')
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
    stages = [bbf_int(), bbf_tt('pt_bbf_tt1', Q1), bbf_tt('pt_bbf_tt2', Q2), bbf_gpole()]
    inline(s, stages)   # flatten the filter stages into the block (layout packs better flat)
    return [inv(), nor2(), nor3(), tg('s'), tg('m'), tg('l'), nsw(), bias(), ota_fast(), s]


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


def bbf_int():
    """Integrator: OTA + switched capacitor bank (unit + 1/2/4/8 x unit on bw0..3)."""
    s = Sub('pt_bbf_int', ['a', 'out', 'vcm', 'vbp', 'pd', *BWP, 'VDD', 'VSS'])
    s.x('pt_rfrx_otaf', 'vcm', 'a', 'out', 'vbp', 'pd', 'VDD', 'VSS')
    s.cap('a', 'out', CU)                          # always-on unit (widest bandwidth)
    for bit, side in (('bw0', CU), ('bw1', CU2), ('bw2', CU4), ('bw3', CU8)):
        s.x('pt_rfrx_tgs', 'a', f'c_{bit}', bit, bit + '_b', 'VDD', 'VSS')  # switch on the virtual-ground side
        s.cap(f'c_{bit}', 'out', side, CU)
    return s


def _tt(s, vin, v1, v2, q):
    """Tow-Thomas core: A1 lossy integrator (Rq = q R), A2 integrator, A3 inverter."""
    s.res('v3', 'a', R_UNIT_L)
    s.res(v1, 'a', q * R_UNIT_L)
    s.x('pt_bbf_int', 'a', v1, 'vcm', 'vbp', 'pd', *BWP, 'VDD', 'VSS')
    s.res(v1, 'b', R_UNIT_L)
    s.x('pt_bbf_int', 'b', v2, 'vcm', 'vbp', 'pd', *BWP, 'VDD', 'VSS')
    s.res(v2, 'c', R_UNIT_L)
    s.res('v3', 'c', R_UNIT_L)
    s.x('pt_rfrx_otaf', 'vcm', 'c', 'v3', 'vbp', 'pd', 'VDD', 'VSS')


def bbf_tt(name, q):
    """Unity-gain Tow-Thomas biquad (v1 band-pass, v2 low-pass)."""
    s = Sub(name, ['vin', 'v1', 'v2', 'vcm', 'vbp', 'pd', *BWP, 'VDD', 'VSS'])
    s.res('vin', 'a', R_UNIT_L)
    _tt(s, 'vin', 'v1', 'v2', q)
    return s


def bbf_gpole():
    """PGA stage: inverting real pole, gain = Rf/R1 = 1 + gain0 + 2 gain1 + 4 gain2 + 8 gain3
    (0..24 dB).  The pole 1/(Rf C) does not move with gain and, unlike a biquad, it has no Q to
    enhance when the OTA loop gain drops at high gain (round-2 fix for the top-code peaking)."""
    gn = ['gain0', 'gain0_b', 'gain1', 'gain1_b', 'gain2', 'gain2_b', 'gain3', 'gain3_b']
    s = Sub('pt_bbf_gpole', ['vin', 'out', 'vcm', 'vbp', 'pd', *gn, *BWP, 'VDD', 'VSS'])
    s.res('vin', 'a', R_UNIT_L)
    for bit, div, size in (('gain0', 1, 's'), ('gain1', 2, 's'), ('gain2', 4, 'm'), ('gain3', 8, 'l')):
        s.res('vin', f'g{div}', R_UNIT_L / div)
        s.x(f'pt_rfrx_tg{size}', f'g{div}', 'a', bit, bit + '_b', 'VDD', 'VSS')
    s.res('a', 'out', R_UNIT_L)
    s.x('pt_bbf_int', 'a', 'out', 'vcm', 'vbp', 'pd', *BWP, 'VDD', 'VSS')
    return s


# ---------------------------------------------------------------- generic observation buffer
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
        s.nmos_m(src, 'obs_on', f'pad_{h}', 20., 3)  # NMOS-only series switch: no PN path from pad to VDD
        s.nmos_m(f'pad_{h}', 'inj_on', f'inj_{h}', 20., 2)  # inject: pad -> chain node
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
