"""TT01 1x1 mezzanine COB channel model (wafer.space Run 1).

Geometry is extracted from the provider KiCad board (commit 4f05ed1 / sha256 b0de95da...).
Electrical model = cascaded ABCD: die pad C -> bond wire (L,R) -> finger C -> F.Cu microstrip
-> via (L,C) -> B.Cu microstrip -> connector land C -> connector contact (L,C, estimated)
-> carrier-board land + 10 mm 50-ohm line -> 50 ohm.
Outputs: geometry.json, channel.json in this directory. Lumped/analytic; NOT an EM solve.
"""
import json, math, cmath, collections, sys
import numpy as np
# copy of scratch/cob/channel_model.py for the 2026-11-14 bond map (pads owner); inputs still read from scratch/cob

HERE = '/home/ubuntu/svalbard/scratch/cob'
PCB = HERE + '/repo/run-1/1x1-cob/1x1-mezzanine.kicad_pcb'
OUT = '/home/ubuntu/svalbard/scratch/pads-core/spec'
d = json.load(open(HERE + '/raw.json'))
fp = {f['ref']: f for f in d['footprints']}
U102, U101 = fp['U102'], fp['U101']
ORG = U102['at']

# ---------------- die-site -> PCB bond-pad ordinal (as verification/audit_provider_cob.py) ----------
c = json.load(open('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/spec/contract.json'))
sides = c['assembly_policy']['provider_site_inventory']['ordered_sites_by_side']
# FIX 2026-11-14: contract lists north west->east; bond numbers run counter-clockwise, so north is reversed too
# (proof: north_proof.py, bond-audit.json).  The original reversed only west.
order = sides['south'] + sides['east'] + list(reversed(sides['north'])) + list(reversed(sides['west']))
_m = json.load(open(OUT + '/site_to_bond.json'))['site_to_bond']
assert all(_m[s] == i + 1 for i, s in enumerate(order)), 'site order disagrees with coordinate-derived bond numbers'
ordinal = {s: i + 1 for i, s in enumerate(order)}
side_of = {}
for sd in ('south', 'east', 'north', 'west'):
    for i, s in enumerate(sides[sd]): side_of[s] = sd

# bond map 2026-11-14: contract bond_map_current + coordinator decisions (WCLK_IN and LNA_SRC deleted; POR_BYPASS strap on
# bidir[16]; bidir[17] spare, held; option L1 = REF_IN/REF_IN_N swap sites with BB_Q_P/BB_Q_N; TLP site on bidir[25])
SIG = {
    'RF_RX_P': 'inputs[11].pad', 'RF_RX_N': 'inputs[10].pad', 'BB_I_P': 'inputs[9].pad', 'BB_I_N': 'inputs[8].pad',
    'BB_Q_P': 'inputs[7].pad', 'BB_Q_N': 'inputs[6].pad', 'AUX_CLK_P': 'inputs[5].pad', 'AUX_CLK_N': 'inputs[4].pad',
    'REF_IN': 'inputs[3].pad', 'REF_IN_N': 'inputs[2].pad', 'RF_TX_P': 'inputs[1].pad', 'RF_TX_N': 'inputs[0].pad',
    'WIRE_RX_P': 'bidir[15].pad', 'WIRE_RX_N': 'bidir[14].pad', 'POR_BYPASS': 'bidir[16].pad', 'SPARE_E17': 'bidir[17].pad',
    'USB_DN': 'bidir[18].pad', 'USB_DP': 'bidir[19].pad',
    'WIRE_TX_P': 'bidir[21].pad', 'WIRE_TX_N': 'bidir[20].pad', 'WTX_EXT_P': 'bidir[22].pad', 'WTX_EXT_N': 'bidir[23].pad',
    'WMON': 'bidir[24].pad', 'TLP_TEST': 'bidir[25].pad',
    'ATB0': 'analog[0].pad', 'ATB1': 'analog[1].pad', 'CLK_OBS': 'bidir[37].pad', 'DBG_OBS0': 'bidir[38].pad',
    'DBG_OBS1': 'bidir[39].pad', 'RESET_N': 'rst_n_pad',
}
for k, v in c['assembly_policy']['candidate_signal_sites'].items():
    if k.startswith(('D2H', 'H2D', 'HOST_')): SIG[k] = v
