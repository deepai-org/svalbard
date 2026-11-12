"""Fully differential baseband filter / PGA (fork S redesign: RC-17, GX-1, DCOC-F, CNV-01; fork U review fixes).

Fork U (review NO-GO, scratch/review-bbf): the Tow-Thomas biquads oscillated at cap code 0 with slow MOS and
fast poly/MIM (31 MHz, 2.5 V pp).  Root cause: integrator loop gain beta * A(f) ~ 1.6 at 45 MHz (beta ~ 0.29:
100 fF integrator C against ~250 fF of summing-node C = OTA input Cgs + routing).  Fix: biquad impedance
halved (R 40 -> 20 kohm, every biquad capacitor x2: beta ~ 0.44) and a smaller biquad OTA input pair
(60/0.5 -> 40/0.35: less Cgs at nearly the same gm); stage-1 OTA Miller C 12.2 -> 8 um (less PGA-dependent
cutoff); +12 dB biquad step switch tgm -> tgl (gain error with the 20 kohm network).

Topology (one differential path; the previous design was two single-ended halves):
  stage 1  PGA real pole: FD inverting amplifier, gain k/4 (6-bit conductance bank), pole 1/(R C)
  stage 2  Tow-Thomas biquad, Q_A (low Q), +12 dB step gainc0
  stage 3  Tow-Thomas biquad, Q_B (high Q), +12 dB step gainc1, Q-trim qt0/qt1
Every integrator is a fully differential two-stage Miller OTA with its own continuous CMFB (output CM
= vref = atb_vcm, the mean of the core inputs), so the common mode has unity gain at every PGA code
(RC-17: the pseudo-differential version multiplied a reference error by the PGA gain and latched).
The Tow-Thomas inverter (A3) is a p/n cross-connection: 2 OTAs per biquad instead of 6.

Each integrator is its own layout cell (OTA + both capacitor banks + every resistor that lands on its
summing nodes), so the virtual grounds never leave the cell (fork B: the flat auto-placed filter moved
virtual-ground parasitics by +-50 % between relayouts).

Capacitor bank per integrator side: C0 always on + coarse bw0..3 (1,2,4,8 x CU) + fine fc_fine0..2
(CF, 2 CF, 4 CF; CF = two series 5 um MIMs), NMOS switches on the virtual-ground side.
Corner: f = 1/(2 pi R (C0 + CU n + CF f)); n = 0, f = 0 is the widest (GX-1 wide range).
Fine DC-offset DAC (DCOC-F): sign + 8 bits, current into the stage-1 summing nodes.
"""
import netlists as N

