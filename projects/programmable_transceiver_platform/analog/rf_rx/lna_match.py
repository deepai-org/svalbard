"""In-band RF_RX match of pt_lna with a board ladder (fork P).

The LNA input is a series R-C (|X/R| = input Q ~ 27-48 extracted, was ~95-130 for the RC-16e device).
Bode-Fano: a lossless network can hold |S11| <= -10 dB over a fractional band B only if
Q <= pi / (B * ln(1/0.316)); for 2.40-2.4835 GHz (+-5 MHz guard, B = 3.9 %) that is Q <= ~70, and a
practical 3-section ladder needs Q <~ 50.  Bond-wire and board-part tolerances cannot be absorbed on chip
(the pad-side real part is only ~1-2 ohm, so +-0.2 nH of bond = +-3 ohm of reactance per leg); the board
network is therefore fitted per board (B25) and the on-chip ct trim is held near mid-range.

zsweep():    Zin(f) at the pads for every ct code at one corner (one deck).
per_board(): one 6-element ladder (sL pC sL pC sL pC, practical part ranges) and one ct code (4..10) that
             hold S11 over the band for all four temperature/supply points of a process corner.
fixed_bom(): one ladder for every corner, with bond/part tolerance: shows why B25 per-board trim is needed.
"""
import math, random
from pathlib import Path
import numpy as np
import tb
import simlib as S

LO, HI = 2.395e9, 2.4885e9          # band + 5 MHz guard
TOPO = ('sL', 'pC', 'sL', 'pC', 'sL', 'pC')
BOND = 1.5e-9                       # B18 nominal bond L per leg
RANGE = {'L': (0.4e-9, 12e-9), 'C': (0.3e-12, 20e-12)}   # 0402 wire-wound L / C0G C