SIG['HOST_CS_N'] = 'bidir[10].pad'
assert len(set(SIG.values())) == len(SIG) == 56

CLASS = {}
for s in SIG:
    if s.startswith('RF_RX'): CLASS[s] = 'rf_rx'
    elif s.startswith('RF_TX'): CLASS[s] = 'rf_tx'
    elif s.startswith(('REF_IN', 'AUX_CLK')): CLASS[s] = 'lo_ref'
    elif s.startswith('WIRE_RX'): CLASS[s] = 'wired_rx'
    elif s.startswith('WIRE_TX'): CLASS[s] = 'wired_tx'
    elif s.startswith('WTX_EXT'): CLASS[s] = 'wired_aux'
    elif s.startswith('USB_'): CLASS[s] = 'usb'
    elif s == 'POR_BYPASS': CLASS[s] = 'strap'
    elif s == 'SPARE_E17': CLASS[s] = 'spare'
    elif s == 'TLP_TEST': CLASS[s] = 'test'
    elif s.startswith(('D2H', 'H2D')): CLASS[s] = 'host'
    elif s.startswith('HOST_') or s == 'RESET_N': CLASS[s] = 'spi'
    else: CLASS[s] = 'debug'
# die-side load C (pF) per class: pads README (lean RF 0.50; wired TX 1.80; RX/USB 2.35 today);
# refpad ~1.0; provider bidir GPIO ~4 (fpga-host-screen).  Termination at die per class.
CPAD = dict(rf_rx=0.50, rf_tx=1.0, lo_ref=1.0, wired_rx=2.35, wired_tx=1.80, wired_aux=1.0, host=4.0, spi=4.0, debug=1.5,
            usb=2.35,    # pad_wirepad, as wired_rx (was in 'debug' 1.5 pF under the retired names)
            strap=4.0, spare=4.0,   # provider cell, same figure as the other provider sites (in_c is not characterised separately)
            test=1.5)    # TLP site: unchanged from the old ESD_TEST entry ('debug')
UNTERMINATED = ('host', 'spi', 'debug', 'usb', 'strap', 'spare', 'test')

# ---------------- geometry -----------------------------------------------------------------------
DIE_W, DIE_H, PITCH, INSET = 3.93, 5.12, 0.211, 0.075   # mm; site pitch 211 um (pad_* pair 422 um)

def die_xy(site):
    sd = side_of[site]; idx = sides[sd].index(site); n = len(sides[sd])
    off = (idx - (n - 1) / 2) * PITCH
    # same direction convention as PCB finger numbering (ordinal increases along the walk)
    if sd == 'south': return (-off, -(DIE_H / 2 - INSET))        # PCB 1..17 run x +3.2 -> -3.2 at y=-4.7
    if sd == 'east': return (-(DIE_W / 2 - INSET), off)           # 18..37 at x=-4.3, y -3.8 -> +3.8
    if sd == 'north': return (-off, DIE_H / 2 - INSET)             # FIX: contract list is die west->east = PCB x +3.2 -> -3.2 (bonds 54..38)
    return ((DIE_W / 2 - INSET), off)                              # west reversed: 55..74 at x=+4.3, y +3.8 -> -3.8

def finger_bond_xy(n):
    p = [q for q in U102['pads'] if q['num'] == str(n)][0]
    x, y = p['at']
    if abs(y) > 4.5: y = math.copysign(abs(y) - 0.35, y)          # bond in inner third of 1.0 mm finger
    else: x = math.copysign(abs(x) - 0.35, x)
    return x, y

conn = {q['num']: q for q in U101['pads']}
gnd_contacts = [int(k) for k, q in conn.items() if k.isdigit() and q['net'] == 'GND']
gvias = [v['at'] for v in d['vias']['GND']]

def conn_dist_to_gnd(cn):
    """distance (mm) along the connector from contact cn to the nearest GND contact / shell tab."""
    xs = lambda k: conn[str(k)]['at']
    x, y = xs(cn)
    best = min(math.hypot(x - xs(g)[0], y - xs(g)[1]) for g in gnd_contacts)
    tabs = [q['at'] for q in U101['pads'] if q['num'] == 'MP']
    return min(best, min(math.hypot(x - t[0], y - t[1]) for t in tabs))