Sub = N.Sub
R_L = 16.0            # biquad unit resistor length (um ppolyf_u_1k w=1) ~ 16 kohm (fork U: 40 -> 20 with C x2; fork B: x0.8
# so the trimmed cap codes sit higher (ss ~m 9, ff ~m 20): at m ~6 one fine LSB moved f3 by ~10 %, more than the
# +-0.5 MHz (9.5 %) CNV-01 window, so ss/30 dB had no passing code)
R_S1 = 32.0           # stage-1 (PGA) unit resistor ~ 32 kohm (fork B: x0.8 with the biquads, same pole/C ratio; DCOC LSB x0.8)
# stage-1 bank geometry (fork S sizes): the stage-1 real pole keeps 40 kohm x the original capacitors
BANK_S1 = dict(C0_SIDE=8.0, CU_DIMS=((10., 10.), (10., 20.), (20., 20.), (20., 40.)), CF_SIDE=5.0, SW_W=(2., 4., 8., 16.))
C0_SIDE = 11.3        # biquad always-on integrator cap side (um) ~ 255 fF (fork U: 9.9 = x2 with R/2; fork B: area x1.3
# with R x0.8 so the widest code's integrator frequency stays at or below fork U's kick-proven value)
CU_SIDE = 10.0        # coarse unit (bw0) ~ 200 fF; bw1..3 = 2, 4, 8 x (wider plates)
CU_DIMS = ((10., 20.), (20., 20.), (20., 40.), (40., 40.))   # biquad bw0..3 plates (1, 2, 4, 8 x CU ~ 400 fF)
SW_W = (4., 8., 16., 32.)   # biquad bank switches (x2 C -> x2 W keeps Ron C).  Fork B (review item 3): x4.  At 1/2/4/8 um
# the switch Ron in series with each integrator C added a zero that moved f3 by ~12 % and opened a ~2.5-LSB gap
# at every coarse/fine boundary (m 7 -> 8: 11.9 -> 10.0 MHz extracted), so no cap code met 10.5 +-0.5 MHz
SWF_W = 4.   # fork B: was 1 (Ron gap, see SW_W); bank switch widths (Ron C << 1/(2 pi f) at every code; small = little C on the virtual ground)
CF_SIDE = 7.07        # biquad fine LSB: two 7.07 um MIMs in series ~ 50 fF; fine1 = one (100 fF), fine2 = 10 um (200 fF)
QA, QB = 0.618, 1.618  # 5th-order Butterworth (real pole + these two)
QA_PRE, QB_PRE = 0.618, 1.618  # Q at the reset trim code (q_top = Q / (1 - QT_RESET QT_STEP))
QT = ['qt0', 'qt1', 'qt2', 'qt3']
QT_STEP = 0.032       # Q-trim LSB (fraction of q_top): k = 0..15 -> Q x 1 .. 0.52
QT_RESET = 6          # reset code: Q = q_top (1 - 6 x 0.032) = target
QT_GC = 0.05          # Rq fraction shorted with gc (Q enhancement of the +12 dB step)
LEAD_SIDE = 8.49       # Tow-Thomas lead: two series 8.49 um MIMs (~72 fF) across the A1->A2 resistor
DCF_BITS = 8
R_DCF_ISO = 100.0
# FD OTA sizing (tail, pair W/L, load W/L, 2nd stage NMOS W/L, PMOS source W, Miller cap side, Rz, CMFB tail)
OTA_B = dict(tail=32., win=40., lin=.35, wl=16., ll=1., w6=36., l6=.5, w7=72., cc=12.2, rz=3., ctail=16., rs=60.)
OTA_S1 = dict(tail=32., win=60., lin=.5, wl=16., ll=1., w6=72., l6=.5, w7=144., cc=12.2, rz=1.5, ctail=16., rs=60.)
BW = ['bw0', 'bw1', 'bw2', 'bw3']
FC = ['fc_fine0', 'fc_fine1', 'fc_fine2']
GN = [f'gain{k}' for k in range(6)]
DCF = [f'dcf{k}' for k in range(DCF_BITS)]


def _r(s, a, b, l):
    """Resistor of l um-equivalent (w = 1); short ones keep l >= 2 um by widening."""
    if l < 2.:
        s.res(a, b, 2., round(2. / l, 3))
    else:
        s.res(a, b, round(l, 2))