def zsweep(work, view, corner, f1=2.390e9, f2=2.4935e9, n=208, codes=range(16), rt=False):   # 0.5 MHz grid
    c, t, vdd = corner
    nl = tb.netlist(work, 'lna', view)
    ctrl = ['op']
    for k in codes:
        ctrl += [f'alter Vct{b} dc={vdd if (k >> b) & 1 else 0}' for b in range(4)]
        ctrl += [f'ac lin {n} {f1} {f2}', 'let zin=(v(sp)-v(sn))/(v(e_p)-v(e_n)-v(sp)+v(sn))*100',
                 f'wrdata zs_{{tag}}_{k}.txt real(zin) imag(zin)']
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
{tb._ctl(['en', 'gain_lo', 'byp', 'island_off'], {'en'}, vdd)}
Vs s 0 DC 0 AC 1
Ep e_p 0 s 0 0.5
En e_n 0 s 0 -0.5
Rsp e_p sp 50
Rsn e_n sn 50
Rxp sp rf_in_p 1m
Rxn sn rf_in_n 1m
Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
Rmp rf_out_p vm 50
Rmn rf_out_n vm 50
Rmqp rf_outq_p vm 50
Rmqn rf_outq_n vm 50
Vm vm 0 1.65
{tb._lna_trim(vdd, 0, rt=rt)}
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b pt_lna
{tb.SRC_BOND}
.control
{chr(10).join(ctrl)}
.endc
"""
    tag = f'{view}_{tb._tag(corner)}{"_rt" if rt else ""}'
    tb.run(work, f'zs_{tag}.cir', body.replace('{tag}', tag), corner)
    out = {}
    for k in codes:
        rows = S.read_table(Path(work) / f'zs_{tag}_{k}.txt')
        out[k] = [(r[0], complex(r[1], r[3])) for r in rows]
    return out


def _apply(z, f, net):
    w = 2 * np.pi * f
    for t, v in net:
        if t == 'sL': z = z + 2j * w * v
        elif t == 'sC': z = z + 2 / (1j * w * v)
        elif t == 'pC': z = 1 / (1 / z + 1j * w * v)
        elif t == 'pL': z = 1 / (1 / z + 1 / (1j * w * v))
    return z


def s11_db(net, f, Z):
    zz = _apply(Z, f, net)
    return 20 * np.log10(np.abs((zz - 100) / (zz + 100)))


def _arr(zsets, scen, codes, dl=0.):
    f = np.array([x[0] for x in zsets[scen[0]][codes[0]]])
    sel = (f >= LO) & (f <= HI)
    Z = np.array([[np.array([z for _, z in zsets[s][k]])[sel] + 2j * 2 * np.pi * f[sel] * dl for s in scen] for k in codes])
    return f[sel], Z


def _penalty(net, lb=BOND):
    p = 0.
    for i, (t, v) in enumerate(net):
        lo, hi = RANGE[t[1]]
        if i == 0: lo = lb + 0.1e-9
        if v < lo: p += 20 * math.log(lo / v)
        if v > hi: p += 20 * math.log(v / hi)
    return p


def _opt(cost, starts, seed, lb=BOND):
    from scipy.optimize import minimize
    random.seed(seed)
    rng = {'sL': (1.6e-9, 8e-9), 'pC': (0.5e-12, 15e-12)}
    mk = lambda x: [(t, math.exp(v)) for t, v in zip(TOPO, x)]
    best = None
    for _ in range(starts):
        x0 = [math.log(random.uniform(*rng[t])) for t in TOPO]
        r = minimize(lambda x: cost(mk(x)) + _penalty(mk(x), lb), x0, method='Nelder-Mead',
                     options=dict(maxiter=4000, xatol=1e-5, fatol=1e-5))
        if best is None or r.fun < best[0]:
            best = (r.fun, mk(r.x))
    return best


def per_board(zsets, scen, codes=range(4, 11), starts=40, seed=5, lb=BOND):
    """One network + one code for all scenarios `scen` (the T/V points of one board)."""
    codes = list(codes)
    f, Z = _arr(zsets, scen, codes)
    cost = lambda net: float(np.min(np.max(np.max(s11_db(net, f, Z), axis=2), axis=1)))
    w, net = _opt(cost, starts, seed, lb)
    g = s11_db(net, f, Z)
    k = codes[int(np.argmin(np.max(np.max(g, axis=2), axis=1)))]
    return dict(order='ladder', net=[[t, v] for t, v in net], lb=lb, ct=k, worst_s11_db=round(cost(net), 2))


def fixed_bom(zsets, scen, codes=range(1, 15), bond_tol=0., part_tol=0., starts=12, seed=3):
    """One network for every scenario; per-scenario ct calibration; bond +-bond_tol and parts +-part_tol."""
    codes = list(codes)
    Zs = []
    for dl in ((-bond_tol, 0., bond_tol) if bond_tol else (0.,)):
        f, Z = _arr(zsets, scen, codes, dl)
        Zs.append(Z)
    Z = np.concatenate(Zs, axis=1)
    def var(net):
        if not part_tol: return [net]
        out = [net]
        for a, b in ((1, 1), (-1, -1), (1, -1), (-1, 1)):
            out.append([(t, v * (1 + part_tol * (a if i % 2 else b)) if i else v) for i, (t, v) in enumerate(net)])
        return out
    cost = lambda net: max(float(np.max(np.min(np.max(s11_db(n, f, Z), axis=2), axis=0))) for n in var(net))
    w, net = _opt(cost, starts, seed)
    return dict(net=[[t, v] for t, v in net], bond_tol_h=bond_tol, part_tol=part_tol, worst_s11_db=round(cost(net), 2))


def att_sweep(work, view, corner, match, ct, f=2.442e9, codes=range(64)):
    """Gain / S11 / NF at f for attenuator codes 0..63 (bits att0..att4 = code bits 0..4, gain_lo = bit 5)."""
    c, t, vdd = corner
    nl = tb.netlist(work, 'lna', view)
    names = ['att0', 'att1', 'att2', 'att3', 'att4', 'gain_lo']
    ctrl = ['op']
    for k in codes:
        ctrl += [f'alter V{n} dc={vdd if (k >> b) & 1 else 0}' for b, n in enumerate(names)]
        ctrl += [f'ac lin 2 {f} {f + 1e3}', 'let zin=(v(sp)-v(sn))/(v(e_p)-v(e_n)-v(sp)+v(sn))*100',
                 f'wrdata at_{{tag}}_{k}.txt db((zin-100)/(zin+100)) db(v(rf_out_p)-v(rf_out_n))']
    srcs = '\n'.join(f'V{n} {n} 0 0' for n in names)
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
Ven en 0 {vdd}
Vbyp byp 0 0
Visl island_off 0 0
{srcs}
Vs s 0 DC 0 AC 1
Ep e_p 0 s 0 0.5
En e_n 0 s 0 -0.5
Rsp e_p sp 50
Rsn e_n sn 50
{tb._match_net(match)}Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
Rmp rf_out_p vm 50
Rmn rf_out_n vm 50
Rmqp rf_outq_p vm 50
Rmqn rf_outq_n vm 50
Vm vm 0 1.65
""" + '\n'.join([f'Vct{b} ct{b} 0 {vdd if (ct >> b) & 1 else 0}' for b in range(4)] + ['Vse se 0 0', f'Vrt rt 0 {vdd if match.get("rt") else 0}']) + f"""
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b pt_lna
{tb.SRC_BOND}
.control
{chr(10).join(ctrl)}
.endc
"""
    tag = f'{view}_{tb._tag(corner)}'
    tb.run(work, f'at_{tag}.cir', body.replace('{tag}', tag), corner)
    rows = []
    for k in codes:
        r = S.read_table(Path(work) / f'at_{tag}_{k}.txt')[0]
        rows.append(dict(code=k, s11_db=round(r[1], 2), gain_db=round(r[3], 2)))
    g0 = rows[0]['gain_db']
    att = sorted(set(round(g0 - r['gain_db'], 2) for r in rows))
    steps = [round(b - a, 2) for a, b in zip(att, att[1:])]
    return dict(rows=rows, att_levels_db=att, range_db=att[-1], max_level_gap_db=max(steps),
                binary_order_max_step_db=max(round(rows[k + 1]['gain_db'] - rows[k]['gain_db'], 2) * -1 for k in range(len(rows) - 1)))