def seg_len(net):
    L = collections.Counter()
    for s in d['segs'].get(net, []): L[s['layer']] += s['L']
    return L

def min_spacing(net, layer):
    """min centre spacing (mm) and coupled length (<0.5 mm) to any other signal net on the same layer."""
    mine = [s for s in d['segs'][net] if s['layer'] == layer]
    best = 9; coup = 0.0; who = None
    for other, ss in d['segs'].items():
        if other == net or other is None: continue
        for a in mine:
            (ax1, ay1), (ax2, ay2) = a['p']
            for b in ss:
                if b['layer'] != layer: continue
                # sample a at 5 points, distance to segment b
                (bx1, by1), (bx2, by2) = b['p']
                vx, vy = bx2 - bx1, by2 - by1; ll = vx * vx + vy * vy or 1e-12
                n_close = 0
                for t in np.linspace(0, 1, 6):
                    px, py = ax1 + t * (ax2 - ax1), ay1 + t * (ay2 - ay1)
                    u = max(0, min(1, ((px - bx1) * vx + (py - by1) * vy) / ll))
                    dd = math.hypot(px - bx1 - u * vx, py - by1 - u * vy)
                    if dd < best: best, who = dd, other
                    if dd < 0.5: n_close += 1
                coup += a['L'] * n_close / 6
    return best, coup, who

# ---------------- electrical primitives -----------------------------------------------------------
H, ER, TAND, T, W = 0.196e-3, 4.5, 0.02, 17.5e-6, 0.1e-3
def microstrip(w=W, h=H, er=ER, t=T):
    we = w + t / math.pi * (1 + math.log(2 * h / t))
    u = we / h
    eeff = (er + 1) / 2 + (er - 1) / 2 * (1 + 12 / u) ** -0.5
    z0 = 60 / math.sqrt(eeff) * math.log(8 / u + u / 4) if u <= 1 else \
        120 * math.pi / math.sqrt(eeff) / (u + 1.393 + 0.667 * math.log(u + 1.444))
    return z0, eeff
Z_MS, EEFF = microstrip()

def abcd_series(Z): return np.array([[1, Z], [0, 1]], complex)
def abcd_shunt(Y): return np.array([[1, 0], [Y, 1]], complex)
def abcd_line(z0, eeff, L, f, w=W):
    rs = math.sqrt(math.pi * f * 4e-7 * math.pi / 5.8e7)
    alpha_c = rs / (z0 * w) * 1.3               # Np/m, narrow-strip + return-plane factor
    alpha_d = math.pi * f * math.sqrt(eeff) / 3e8 * TAND * (ER / eeff) * (eeff - 1) / (ER - 1)
    g = alpha_c + alpha_d + 1j * 2 * math.pi * f * math.sqrt(eeff) / 3e8
    return np.array([[cmath.cosh(g * L), z0 * cmath.sinh(g * L)], [cmath.sinh(g * L) / z0, cmath.cosh(g * L)]])

def wire_L_per_mm(h=0.40, dia=0.025):
    return 0.2 * math.log(4 * h / dia)            # nH/mm, wire over In1 plane (loop ~0.2 mm + 0.196 mm FR4)

CONN_L0, CONN_C = 0.6, 0.25                       # nH, pF: 0.4 mm B2B contact, 1.5 mm mated (estimate)
def conn_L(dist_mm):                              # loop inductance grows with distance to nearest GND contact
    return CONN_L0 + 0.2 * 1.5 * math.log(1 + dist_mm / 0.3)

def chain(p, f, cpad=None, rterm=None, carrier_mm=10.0):
    """ABCD from die (port 1) to carrier 50-ohm line end (port 2)."""
    w = 2 * math.pi * f
    M = np.eye(2, dtype=complex)
    Lb = p['bond_mm'] * wire_L_per_mm() * 1e-9
    Rb = 0.05 * p['bond_mm'] * math.sqrt(f / 1e9) + 0.05      # ohm, 25 um Au skin + contact
    elems = [abcd_series(Rb + 1j * w * Lb),
             abcd_shunt(1j * w * 0.08e-12),                    # finger 1.0 x 0.25 mm over In1
             abcd_line(Z_MS, EEFF, p['f_mm'] * 1e-3, f),
             abcd_series(1j * w * p['via_nH'] * 1e-9), abcd_shunt(1j * w * 0.10e-12),
             abcd_line(Z_MS, EEFF, p['b_mm'] * 1e-3, f),
             abcd_shunt(1j * w * 0.06e-12),                    # connector land 0.2 x 0.66
             abcd_series(1j * w * p['conn_nH'] * 1e-9), abcd_shunt(1j * w * CONN_C * 1e-12),
             abcd_line(50.0, 3.3, carrier_mm * 1e-3, f)]
    for e in elems: M = M @ e
    return M

