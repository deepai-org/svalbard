"""Passive-placement tolerance sweep on the TT01 COB channel (uses channel_model.py primitives).

Placement points (reference plane where the passive sits, measured from the die):
  strip   : COB passive strip (back side, board edge) = bond + F.Cu + via + B.Cu to strip (~3 mm); shunt-only rework
  conn+2  : carrier board just past the mezzanine connector (2 mm of 50-ohm line)
  car10/30/50 : carrier board 10/30/50 mm of 50-ohm line past the connector
For each, a 2-element L-match (Q_L=40, Q_C=200) is designed at the band centre and evaluated across the band and
for bond-length spread (+-0.3 mm). Lumped/analytic, not EM; component values are design points, not BOM.
"""
import json, math, cmath, sys
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/pads-core/spec')
import channel_model as cm

geo = json.load(open('/home/ubuntu/svalbard/scratch/pads-core/spec/channel.json'))['geometry']
PLACES = [('strip', None), ('conn+2mm', 2.0), ('car10mm', 10.0), ('car30mm', 30.0), ('car50mm', 50.0)]

def chain_to(p, f, place, dbond=0.0):
    w = 2 * math.pi * f
    q = dict(p, bond_mm=p['bond_mm'] + dbond)
    Lb = q['bond_mm'] * cm.wire_L_per_mm() * 1e-9
    Rb = 0.05 * q['bond_mm'] * math.sqrt(f / 1e9) + 0.05
    els = [cm.abcd_series(Rb + 1j * w * Lb), cm.abcd_shunt(1j * w * 0.08e-12),
           cm.abcd_line(cm.Z_MS, cm.EEFF, q['f_mm'] * 1e-3, f),
           cm.abcd_series(1j * w * q['via_nH'] * 1e-9), cm.abcd_shunt(1j * w * 0.10e-12)]
    if place == 'strip':
        els.append(cm.abcd_line(cm.Z_MS, cm.EEFF, min(q['b_mm'], 3.0) * 1e-3, f))
        tail = [cm.abcd_line(cm.Z_MS, cm.EEFF, max(q['b_mm'] - 3.0, 0.5) * 1e-3, f)]
    else:
        els += [cm.abcd_line(cm.Z_MS, cm.EEFF, q['b_mm'] * 1e-3, f), cm.abcd_shunt(1j * w * 0.06e-12),
                cm.abcd_series(1j * w * q['conn_nH'] * 1e-9), cm.abcd_shunt(1j * w * cm.CONN_C * 1e-12),
                cm.abcd_line(50.0, 3.3, dict(PLACES)[place] * 1e-3, f)]
        tail = []
    M = np.eye(2, dtype=complex)
    for e in els: M = M @ e
    return M, tail

def zin_from(M, Zd):
    A, B, C, D = M[0, 0], M[0, 1], M[1, 0], M[1, 1]
    return (D * Zd + B) / (C * Zd + A)

def lmatch(Z, f, Rs=50.0):
    """lossless L-match from source Rs to load Z at f: returns list of candidate (kind, X1, X2)."""
    R, X = Z.real, Z.imag; sols = []
    # shunt at source side, series next to load (R < Rs) : series jXs then shunt jB
    if R < Rs:
        Q = math.sqrt(Rs / R - 1)
        for s in (1, -1):
            Xs = s * Q * R - X; B = s * Q / Rs
            sols.append(('series_load_shunt_src', Xs, B))
    # shunt next to load then series (Y side)
    G = (1 / Z).real; Bl = (1 / Z).imag
    if G > 1 / Rs:
        pass
    Y = 1 / Z; Rp = 1 / Y.real
    if Rp > Rs:
        Q = math.sqrt(Rp / Rs - 1)
        for s in (1, -1):
            Bsh = s * Q / Rp - Y.imag; Xse = s * Q * Rs
            sols.append(('shunt_load_series_src', Bsh, Xse))
    return sols