def rein_sweep(work, view, corner, ct, f1=0.1e9, f2=12e9, n=120):
    """Stability screen: Re(Zin) at the pads, no board network, 0.1-12 GHz (negative = potential oscillation)."""
    c, t, vdd = corner
    nl = tb.netlist(work, 'lna', view)
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
{tb._ctl(['en', 'gain_lo', 'byp', 'island_off'], {'en'}, vdd)}
Iin sn sp DC 0 AC 1
Rbig sp 0 1e9
Rbig2 sn 0 1e9
Rxp sp rf_in_p 1m
Rxn sn rf_in_n 1m
Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
Rmp rf_out_p vm 50
Rmn rf_out_n vm 50
Rmqp rf_outq_p vm 50
Rmqn rf_outq_n vm 50
Vm vm 0 1.65
{tb._lna_trim(vdd, ct)}
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b pt_lna
{tb.SRC_BOND}
.control
op
ac dec 40 {f1} {f2}
let zr=real(v(sp)-v(sn))
let zmin=minimum(zr)
print zmin
.endc
"""
    tag = f'rein_{view}_{tb._tag(corner)}_ct{ct}'
    log, m = tb.run(work, f'{tag}.cir', body, corner)
    return dict(min_re_zin_ohm=m.get('zmin'))


# ---------------------------------------------------------------- board trimmer network (user decision 2026-11-12)
# Lossy board parts (spec/design-assumptions.md pessimistic): 0402 wire-wound L Q 20, C0G C Q 100, +-5 %;
# trimmer capacitor across the pair: Q 50 at 2.45 GHz, 0.4 nH ESL, 0.1 pF per terminal to ground; bond Q 50.
Q_L, Q_C, Q_T, ESL_T, CTERM_T, Q_BOND = 20., 100., 50., 0.4e-9, 0.1e-12, 50.
TRIM_TOPO = ('sL', 'pC', 'sL', 'pT', 'sL', 'pT')
RT_PENALTY_DB = 1.5   # selection only: rt (Q-spoil) is used only if it improves the worst S11 by more than this   # pad -> source; pT = trimmer across the pair


def _apply_lossy(z, f, net, lb, dlb=0.):
    """net elements (kind, value); the first sL includes the bond lb (+dlb)."""
    w = 2 * np.pi * f
    w0 = 2 * np.pi * 2.44e9            # loss resistances evaluated at 2.44 GHz (as tb._ladder_net)
    for i, (t, v) in enumerate(net):
        if t == 'sL':
            if i == 0:
                lbond = lb + dlb
                z = z + 2 * (1j * w * lbond + w0 * lbond / Q_BOND) + 2 * (1j * w * (v - lb) + w0 * (v - lb) / Q_L)
            else:
                z = z + 2 * (1j * w * v + w0 * v / Q_L)
        elif t == 'pC':
            z = 1 / (1 / z + 1j * w * v + w0 * v / Q_C)
        elif t == 'pT':
            zt = 1 / (1j * w * v) + (1 / (w0 * v * Q_T)) + 1j * w * ESL_T
            z = 1 / (1 / z + 1 / zt + 1j * w * CTERM_T / 2)
    return z


def _s11(z):
    return 20 * np.log10(np.abs((z - 100) / (z + 100)))


def trim_chips(chips, codes=range(4, 11)):
    """chips: {chip: ((zsets rt off, zsets rt on), scenarios)} -> f, {chip: Z array (rt, code, TV, F)} on band+guard."""
    out = {}
    for chip, (zs0, scen) in chips.items():
        arrs = []
        for zs in zs0:
            f, Z = _arr(zs, scen, list(codes))
            arrs.append(Z)
        out[chip] = np.array(arrs)
    return f, out


def _draws(tol=0.05, dlbs=(-0.2e-9, 0., 0.2e-9)):
    pats = [(0, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]   # (L sign, fixed-C sign); trimmers re-tuned anyway
    return [(dl, a * tol, b * tol) for dl in dlbs for a, b in pats]


def trim_best(Z, f, net, lb, ratio, draw, ngrid=5, refine=True):
    """Best trimmer settings (continuous within nominal x ratio^[-1, 1]) + ct + rt for one chip and one tolerance
    draw (bond dl, L tolerance, fixed-C tolerance).  Grid start, then Nelder-Mead on the clipped log trimmer values.
    Returns (worst S11 over (TV, f), setting)."""
    import itertools
    from scipy.optimize import minimize
    dl, eL, eC = draw
    tnom = [v for t, v in net if t == 'pT']

    def build(gs):
        n2, k = [], 0
        for i, (t, v) in enumerate(net):
            if t == 'pT':
                n2.append((t, float(gs[k]))); k += 1
            elif t == 'sL':
                n2.append((t, lb + (v - lb) * (1 + eL) if i == 0 else v * (1 + eL)))
            else:
                n2.append((t, v * (1 + eC)))
        return n2

    def ev(gs):
        g = _s11(_apply_lossy(Z, f, build(gs), lb, dl))      # (rt, code, TV, F)
        w = np.max(np.max(g, axis=3), axis=2)
        ws = w.copy()
        if ws.shape[0] > 1:
            ws[1] += RT_PENALTY_DB          # prefer rt (Q-spoil, costs NF) off unless it buys > RT_PENALTY_DB of S11
        i = np.unravel_index(np.argmin(ws), ws.shape)
        return float(ws[i]), i

    def clip(x):
        return [v * ratio ** float(np.clip(u, -1, 1)) for v, u in zip(tnom, x)]
    best = (99., None)
    for us in itertools.product(*[np.linspace(-1, 1, ngrid)] * len(tnom)):
        w, i = ev(clip(us))
        if w < best[0]:
            best = (w, list(us))
    if refine:
        r = minimize(lambda x: ev(clip(x))[0] + 10 * sum(max(0, abs(u) - 1) for u in x), best[1], method='Nelder-Mead',
                     options=dict(maxiter=150, xatol=1e-3, fatol=1e-3))
        if r.fun < best[0]:
            best = (float(r.fun), list(r.x))
    gs = clip(best[1]); w, i = ev(gs)
    w -= RT_PENALTY_DB if i[0] == 1 else 0.
    return w, dict(trim=[float(x) for x in gs], rt=int(i[0]), ct=int(i[1]) + 4, net=build(gs))


def trim_cost(chips, f, net, lb, ratio, draws, ngrid=3):
    return max(trim_best(Z, f, net, lb, ratio, d, ngrid)[0] for Z in chips.values() for d in draws)


# ---------------------------------------------------------------- stability (review lna2 item 4)
L_BOND_SUP = 1.0e-9     # VDD / VSS bond + package per pin (pessimistic: no island decap credited off chip)


def stability(work, view, corner, ct=7, att=0, mode='active', rt=False, f1=0.1e9, f2=12e9, ppd=40):
    """LNA two-port with RF bond wires (1.5 nH/leg) and VDD/VSS bond L (1 nH each).
    (1) Rollett K / Edwards-Sinsky mu from Z-parameters (port 1 = rf_in diff, port 2 = rf_out (I) diff; the
    Q outputs carry the 50 ohm/leg mixer model); K/mu are invariant to the reference impedance.
    (2) Re(Zin) at the RF pads with the REAL extracted rxmix_i/rxmix_q attached (LO static, both polarities).
    mode: active | bypass.  Returns min mu, min K, min Re(Zin)."""
    c, t, vdd = corner
    nl = tb.netlist(work, 'lna', view)
    ni, nq = tb.netlist(work, 'rxmix_i', 'ext'), tb.netlist(work, 'rxmix_q', 'ext')
    on = {'active': {'en'}, 'bypass': {'byp'}}[mode]
    att_bits = [f'Vatt{k} att{k} 0 {vdd if (att >> k) & 1 else 0}' for k in range(5)]
    ctl = '\n'.join([f'V{n} {n} 0 {vdd if n in on else 0}' for n in ('en', 'byp', 'island_off')] +
                    [f'Vgl gain_lo 0 {vdd if att & 32 else 0}'] + att_bits +
                    [f'Vct{k} ct{k} 0 {vdd if (ct >> k) & 1 else 0}' for k in range(4)] +
                    ['Vse se 0 0', f'Vrt rt 0 {vdd if rt else 0}'])
    common = f""".include {nl}