def sparams(M, z1=50.0, z2=50.0):
    A, B, C, D = M[0, 0], M[0, 1], M[1, 0], M[1, 1]
    den = A * z2 + B + C * z1 * z2 + D * z1
    s11 = (A * z2 + B - C * z1 * z2 - D * z1) / den
    s21 = 2 * math.sqrt(z1 * z2) / den
    return s11, s21

def with_die(p, f, cls, rterm=50.0):
    """Insertion/return loss seen from the carrier with the die load = pad C || rterm (on-die termination)."""
    M = chain(p, f)
    w = 2 * math.pi * f
    Zd = 1 / (1j * w * CPAD[cls] * 1e-12 + (1 / rterm if rterm else 0))
    # input impedance looking into port 2 (carrier side) with die load at port 1
    A, B, C, D = M[0, 0], M[0, 1], M[1, 0], M[1, 1]
    # reverse: Zin2 = (D*Zd + B)/(C*Zd + A)
    Zin2 = (D * Zd + B) / (C * Zd + A)
    g = (Zin2 - 50) / (Zin2 + 50)
    # transfer: source 50 ohm at carrier end -> voltage on die
    # V2 = A V1 + B I1' with I1' into load... use port1 as load: V2 = A*V1 + B*(V1/Zd)
    Vs = 1.0
    V2 = Vs * Zin2 / (Zin2 + 50)
    V1 = V2 / (A + B / Zd)
    # reference: ideal matched delivery to rterm (or 50) -> V = 0.5
    ref = 0.5 if rterm else 1.0
    return g, V1 / ref

def interconnect_only(p, f):
    s11, s21 = sparams(chain(p, f))
    return s11, s21

def run():
    geo = {}
    for sig, site in SIG.items():
        n = ordinal[site]
        net = [q['net'] for q in U102['pads'] if q['num'] == str(n)][0]
        dx, dy = die_xy(site); fx, fy = finger_bond_xy(n)
        planar = math.hypot(fx - dx, fy - dy)
        bond = 1.1 * planar + 0.15
        angle = math.degrees(math.atan2(abs((fx - dx) if abs(fy) > 4.0 else (fy - dy)),
                                        abs((fy - dy) if abs(fy) > 4.0 else (fx - dx))))
        L = seg_len(net)
        via = d['vias'][net][0]['at']
        gd = min(math.hypot(via[0] - g[0], via[1] - g[1]) for g in gvias)
        via_nH = 0.2 * 0.747 * math.log(gd / 0.15) + 0.05      # signal/return via pair partial loop (nH)
        cn = [int(k) for k, q in conn.items() if k.isdigit() and q['net'] == net][0]
        cg = conn_dist_to_gnd(cn)
        sF, cF, wF = min_spacing(net, 'F.Cu'); sB, cB, wB = min_spacing(net, 'B.Cu')
        geo[sig] = dict(site=site, bond_pad=n, board_net=net, connector_contact=cn, cls=CLASS[sig],
                        bond_mm=round(bond, 2), bond_angle_deg=round(angle, 1), f_mm=round(L['F.Cu'], 2),
                        b_mm=round(L['B.Cu'], 2), trace_w_mm=0.1, vias=1, via_to_gnd_via_mm=round(gd, 2),
                        via_nH=round(via_nH, 3), conn_dist_gnd_mm=round(cg, 2), conn_nH=round(conn_L(cg), 2),
                        minsp_F_mm=round(sF, 3), coupled_F_mm=round(cF, 2), nbr_F=wF,
                        minsp_B_mm=round(sB, 3), coupled_B_mm=round(cB, 2), nbr_B=wB,
                        ref_plane='F.Cu over In1.Cu GND (0.196 mm prepreg), B.Cu over In2.Cu GND (0.196 mm)')
    # supplies / grounds
    sup = {}
    for q in U102['pads']:
        if q['num'].isdigit() and int(q['num']) <= 74 and not q['net'].startswith('/'):
            n = int(q['num']); site = order[n - 1]
            sup[site] = dict(bond_pad=n, net=q['net'], f_mm=round(seg_len(q['net'])['F.Cu'], 2) if q['net'] != 'GND' else None,
                             connector=[int(k) for k, x in conn.items() if k.isdigit() and x['net'] == q['net']] if q['net'] != 'GND' else 'GND plane')
    freqs = [156.25e6, 1.25e9, 2.45e9]
    out = {}
    for sig, p in geo.items():
        r = {}
        for f in freqs:
            s11, s21 = interconnect_only(p, f)
            rterm = None if p['cls'] in UNTERMINATED else 50.0
            g, h = with_die(p, f, p['cls'], rterm)
            r[f'{f/1e6:g}MHz'] = dict(IL_interconnect_dB=round(-20 * math.log10(abs(s21)), 2),
                                      RL_interconnect_dB=round(-20 * math.log10(abs(s11)), 1),
                                      RL_with_die_dB=round(-20 * math.log10(max(abs(g), 1e-6)), 1),
                                      gain_to_die_dB=round(20 * math.log10(abs(h)), 2))
        out[sig] = r
    return geo, sup, out