def ota_fd(name, p):
    """FD two-stage Miller OTA, PMOS input, continuous CMFB on the first-stage loads.
    outp = A (inp - inn).  pd = 1: off (supply switches open, first-stage nodes pulled low)."""
    s = Sub(name, ['inp', 'inn', 'outp', 'outn', 'vref', 'vbp', 'pd', 'VDD', 'VSS'])
    s.pmos('ts', 'pd', 'VDD', max(8., p['tail'] + p['ctail']))
    s.pmos('tail', 'vbp', 'ts', p['tail'], 1.)
    s.pmos('xa', 'inp', 'tail', p['win'], p['lin'])   # inp -> xa -> outp (non-inverting)
    s.pmos('xb', 'inn', 'tail', p['win'], p['lin'])
    s.nmos('xa', 'cmfb', 'VSS', p['wl'], p['ll'])
    s.nmos('xb', 'cmfb', 'VSS', p['wl'], p['ll'])
    s.pmos('os', 'pd', 'VDD', max(40., 2 * p['w7']))
    s.nmos('outp', 'xa', 'VSS', p['w6'], p['l6'])
    s.nmos('outn', 'xb', 'VSS', p['w6'], p['l6'])
    s.pmos('outp', 'vbp', 'os', p['w7'], 1.)
    s.pmos('outn', 'vbp', 'os', p['w7'], 1.)
    s.res('xa', 'za', max(2., p['rz']), max(2., p['rz']) / p['rz'])
    s.cap('za', 'outp', p['cc'])
    s.res('xb', 'zb', max(2., p['rz']), max(2., p['rz']) / p['rz'])
    s.cap('zb', 'outn', p['cc'])
    # CMFB: output CM sensed by Rs || Cs, PMOS error pair against vref; diode on the sense side sets the loads
    s.res('outp', 'ocm', p['rs'])
    s.res('outn', 'ocm', p['rs'])
    s.cap('outp', 'ocm', 5.)
    s.cap('outn', 'ocm', 5.)
    s.pmos('ctl', 'vbp', 'ts', p['ctail'], 1.)
    s.pmos('cmfb', 'ocm', 'ctl', p['win'] / 2, p['lin'])
    s.pmos('cdump', 'vref', 'ctl', p['win'] / 2, p['lin'])
    wd = p['wl'] * p['ctail'] / p['tail']             # load / diode = tail / ctail (both halves balanced)
    s.nmos('cmfb', 'cmfb', 'VSS', wd, p['ll'])
    s.nmos('cdump', 'cdump', 'VSS', wd, p['ll'])
    for n in ('xa', 'xb', 'cmfb'):
        s.nmos(n, 'pd', 'VSS', 1.)
    return s


def bank(name='pt_bbf_bank', geo=None):
    """One integrator side: C0 + coarse 1/2/4/8 CU + fine 1/2/4 CF between virtual ground a and out.
    NMOS switches on the virtual-ground side (CM ~1.65 V; Ron << 1/(w C) at every code)."""
    g = dict(C0_SIDE=C0_SIDE, CU_DIMS=CU_DIMS, CF_SIDE=CF_SIDE, SW_W=SW_W, SWF_W=SWF_W)
    g.update(geo or {})
    s = Sub(name, ['a', 'out', *BW, *FC, 'VSS'])
    s.cap('a', 'out', g['C0_SIDE'])
    for k, b in enumerate(BW):
        s.nmos('a', b, f'c{k}', g['SW_W'][k], .28)
        w_, l_ = g['CU_DIMS'][k]
        s.cap(f'c{k}', 'out', w_, l_)
    cf = g['CF_SIDE']
    s.nmos('a', 'fc_fine0', 'f0', g['SWF_W'], .28)
    s.cap('f0', 'f0m', cf)
    s.cap('f0m', 'out', cf)
    s.nmos('a', 'fc_fine1', 'f1', g['SWF_W'], .28)
    s.cap('f1', 'out', cf)
    s.nmos('a', 'fc_fine2', 'f2', g['SWF_W'], .28)
    s.cap('f2', 'out', round(cf * 2 ** .5, 2))
    return s


PAR_EMU = None   # exploration only: {'m': F, 'o': F} ideal C on summing nodes / outputs (never published)


def _int_core(s, ota, ip, inn_, op, on, banks=True, bank_cell='pt_bbf_bank'):
    """FD integrator core: OTA with summing nodes mp (-> inn, fb from op) and mn (-> inp, fb from on)."""
    s.x(ota, 'mn', 'mp', op, on, 'vref', 'vbp', 'pd', 'VDD', 'VSS')
    if PAR_EMU:
        for n, k in (('mp', 'm'), ('mn', 'm'), (op, 'o'), (on, 'o')):
            s.lines.append(f'Cemu_{n} {n} VSS {PAR_EMU[k]:g}')
    if banks:
        s.x(bank_cell, 'mp', op, *BW, *FC, 'VSS')
        s.x(bank_cell, 'mn', on, *BW, *FC, 'VSS')