def elem(x, f, kind, QL=40, QC=200):
    """reactance x (ohm) -> lossy impedance; kind 'X' series reactance, value sign decides L or C."""
    w = 2 * math.pi * f
    return x / QL + 1j * x if x > 0 else -x / QC + 1j * x

def match_abcd(sol, f0, f, QL=40, QC=200):
    """ABCD (source side -> load side) of the lossy L-match, values fixed at f0."""
    kind, a, b = sol; w0 = 2 * math.pi * f0; w = 2 * math.pi * f
    def zser(x0):            # series element of reactance x0 at f0
        if x0 > 0: L = x0 / w0; return w * L / QL + 1j * w * L
        C = -1 / (w0 * x0); return 1 / (w * C * QC) + 1 / (1j * w * C)
    def ysh(b0):             # shunt element of susceptance b0 at f0
        if b0 > 0: C = b0 / w0; return w * C / QC + 1j * w * C
        L = -1 / (w0 * b0); Z = w * L / QL + 1j * w * L; return 1 / Z
    if kind == 'series_load_shunt_src':     # src: shunt b, then series a, then load
        return cm.abcd_shunt(ysh(b)) @ cm.abcd_series(zser(a))
    return cm.abcd_series(zser(b)) @ cm.abcd_shunt(ysh(a))   # src: series b, then shunt a, then load

def rev(M): return np.array([[M[1, 1], M[0, 1]], [M[1, 0], M[0, 0]]])

def deliver(T, Zd, Rs=50.0):
    A, B, C, D = T[0, 0], T[0, 1], T[1, 0], T[1, 1]
    Zin = (A * Zd + B) / (C * Zd + D)
    Vin = Zin / (Zin + Rs); Vl = Vin / (A + B / Zd)
    Pl = abs(Vl) ** 2 * (1 / Zd).real / 2; Pav = 1 / (8 * Rs)
    return Zin, Vl, Pl / Pav

def match_study(p, Zdie, band, place, Rs=50.0):
    f0 = sum(band) / 2
    M0, _ = chain_to(p, f0, place)
    Z0 = zin_from(M0, Zdie(f0))
    best = None
    for sol in lmatch(Z0, f0, Rs):
        worst = 0; spread = []
        for f in np.linspace(band[0], band[1], 9):
            M, _ = chain_to(p, f, place)
            Zin, _, _ = deliver(match_abcd(sol, f0, f) @ rev(M), Zdie(f)); worst = max(worst, abs((Zin - Rs) / (Zin + Rs)))
        for db in (-0.3, 0.3):
            M, _ = chain_to(p, f0, place, db)
            Zin, _, _ = deliver(match_abcd(sol, f0, f0) @ rev(M), Zdie(f0)); spread.append(abs((Zin - Rs) / (Zin + Rs)))
        M, _ = chain_to(p, f0, place)
        _, _, eta = deliver(match_abcd(sol, f0, f0) @ rev(M), Zdie(f0))
        _, _, eta_ch = deliver(rev(M), Zdie(f0))
        r = dict(topology=sol[0], RL_worst_band_dB=round(-20 * math.log10(max(worst, 1e-4)), 1),
                 RL_bond_pm0p3mm_dB=round(-20 * math.log10(max(max(spread), 1e-4)), 1),
                 loss_matched_dB=round(-10 * math.log10(eta), 2), loss_unmatched_dB=round(-10 * math.log10(eta_ch), 2),
                 Zseen_at_plane=f'{Z0.real:.1f}{Z0.imag:+.1f}j')
        if best is None or r['loss_matched_dB'] < best['loss_matched_dB']: best = r
    return best