def xtalk(geo):
    """adjacent-pin crosstalk: bond wire mutual (dominant) + trace coupling + connector, 50-ohm terminated."""
    res = {}
    ordered = sorted(geo.items(), key=lambda kv: kv[1]['bond_pad'])
    pads = {v['bond_pad']: k for k, v in geo.items()}
    for sig, p in geo.items():
        n = p['bond_pad']; out = {}
        for nb in (n - 1, n + 1):
            if nb not in pads: continue
            q = geo[pads[nb]]
            for f in (156.25e6, 1.25e9, 2.45e9):
                w = 2 * math.pi * f
                # bond: wires over plane, die-end spacing 0.211, finger-end 0.4: M/L avg
                Lpm = wire_L_per_mm()
                Mpm = 0.5 * (0.1 * math.log(1 + (0.8 / 0.211) ** 2) + 0.1 * math.log(1 + (0.8 / 0.4) ** 2))
                Mb = Mpm * min(p['bond_mm'], q['bond_mm']) * 1e-9
                # trace: microstrip coupling coefficient ~ 1/(1+(s/h)^2), backward (NEXT) coefficient kb=k/2
                kF = 1 / (1 + (p['minsp_F_mm'] / 0.196) ** 2) if q['board_net'] == p['nbr_F'] else 0.0
                kB = 1 / (1 + (p['minsp_B_mm'] / 0.196) ** 2) if q['board_net'] == p['nbr_B'] else 0.0
                # connector: adjacent contacts 0.4 mm, k ~ 0.3 when far from a GND contact, ~0.15 next to it
                kc = 0.15 + 0.15 * min(1, p['conn_dist_gnd_mm'] / 2.0) if abs(p['connector_contact'] - q['connector_contact']) == 1 else 0.05
                Mc = kc * p['conn_nH'] * 1e-9
                Vind = w * (Mb + Mc) / (2 * 50)              # inductive NEXT+FEXT into 50||50 (per volt aggressor)
                tdF = p['coupled_F_mm'] * 1e-3 * math.sqrt(EEFF) / 3e8
                tdB = p['coupled_B_mm'] * 1e-3 * math.sqrt(EEFF) / 3e8
                Vtr = 0.5 * (kF * min(1, w * tdF) + kB * min(1, w * tdB)) * 0.5
                out.setdefault(pads[nb], {})[f'{f/1e6:g}MHz'] = round(20 * math.log10(max(Vind + Vtr, 1e-6)), 1)
        res[sig] = out
    return res