def stage1():
    """PGA real pole.  Input p -> mp: outp = -(Rf/Rin) in_p.  gain = k/4, k = sum 2^j gain_j."""
    s = Sub('pt_bbf_s1', ['in_p', 'in_n', 'outp', 'outn', 'vref', 'vbp', 'pd', *GN,
                          *[x + '_b' for x in GN], *BW, *FC, *DCF, 'dcf_sign', 'VDD', 'VSS'])
    # fork U: the DCOC DAC lives inside the stage-1 cell.  As a separate macro its high-impedance output
    # nets (dci, 100 kohm into the summing nodes) were routed at the top next to the filter output co
    # (51 fF co_p -> dci_n in the fork-U relayout): a +42 dB feedback path from the output into the PGA
    # summing node (3 dB passband dip at 4 MHz at PGA >= 21 dB, found with a top-level C strip test).
    s.x('pt_bbf_dcdac', 'dci_p', 'dci_n', 'vbp', *DCF, 'dcf_sign', 'VDD', 'VSS')
    r1 = R_S1 or R_L
    for h, m in (('p', 'mp'), ('n', 'mn')):
        for j, size in enumerate(('s', 's', 's', 'm', 'm', 'l')):
            s.res(f'in_{h}', f'g{j}{h}', 4 * r1 / (1 << j))
            s.x(f'pt_rfrx_tg{size}', f'g{j}{h}', m, f'gain{j}', f'gain{j}_b', 'VDD', 'VSS')
        s.res(m, 'outp' if h == 'p' else 'outn', r1)
        s.res(f'dci_{h}', m, R_DCF_ISO)
    _int_core(s, 'pt_bbf_ota1', 'in_p', 'in_n', 'outp', 'outn', bank_cell='pt_bbf_bank1' if BANK_S1 else 'pt_bbf_bank')
    return s


def tt_a(name, q, trim=True):
    """Tow-Thomas A1 (lossy integrator): inputs vin (R, + R/3 with gc), fb = -v2 (cross-wired outside),
    damping Rq: a series string (all TGs off: Q = q_top) whose binary segments are shorted by the 4-bit
    Q-trim (Q = q_top (1 - k QT_STEP), k = qt3..0) and by gc (the +12 dB input raises A1's noise gain
    and with it the Q enhancement; QT_GC compensates)."""
    ports = ['vin_p', 'vin_n', 'fb_p', 'fb_n', 'v1_p', 'v1_n', 'vref', 'vbp', 'pd', 'gc', 'gc_b',
             *[x for b in QT for x in (b, b + '_b')], *BW, *FC, 'VDD', 'VSS']
    s = Sub(name, ports)
    qtop = q / (1 - QT_RESET * QT_STEP)
    segs = [(f'qt{j}', (1 << j) * QT_STEP) for j in range(len(QT))] + [('gc', QT_GC)]
    base = 1 - sum(f for _, f in segs)
    for h, m in (('p', 'mp'), ('n', 'mn')):
        s.res(f'vin_{h}', m, R_L)
        s.res(f'vin_{h}', f'gx{h}', R_L / 3)
        s.x('pt_rfrx_tgl', f'gx{h}', m, 'gc', 'gc_b', 'VDD', 'VSS')
        s.res(f'fb_{h}', m, R_L)
        node = f'v1_{h}'
        for k, (bit, frac) in enumerate(segs if trim else ()):
            nxt = f'q{k}{h}'
            _r(s, node, nxt, frac * qtop * R_L)
            s.x('pt_rfrx_tgs', node, nxt, bit, bit + '_b', 'VDD', 'VSS')
            node = nxt
        _r(s, node, m, (base if trim else 1.) * qtop * R_L)
    _int_core(s, 'pt_bbf_ota', 'vin_p', 'vin_n', 'v1_p', 'v1_n')
    return s


def tt_b(name='pt_bbf_ttb'):
    """Tow-Thomas A2 (lossless integrator): v1 -> v2, optional lead cap across the input R."""
    s = Sub(name, ['v1_p', 'v1_n', 'v2_p', 'v2_n', 'vref', 'vbp', 'pd', *BW, *FC, 'VDD', 'VSS'])
    for h, m in (('p', 'mp'), ('n', 'mn')):
        s.res(f'v1_{h}', m, R_L)
        if LEAD_SIDE:   # two series MIMs (a single ~35 fF MIM is below the minimum PCell size)
            s.cap(f'v1_{h}', f'ld{h}', LEAD_SIDE)
            s.cap(f'ld{h}', m, LEAD_SIDE)
    _int_core(s, 'pt_bbf_ota', 'v1_p', 'v1_n', 'v2_p', 'v2_n')
    return s