VDDX vddx 0 {vdd}
Lvdd vddx VDD {L_BOND_SUP}
Lvss vss 0 {L_BOND_SUP}
Vibs vib 0 3.3
Ib vib ibias 10u
{ctl}
Lbp rf_in_p pp 1.5n
Lbn rf_in_n pn 1.5n
Cpp rf_in_p vss 0.5p
Cpn rf_in_n vss 0.5p
Vm vm vss 1.65
"""
    xl = 'X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD vss ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b pt_lna\n' + tb.SRC_BOND
    tag = f'stab_{view}_{tb._tag(corner)}_ct{ct}_a{att}_{mode}{"_rt" if rt else ""}'
    body = common + f"""Rqp rf_outq_p vm 50
Rqn rf_outq_n vm 50
Rbp pp vss 1e9
Rbn pn vss 1e9
Rop rf_out_p vm 1e9
Ron rf_out_n vm 1e9
I1 pn pp DC 0 AC 0
I2 rf_out_n rf_out_p DC 0 AC 0
{xl}
.control
op
alter I1 acmag=1
ac dec {ppd} {f1} {f2}
let z11=v(pp)-v(pn)
let z21=v(rf_out_p)-v(rf_out_n)
wrdata {tag}_a.txt z11 z21
alter I1 acmag=0
alter I2 acmag=1
ac dec {ppd} {f1} {f2}
let z12=v(pp)-v(pn)
let z22=v(rf_out_p)-v(rf_out_n)
wrdata {tag}_b.txt z12 z22
.endc
"""
    tb.run(work, f'{tag}.cir', body, corner)
    a = S.read_table(Path(work) / f'{tag}_a.txt'); b = S.read_table(Path(work) / f'{tag}_b.txt')
    f = np.array([r[0] for r in a])
    z11 = np.array([complex(r[1], r[2]) for r in a]); z21 = np.array([complex(r[4], r[5]) for r in a])
    z12 = np.array([complex(r[1], r[2]) for r in b]); z22 = np.array([complex(r[4], r[5]) for r in b])
    z0 = 100.
    den = (z11 + z0) * (z22 + z0) - z12 * z21
    s11 = ((z11 - z0) * (z22 + z0) - z12 * z21) / den
    s22 = ((z11 + z0) * (z22 - z0) - z12 * z21) / den
    s12 = 2 * z12 * z0 / den; s21 = 2 * z21 * z0 / den
    dlt = s11 * s22 - s12 * s21
    k = (1 - abs(s11) ** 2 - abs(s22) ** 2 + abs(dlt) ** 2) / (2 * abs(s12 * s21) + 1e-30)
    mu = (1 - abs(s11) ** 2) / (abs(s22 - dlt * np.conj(s11)) + abs(s12 * s21) + 1e-30)
    # Re(Zin) with the real mixers, LO static in both polarities
    rein = []
    for lo in (0, 1):
        lp, ln = (vdd, 0) if lo else (0, vdd)
        body2 = common + f""".include {ni}