def pulse(p, cls, rate=2.5e9, rterm=50.0, n=4096, fs=200e9):
    """single-bit pulse response through the full channel (source 50 ohm carrier -> die pad C || rterm)."""
    f = np.fft.rfftfreq(n, 1 / fs); H = np.zeros(len(f), complex)
    for i, fi in enumerate(f):
        if fi == 0: H[i] = 1; continue
        _, h = with_die(p, fi, cls, rterm); H[i] = h
    t = np.arange(n) / fs; ui = 1 / rate
    x = ((t >= 0) & (t < ui)).astype(float)
    y = np.fft.irfft(np.fft.rfft(x) * H, n)
    imp = np.fft.irfft(H, n); step = np.cumsum(imp)
    k = int(np.argmax(y)); spu = int(ui * fs)
    cur = y[k]; pre = y[k - spu] if k >= spu else 0; post = [y[k + j * spu] for j in (1, 2, 3)]
    # 10-90 rise of step
    s = step[: n // 2]; s = s / s[-200:].mean()
    t10 = np.argmax(s > 0.1) / fs; t90 = np.argmax(s > 0.9) / fs
    return dict(main=round(float(cur), 3), pre=round(float(pre), 3), post=[round(float(v), 3) for v in post],
                isi_sum_abs=round(float(abs(pre) + sum(abs(v) for v in post)), 3),
                eye_open_frac=round(float(cur - abs(pre) - sum(abs(v) for v in post)), 3),
                rise_10_90_ps=round((t90 - t10) * 1e12, 1),
                overshoot=round(float(s.max() - 1), 3))

if __name__ == '__main__':
    geo, sup, out = run()
    xt = xtalk(geo)
    pr = {}
    for sig in ('WIRE_RX_P', 'WIRE_TX_P', 'WTX_EXT_P', 'D2H_CLK', 'H2D_CLK'):
        cls = geo[sig]['cls']
        pr[sig] = pulse(geo[sig], cls, 2.5e9 if cls.startswith('wired') else 312.5e6,
                        None if cls == 'host' else 50.0)
    # 2.5 Gb/s with the S7 target pad C and ideal 1 nH bond for comparison
    save = dict(CPAD)
    CPAD['wired_rx'] = 1.6; pr['WIRE_RX_P@1.6pF'] = pulse(geo['WIRE_RX_P'], 'wired_rx'); CPAD.update(save)
    g0 = dict(geo['WIRE_RX_P'], bond_mm=1.5, f_mm=0, b_mm=0, via_nH=0, conn_nH=0)
    pr['WIRE_RX_P@old_assumption_1.5nH_only'] = pulse(g0, 'wired_rx')
    json.dump(dict(source=dict(repo='https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs',
                               board='run-1/1x1-cob/1x1-mezzanine.kicad_pcb', clone_head='5cb4668',
                               board_sha256='b0de95dacd95a0e7ce6c4f997747d313230c8f4f259d64994fb9e6ab4f69dd8b'),
                   microstrip=dict(w_mm=0.1, h_mm=0.196, er=ER, z0_ohm=round(Z_MS, 1), eeff=round(EEFF, 2)),
                   bond_L_nH_per_mm=round(wire_L_per_mm(), 2), cpad_pF=CPAD,
                   geometry=geo, supplies_grounds=sup, sparams=out, xtalk_dB=xt, pulse=pr),
              open(OUT + '/channel.json', 'w'), indent=1)
    print('Z_ms', round(Z_MS, 1), 'eeff', round(EEFF, 2), 'bondL/mm', round(wire_L_per_mm(), 2))
    for s, p in sorted(geo.items(), key=lambda kv: kv[1]['bond_pad']):
        print(f"{s:10s} pad{p['bond_pad']:>3} c{p['connector_contact']:>3} bond {p['bond_mm']:.2f}mm/{p['bond_angle_deg']:4.1f}deg "
              f"F {p['f_mm']:.2f} B {p['b_mm']:.2f} via {p['via_nH']:.2f}nH connL {p['conn_nH']:.2f} gnd@{p['conn_dist_gnd_mm']:.1f} "
              f"sp {p['minsp_F_mm']:.2f}/{p['minsp_B_mm']:.2f} | " +
              ' '.join(f"{k}: IL{v['IL_interconnect_dB']} RLd{v['RL_with_die_dB']} G{v['gain_to_die_dB']}" for k, v in out[s].items()))
    for k, v in pr.items(): print(k, v)
    for s in ('RF_RX_P', 'RF_TX_P', 'REF_IN', 'AUX_CLK_P', 'WIRE_RX_P', 'WIRE_TX_P', 'D2H_CLK', 'H2D_CLK', 'D2H_D[0]'):
        print('xt', s, xt[s])