def lo_pad_study(pI, pQ, place, f=2.45e9, Cpad=1.0e-12, Rbias=5e3):
    """open-circuit 50-ohm source (AC-coupled, no match) -> pad voltage ratio and I/Q phase error from COB asymmetry."""
    out = {}
    for name, p in (('I', pI), ('Q', pQ)):
        res = []
        for db in (-0.3, 0.0, 0.3):
            M, _ = chain_to(p, f, place, db)
            Zd = 1 / (1j * 2 * math.pi * f * Cpad + 1 / Rbias)
            _, Vl, _ = deliver(rev(M), Zd)
            res.append(2 * Vl)          # ratio to the 50-ohm source open-circuit voltage
        out[name] = res
    gI, gQ = out['I'][1], out['Q'][1]
    return dict(pad_over_open_circuit_I=round(abs(gI), 3), pad_over_open_circuit_Q=round(abs(gQ), 3),
                IQ_amp_mismatch_dB=round(20 * math.log10(abs(gQ) / abs(gI)), 2),
                IQ_phase_err_deg=round(math.degrees(cmath.phase(gQ / gI)), 1),
                bond_pm0p3_amp_spread_dB=round(20 * math.log10(max(abs(x) for x in out['I']) / min(abs(x) for x in out['I'])), 2))

def run():
    out = {}
    # RF RX: die = 0.5 pF || 200 ohm per leg (inductorless LNA input + bias); match 50 ohm single-ended per leg
    rx = lambda f: 1 / (1j * 2 * math.pi * f * 0.5e-12 + 1 / 200.0)
    # RF TX: optimum per-leg load 100 ohm (200 ohm diff) behind 1.0 pF pad -> deliver into 50 ohm (balun 2:1 per leg)
    tx = lambda f: 1 / (1j * 2 * math.pi * f * 1.0e-12 + 1 / 100.0)
    band = (2.400e9, 2.4835e9)
    out['rf_rx_match'] = {pl: match_study(geo['RF_RX_P'], rx, band, pl) for pl, _ in PLACES}
    out['rf_tx_match'] = {pl: match_study(geo['RF_TX_P'], tx, band, pl) for pl, _ in PLACES}
    out['lo_ext_unmatched'] = {pl: lo_pad_study(geo['REF_IN'], geo['AUX_CLK_P'], pl) for pl, _ in PLACES if pl != 'strip'}
    out['lo_ext_unmatched_N'] = {pl: lo_pad_study(geo['REF_IN_N'], geo['AUX_CLK_N'], pl) for pl, _ in PLACES if pl != 'strip'}
    # Wired RX return loss at 1.25 GHz vs on-die termination value (differential approx = single-ended leg)
    wr = {}
    for cpad in (2.35, 1.6, 1.0):
        row = {}
        for rt in (40, 45, 50, 55, 60):
            cm.CPAD['wired_rx'] = cpad
            g, h = cm.with_die(geo['WIRE_RX_P'], 1.25e9, 'wired_rx', rt)
            g2, _ = cm.with_die(geo['WIRE_RX_P'], 2.5e9 / 2 * 0.5, 'wired_rx', rt)
            row[f'R{rt}'] = dict(RL_1p25G=round(-20 * math.log10(abs(g)), 1), RL_625M=round(-20 * math.log10(abs(g2)), 1))
        wr[f'Cpad{cpad}pF'] = row
    cm.CPAD['wired_rx'] = 2.35
    out['wired_rx_RL_vs_term'] = wr
    # carrier trace loss contribution at 1.25 GHz (50-ohm, w 0.3 mm FR4 tand 0.02) per placement
    out['carrier_line_IL_dB_1p25G'] = {pl: round(-20 * math.log10(abs(cm.sparams(cm.abcd_line(50.0, 3.3, (L or 0) * 1e-3, 1.25e9))[1])), 3)
                                     for pl, L in PLACES if L}
    return out

if __name__ == '__main__':
    r = run()
    json.dump(r, open('/home/ubuntu/svalbard/scratch/pads-core/spec/placement.json', 'w'), indent=1)
    print(json.dumps(r, indent=1))