.include {nq}
Iin pn pp DC 0 AC 1
Rbp pp vss 1e9
Rbn pn vss 1e9
Venm enm 0 {vdd}
{tb._ofs(0, vdd, 'i')}
{tb._ofs(0, vdd, 'q')}
Vlp lp 0 {lp}
Vln ln 0 {ln}
Ib2 vib ib2 10u
Ib3 vib ib3 10u
{xl}
XI rf_out_p rf_out_n lp ln bip bin ib2 enm ofs0i ofs1i ofs2i ofs3i ofs4i ofs_signi island_off avi abi VDD vss pt_rxmix_i
XQ rf_outq_p rf_outq_n lp ln bqp bqn ib3 enm ofs0q ofs1q ofs2q ofs3q ofs4q ofs_signq island_off avq abq VDD vss pt_rxmix_q
.control
op
ac dec {ppd} {f1} {f2}
let zr=real(v(pp)-v(pn))
let zmin=minimum(zr)
print zmin
.endc
"""
        log, m = tb.run(work, f'{tag}_mx{lo}.cir', body2, corner)
        rein.append(m.get('zmin'))
    sel = f > 0
    hi = f >= 1e9
    return dict(min_mu=float(np.min(mu[sel])), f_min_mu=float(f[np.argmin(mu)]), min_k=float(np.min(k[sel])),
                min_mu_above_1ghz=float(np.min(mu[hi])),
                min_re_zin_real_mixer_ohm=min(x for x in rein if x is not None) if any(x is not None for x in rein) else None)


def board_trim_nominal(work, view, corner):
    """BOARD_TRIM tuned (numpy, nominal parts/bond) for one corner -> lossy ladder dict with ct / rt."""
    zz = ({corner: zsweep(work, view, corner)}, {corner: zsweep(work, view, corner, rt=True)})
    f, ch = trim_chips({'c': (zz, [corner])})
    w, st = trim_best(ch['c'], f, [tuple(x) for x in BOARD_TRIM['net']], BOND, BOARD_TRIM['ratio'], (0., 0., 0.), ngrid=13)
    return dict(order='ladder', lossy=True, lb=BOND, net=[list(x) for x in st['net']], ct=st['ct'], rt=st['rt'], worst_s11_db=round(w, 2))


# RC-16i board network (inductively degenerated LNA; extpr tt fit, NOT yet tolerance-closed, see RFR-11): pad -> source,
# series 3.2 nH per leg (incl. 1.5 nH bond), trimmer across the pair (nominal 1.62 pF, x2^[-1,1]), 1.34 nH, 0.31 pF.
BOARD_TRIM = dict(topo=['sL', 'pT', 'sL', 'pC'], ratio=2.0,
                  net=[['sL', 3.2e-9], ['pT', 1.62e-12], ['sL', 1.34e-9], ['pC', 0.312e-12]])