def dcdac():
    """Fine DC-offset DAC (fork B design): sign-magnitude, 8 bits, LSB ~9.8 nA -> ~0.4 mV at the stage-1
    output (Rf = 40 kohm).  Sinks the sum from dci_p (sign 0) or dci_n (sign 1)."""
    s = Sub('pt_bbf_dcdac', ['dci_p', 'dci_n', 'vbp', *DCF, 'dcf_sign', 'VDD', 'VSS'])
    s.pmos('nd', 'vbp', 'VDD', .625, 8.)    # fork B: x1.25 reference with Rf 40 -> 32 kohm (same mV/LSB)
    s.nmos('nd', 'nd', 'VSS', 4., 4.)
    for k in range(DCF_BITS):
        w = .5 * (1 << k)
        if w <= 8:
            s.nmos(f'm{k}', 'nd', 'VSS', w, 16.)
        else:
            s.nmos_m(f'm{k}', 'nd', 'VSS', 8., int(w // 8), 16.)
        s.nmos('idac', f'dcf{k}', f'm{k}', 1.)
    s.x('pt_rfrx_inv', 'dcf_sign', 'sgn_b', 'VDD', 'VSS')
    s.nmos('dci_p', 'sgn_b', 'idac', 2.)
    s.nmos('dci_n', 'dcf_sign', 'idac', 2.)
    return s


PORTS = ['rx_in_p', 'rx_in_n', 'tx_in_p', 'tx_in_n', 'inj_p', 'inj_n',
         'out_rx_p', 'out_rx_n', 'out_tx_p', 'out_tx_n', 'obs_p', 'obs_n',
         'ibias', 'en', 'dir_tx', 'inj', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1',
         *BW, *GN, 'gainc0', 'gainc1', 'qt0', 'qt1', 'island_off',
         'atb_vcm', 'atb_vbp', 'VDD', 'VSS', 'qt2', 'qt3', *FC, *DCF, 'dcf_sign']


def bbfilter(name):
    """Top: control/switch group (pt_bbf_ctl) + stage 1 + DCOC DAC + 4 integrator cells (macros only)."""
    s = Sub('pt_bbf_ctl', [])        # ports filled in below
    t = Sub(name, PORTS)
    I = lambda a, y: s.x('pt_rfrx_inv', a, y, 'VDD', 'VSS')
    N2 = lambda a, b, y: s.x('pt_rfrx_nor2', a, b, y, 'VDD', 'VSS')
    N3 = lambda a, b, c, y: s.x('pt_rfrx_nor3', a, b, c, y, 'VDD', 'VSS')
    for c in ('en', 'dir_tx', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1',
              *GN, 'gainc0', 'gainc1', *QT):
        I(c, c + '_b')
    N3('en_b', 'dir_tx', 'inj', 'k_inrx')
    N3('en_b', 'dir_tx_b', 'inj', 'k_intx')
    N3('en_b', 'dir_tx', 'rx_direct', 'k_orx')
    N2('en_b', 'dir_tx_b', 'k_otx')
    N2('en_b', 'rx_direct_b', 'k_rxd')
    N2('en_b', 'byp_s1', 'k_s1run')
    N2('en_b', 'byp_s1_b', 'k_s1byp')
    N2('en_b', 'byp_s23', 'k_s23run')
    N2('en_b', 'byp_s23_b', 'k_s23byp')
    N3('en_b', 'obs_sel1', 'obs_sel0_b', 'k_obs1')
    N3('en_b', 'obs_sel1_b', 'obs_sel0', 'k_obs2')
    N3('en_b', 'obs_sel1_b', 'obs_sel0_b', 'k_obs3')
    for k in ('k_inrx', 'k_otx', 'k_s1byp', 'k_s23byp', 'k_obs1', 'k_obs2', 'k_obs3'):
        I(k, k + 'b')
    I('k_s1run', 'pd1')
    I('k_s23run', 'pd23')
    s.x('pt_rfrx_bias', 'ibias', 'en', 'en_b', 'atb_vbp', 'VDD', 'VSS')
    for h in 'pn':
        s.res(f'inj_{h}', 'atb_vcm', 200.)
    s.cap('atb_vcm', 'VSS', 31.6)

    def T(size, a, b, k):
        s.x(f'pt_rfrx_tg{size}', a, b, k, k + 'b' if k.startswith('k_') else k + '_b', 'VDD', 'VSS')

    for h in 'pn':
        T('m', f'rx_in_{h}', f'inj_{h}', 'k_inrx')
        s.x('pt_rfrx_nsw', f'tx_in_{h}', f'inj_{h}', 'k_intx', 'VSS')
        T('m', f'inj_{h}', f's1_{h}', 'k_s1byp')
        T('m', f's1_{h}', f'co_{h}', 'k_s23byp')
        s.x('pt_rfrx_nsw', f'co_{h}', f'out_rx_{h}', 'k_orx', 'VSS')
        T('m', f'co_{h}', f'out_tx_{h}', 'k_otx')
        s.x('pt_rfrx_nsw', f'rx_in_{h}', f'out_rx_{h}', 'k_rxd', 'VSS')
        T('s', f'rx_in_{h}', f'obs_{h}', 'k_obs1')
        T('s', f's1_{h}', f'obs_{h}', 'k_obs2')
        T('s', f'co_{h}', f'obs_{h}', 'k_obs3')
        for node in (f'out_rx_{h}', f'out_tx_{h}', f'obs_{h}'):
            s.nmos(node, 'island_off', 'VSS', 1., 10.)
    com = ['atb_vcm', 'atb_vbp']
    gnb = [x + '_b' for x in GN]
    qq = [x for b in QT for x in (b, b + '_b')]
    # stage 1 inverts: outp -> s1_n, outn -> s1_p
    t.x('pt_bbf_s1', 'inj_p', 'inj_n', 's1_n', 's1_p', *com, 'pd1', *GN, *gnb, *BW, *FC, *DCF, 'dcf_sign',
        'VDD', 'VSS')
    # biquad A (low Q): A1 -> bp1, A2 -> lp1 (non-inverting LP); fb = -lp1 (cross-wired)
    t.x('pt_bbf_tta', 's1_p', 's1_n', 'lp1_n', 'lp1_p', 'bp1_p', 'bp1_n', *com, 'pd23', 'gainc0', 'gainc0_b',
        *qq, *BW, *FC, 'VDD', 'VSS')
    t.x('pt_bbf_ttb', 'bp1_p', 'bp1_n', 'lp1_p', 'lp1_n', *com, 'pd23', *BW, *FC, 'VDD', 'VSS')
    t.x('pt_bbf_ttq', 'lp1_p', 'lp1_n', 'co_n', 'co_p', 'bp2_p', 'bp2_n', *com, 'pd23', 'gainc1', 'gainc1_b',
        *qq, *BW, *FC, 'VDD', 'VSS')
    t.x('pt_bbf_ttb', 'bp2_p', 'bp2_n', 'co_p', 'co_n', *com, 'pd23', *BW, *FC, 'VDD', 'VSS')
    tnets = {n for ln in t.lines for n in ln.split()[1:-1]} | set(PORTS)
    snets = []
    for ln in s.lines:
        tok = ln.split()
        nodes = tok[1:-1] if tok[0].startswith('X') and '=' not in ln else tok[1:5]
        for n in nodes:
            if n in tnets and n not in snets:
                snets.append(n)
    s.ports = snets
    t.x('pt_bbf_ctl', *snets)
    return [N.inv(), N.nor2(), N.nor3(), N.tg('s'), N.tg('m'), N.tg('l'), N.nsw(), N.bias(),
            ota_fd('pt_bbf_ota', OTA_B), ota_fd('pt_bbf_ota1', OTA_S1), bank(),
            *([bank('pt_bbf_bank1', BANK_S1)] if BANK_S1 else []), dcdac(), stage1(),
            tt_a('pt_bbf_tta', QA_PRE), tt_a('pt_bbf_ttq', QB_PRE), tt_b(), s, t]
