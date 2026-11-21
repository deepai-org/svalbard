#!/usr/bin/env python3
"""hseye.py: USB 2.0 HS eye + return-loss bench for pad_wirepad (esdopt/usb, 2026-11-20, task b7-b).

    hseye.py eye   <model.spice|ideal|ctrl> <tag> <process> <temp> <vdd> [--code N | --termjson J] [--bond nom|max] [--tb-mm 30]
    hseye.py rl    <model.spice|ideal|ideal30> <tag> <process> <temp> <vdd> [same options]

Driver: the pad's own HS current cells (HS_P / HS_N switches, 14 x 20/1 PMOS per leg) biased as stress_safe_usb's mirror (one 20/1
replica diode carrying 17.78 mA / 14 from an ideal DAC; 20 pF HS_PBIAS bypass to VDD as USB-INTEGRATION.md asks), on-die
termination on (TERM_ENABLE, TERM_TRIM = code: --code, or the code closest to 45 ohm on the worse leg at this corner from a tbench.py
json), TERM_VCM 0 V, DVDD = VDD, other controls 0. Gates HS_P / HS_N driven complementary from an ideal 0..VDD source with a
GATE_RAMP linear ramp (default 1.2 ns; stand-in for pt_usb_txdrv, whose HS_STR trim sets the line edge: 857-873 ps at tt on the
published pad, usbdrv-evidence.json; line edges reported against THSR/THSF >= 500 ps). Data: 16 J/K preamble
bits then PRBS7 (127 bits), 480 Mb/s, after 40 ns of HS idle-with-current (HS_N on) for the bias to settle.
Channel per leg (uncoupled): pad -> COB of USB_DP / USB_DN from spec/package-channel-wired.json (bond R + L (nom or max), finger
0.08 pF, F.Cu 86.6 ohm line, via L + 0.10 pF, B.Cu line, land 0.06 pF, connector L + 0.25 pF; element set of
scratch/reviews/pads-core/package-channel-tools/channel_model.py) -> test board (spec/test-board/tb_models.spice inlined:
tb_land, tb_line50 len --tb-mm at f0 = 0.24 GHz, the Nyquist frequency as test-board-models.md section 2 asks) -> USB connector TVS 0.5 pF (B46 maximum) -> receptacle 0.5 nH + 0.3 pF (estimate,
no spec value) = TP (template 1 point) -> cable 45 ohm per leg (90 ohm differential), 5 ns lossless (T line) -> host 45 ohm to ground +
1 pF per leg.  Ideal T lines are used only for the 5 ns cable (ns delay), ladders elsewhere.
eye: d = V(TP_P) - V(TP_N) folded on the mean zero crossing; USB 2.0 Figure 7-13 template 1 (inner hexagon 7.5 / 37.5 / 62.5 / 92.5 %
UI at 0 / 300 / 300 / 0 mV; outer 525 mV in a bit after a transition, 475 mV otherwise: the LIMITS of analog/wired_tx/sim_usbdrv.py),
decoded bits, settled high level (360-440 mV, WR-USB-HSSWING) at TP and at the host, 10-90 % line edges (>= 500 ps).
rl: device side seen from TP with the cable and host removed: AC differential (+-0.5 V from 45 ohm per leg), Zdd and
RL = -20 log|(Zdd - 90)/(Zdd + 90)| at 10 MHz..1.5 GHz; TDR: differential 400 ps (10-90 %) step from 45 ohm per leg, Zdiff(t)
= 90 (1 + rho) / (1 - rho) on the reflected wave, min / max reported (no USB 2.0 numeric RL; WR-USB-RL "none numeric").
Pseudo-DUTs (bench proofs): `ideal` = ideal 17.78 mA current steering per leg (500 ps edges) into ideal 45 ohm per leg at the pad,
ideal 90 ohm channel (the COB and test board replaced by a 0.5 ns 45 ohm T line, no TVS / receptacle, no host C), 0.7 ns edges:
known answer +-400 mV at TP and host, inner margin 100 mV, outer 75 mV, RL > 40 dB; `ideal30` = the same with 30 ohm per leg (RL known answer 14.0 dB, Zdd 60 ohm);
`ctrl` = ideal driver with 5 pF per leg at the pad and 2.5 ns edges (failing control: template 1 must fail).
--cal: B11 per-board amplitude calibration: the bias DAC (ideal IHSREF) is scaled so the static J level at TP is 400 mV (OP with
HS_P on; scale x 0.4 / level, 3 passes); without it the nominal 17.78 mA / 14 reference.
Output: bench/<tag>-hseye.json / -hsrl.json."""
import sys, json, re, math, argparse
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import stress_safe_clamp as s, stress_safe_family_sims as f
from tbench import load, corner
HERE = Path(__file__).resolve().parent
SPEC = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/spec')
UI = 1 / 480e6
GATE_RAMP = 1.2e-9   # default; --gate-ramp
T0 = 40e-9
HS_SCALE = [1.0]   # bias DAC scale (B11 per-board amplitude calibration, --cal)
TPL1 = dict(inner=[(0.075, 0.0), (0.375, 0.300), (0.625, 0.300), (0.925, 0.0)], outer_after=0.525, outer_other=0.475)


def prbs7(n):
    r, out = 0x7f, []
    for _ in range(n):
        b = ((r >> 6) ^ (r >> 5)) & 1; r = ((r << 1) | b) & 0x7f; out.append(b)
    return out


BITS = [1, 0] * 8 + prbs7(127)


def cob(name, pin, bond):
    g = json.loads((SPEC / 'package-channel-wired.json').read_text())['pins'][pin]
    lb = g['bond_wire']['L_nH'][bond]; rb = g['bond_wire']['R_mohm_Al'][bond] * 1e-3
    def line(tag, a, b, mm, nsec, z0=86.6, eeff=3.14):
        td = mm * math.sqrt(eeff) / 299.792458; ls, cs = z0 * td / nsec, td / z0 / nsec * 1e3
        out, p = [], a
        for i in range(nsec):
            q = b if i == nsec - 1 else f'{tag}{i}'
            out += [f'C{tag}{i}a {p} 0 {cs / 2:.5f}p', f'L{tag}{i} {p} {q} {ls:.5f}n', f'C{tag}{i}b {q} 0 {cs / 2:.5f}p']; p = q
        return out
    L = [f'.subckt {name} die conn', f'Rb die n1 {rb:.4f}', f'Lb n1 n2 {lb:.4f}n', 'Cf n2 0 0.08p']
    L += line('f', 'n2', 'n3', g['trace_F_mm'], 1) + [f'Lv n3 n4 {g["via_nH"]:.4f}n', 'Cv n4 0 0.10p']
    L += line('b', 'n4', 'n5', g['trace_B_mm'], 2) + ['Cl n5 0 0.06p', f'Lc n5 conn {g["connector_nH"]:.4f}n', 'Cc conn 0 0.25p', f'.ends {name}']
    return '\n'.join(L) + '\n', dict(bond_nH=lb, bond_ohm=rb, F_mm=g['trace_F_mm'], B_mm=g['trace_B_mm'], via_nH=g['via_nH'], conn_nH=g['connector_nH'])


def tb_text():
    return '\n'.join(l for l in (SPEC / 'test-board/tb_models.spice').read_text().splitlines())


def channel(a, mode):
    """pad nodes PAD_P / PAD_N -> TP_P / TP_N (+ cable + host for the eye)."""
    d, info = '', {}
    if a.dut in ('ideal', 'ideal30', 'ctrl'):
        for x in 'PN': d += f'TPKG_{x} PAD_{x} 0 TP_{x} 0 Z0=45 TD=0.5n\n'
    else:
        tb = tb_text(); d += tb + '\n'
        for x, pin in (('P', 'USB_DP'), ('N', 'USB_DN')):
            t, info[pin] = cob(f'cob_{x}', pin, a.bond); d += t
            d += f'XCOB_{x} PAD_{x} CONN_{x} cob_{x}\nXLAND_{x} CONN_{x} TB1_{x} 0 tb_land\nXLINE_{x} TB1_{x} TB2_{x} 0 tb_line50 len_mm={a.tb_mm} f0_ghz=0.24\n'
            d += f'CTVS_{x} TB2_{x} 0 0.5p\nLREC_{x} TB2_{x} TP_{x} 0.5n\nCREC_{x} TP_{x} 0 0.3p\n'
    if mode == 'eye':
        for x in 'PN': d += f'TCAB_{x} TP_{x} 0 H_{x} 0 Z0=45 TD=5n\nRHOST_{x} H_{x} 0 45\n' + ('' if a.dut == 'ideal' else f'CHOST_{x} H_{x} 0 1p\n')
    return d, info


def gate_pwl(vdd, inv):
    pts = [(0, vdd if inv else 0.)]   # idle-with-current: HS_N on (K-like) before the data
    lvl = lambda b: (vdd if (b ^ inv) else 0.)
    prev = lvl(0)
    pts = [(0, prev)]
    for k, b in enumerate(BITS):
        t = T0 + k * UI; v = lvl(b)
        if v != prev: pts += [(t, prev), (t + GATE_RAMP, v)]; prev = v
    return 'PWL(' + ' '.join(f'{t * 1e9:.4f}n {v:.4g}' for t, v in pts) + ')'


def ideal_pwl(amp, inv, edge):
    prev = (0 ^ inv) * amp; pts = [(0, prev)]
    for k, b in enumerate(BITS):
        t = T0 + k * UI; v = (b ^ inv) * amp
        if v != prev: pts += [(t, prev), (t + edge, v)]; prev = v
    return 'PWL(' + ' '.join(f'{t * 1e9:.4f}n {v:.6g}' for t, v in pts) + ')'


def dut(a, mode, vdd):
    if a.dut in ('ideal', 'ideal30', 'ctrl'):
        r = 30 if a.dut == 'ideal30' else 45; edge = 2.5e-9 if a.dut == 'ctrl' else 0.7e-9
        d = ''
        for x, inv in (('P', 0), ('N', 1)):
            d += f'RT_{x} PAD_{x} 0 {r}\n'
            if mode == 'eye': d += f'I{x} 0 PAD_{x} {ideal_pwl(17.78e-3, inv, edge)}\n'
            if a.dut == 'ctrl': d += f'CX_{x} PAD_{x} 0 5p\n'
        return d, None
    body, cell, ports = load(a.dut)
    code = a.code
    if code is None and a.termjson:
        tj = json.load(open(a.termjson))['term'][f'{a.process}_{a.temp}_{vdd:g}']
        code = min(range(8), key=lambda c: max(abs(tj['r_p'][c] - 45), abs(tj['r_n'][c] - 45)))
    code = code or 0
    d = body + '\n'
    on = {'TERM_ENABLE': vdd, **{f'TERM_TRIM{k}': (vdd if code >> k & 1 else 0) for k in range(3)}}
    for p in ports:
        if p in ('PAD_P', 'PAD_N', 'VDD', 'VSS', 'TERM_VCM'): continue
        if p == 'DVDD': continue
        if p in ('RX_P', 'RX_N'): d += f'CC_{p} {p} 0 50f\nRC_{p} {p} 0 1g\n'; continue
        if p == 'ATB_ESD_RAIL': d += 'RATB ATB_ESD_RAIL 0 10meg\n'; continue
        if p == 'HS_PBIAS':
            d += 'XHSREF HS_PBIAS HS_PBIAS VDD VDD pfet_03v3 w=20u l=1u nf=1 m=1 ad=8.8p as=8.8p pd=40.88u ps=40.88u\n'
            d += f'IHSREF HS_PBIAS 0 {17.78e-3 / 14 * HS_SCALE[0]:.6g}\nCPBIAS HS_PBIAS VDD 20p\n'; continue
        if p in ('HS_P', 'HS_N') and mode == 'eye': d += f'V{p} {p} 0 {gate_pwl(vdd, p == "HS_N")}\n'; continue
        if p in ('HS_P', 'HS_N') and mode == 'cal': d += f'V{p} {p} 0 {vdd if p == "HS_P" else 0}\n'; continue
        d += f'V{p} {p} 0 {on.get(p, 0)}\n'
    d += 'VTERM_VCM TERM_VCM 0 0\nVDVDD DVDD 0 {}\n'.format(vdd) if 'DVDD' in ports else 'VTERM_VCM TERM_VCM 0 0\n'
    d += 'Xpad ' + ' '.join(p for p in ports) + f' {cell}\n'
    return d, code


def cross(t, v, lvl, rising=None):
    s_ = v - lvl; i = np.nonzero(s_[:-1] * s_[1:] < 0)[0]
    if rising is not None: i = i[(s_[i + 1] > s_[i]) == rising]
    return t[i] - s_[i] * (t[i + 1] - t[i]) / (s_[i + 1] - s_[i])


def template1(t, dd_, t0):
    """as analog/wired_tx/sim_usbdrv.py template1 (Figure 7-13), bits 1 .. n-2 of BITS."""
    bits = BITS; k0, k1 = 1, len(bits) - 1
    ref = np.array([2 * bits[min(max(int((x - t0) // UI), 0), len(bits) - 1)] - 1 for x in t])
    lagc = max(range(0, 1200), key=lambda k: float(np.dot(np.interp(t + k * 5e-12, t, dd_), ref)))   # coarse bulk delay (5 ps steps)
    t0 = t0 + lagc * 5e-12
    zc = cross(t, dd_, 0.0); zc = zc[(zc > t0 + k0 * UI - UI / 2) & (zc < t0 + k1 * UI + UI / 2)]
    ph = ((zc - t0 + UI / 2) % UI) - UI / 2; off = float(np.mean(ph)); jit = float(np.ptp(ph))
    xs, ys = zip(*TPL1['inner'])
    sel = (t >= t0 + off + k0 * UI) & (t < t0 + off + k1 * UI); tt, dd = t[sel], dd_[sel]
    idx = np.floor((tt - t0 - off) / UI).astype(int); phs = (tt - t0 - off) / UI - idx
    bound = np.interp(phs, xs, ys); inside = (phs >= xs[0]) & (phs <= xs[-1])
    mi = (np.abs(dd) - bound)[inside]
    b = np.array(bits); after = np.array([b[i] != b[i - 1] for i in idx])
    mo = np.where(after, TPL1['outer_after'], TPL1['outer_other']) - np.abs(dd)
    dec = [int(np.interp(t0 + off + (k + .5) * UI, t, dd_) > 0) for k in range(k0, k1)]
    err = int(sum(x != y for x, y in zip(dec, bits[k0:k1])))
    mid = (phs > .375) & (phs < .625)
    return dict(bulk_delay_ps=round(lagc * 5., 1), clock_offset_ps=round(off * 1e12, 1), crossing_jitter_pp_ps=round(jit * 1e12, 1),
                inner_margin_mv=round(float(mi.min()) * 1e3, 1), inner_violations=int((mi < 0).sum()),
                outer_margin_mv=round(float(mo.min()) * 1e3, 1), outer_violations=int((mo < 0).sum()),
                eye_height_min_mv=round(float(np.abs(dd[mid]).min()) * 1e3, 1), peak_mv=round(float(np.abs(dd).max()) * 1e3, 1),
                bit_errors=err, bits_checked=k1 - k0, ok=bool((mi >= 0).all() and (mo >= 0).all() and err == 0))


def levels_edges(t, d):
    """settled level: mean |d| over 35-65 % UI of bits inside runs of >= 3 equal bits; 10-90 % edges of isolated
    transitions between two settled runs (>= 3 bits each side), by the settled levels."""
    hi, lo, edges = [], [], []
    for k in range(2, len(BITS) - 1):
        if BITS[k] == BITS[k - 1] == BITS[k - 2]:
            m = (t > T0 + (k + .35) * UI) & (t < T0 + (k + .65) * UI)
            (hi if BITS[k] else lo).append(float(d[m].mean()))
    vh, vl = float(np.mean(hi)), float(np.mean(lo))
    for k in range(3, len(BITS) - 3):
        if BITS[k] != BITS[k - 1] and BITS[k - 3] == BITS[k - 2] == BITS[k - 1] and BITS[k] == BITS[k + 1] == BITS[k + 2]:
            m = (t > T0 + (k - .5) * UI) & (t < T0 + (k + 1.5) * UI); tt, vv = t[m], d[m]
            r = BITS[k] == 1; a_, b_ = vl + .1 * (vh - vl), vl + .9 * (vh - vl)
            ca, cb = cross(tt, vv, a_, r), cross(tt, vv, b_, r)
            if len(ca) and len(cb): edges.append(abs(float(cb[0] - ca[0])) if r else abs(float(ca[-1] - cb[0])))
    return vh, vl, edges


def main():
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=('eye', 'rl')); p.add_argument('dut'); p.add_argument('tag')
    p.add_argument('process'); p.add_argument('temp', type=int); p.add_argument('vdd', type=float)
    p.add_argument('--code', type=int); p.add_argument('--termjson'); p.add_argument('--bond', default='nom'); p.add_argument('--tb-mm', type=float, default=30.); p.add_argument('--gate-ramp', type=float); p.add_argument('--cal', action='store_true')
    a = p.parse_args()
    global GATE_RAMP
    if a.gate_ramp: GATE_RAMP = a.gate_ramp
    W = HERE / 'benchrun' / a.tag; W.mkdir(parents=True, exist_ok=True)
    name = f'{a.mode}_{a.process}_{a.temp}_{a.vdd:g}_{a.bond}_{a.tb_mm:g}'
    cal = None
    if a.cal and a.dut not in ('ideal', 'ideal30', 'ctrl'):   # B11: bias DAC scaled so the static J level at TP is 400 mV (OP, 3 passes)
        cal = []
        for it in range(3):
            dd, code = dut(a, 'cal', a.vdd); ch, info = channel(a, 'eye')
            dc_ = corner(f.header() + dd + ch + f'VDD VDD 0 {a.vdd}\nVSS VSS 0 0\n', a.process, a.temp) + s.control(W, name + '_cal', 'op', 'v(TP_P) v(TP_N)')
            y = np.atleast_2d(s.run(W, name + '_cal', dc_, timeout_s=3600)); lvl = float(y[0, 1] - y[0, 2])
            cal.append(dict(scale=round(HS_SCALE[0], 4), static_j_tp_mv=round(lvl * 1e3, 2)))
            HS_SCALE[0] *= 0.400 / lvl
    dd, code = dut(a, a.mode, a.vdd); ch, info = channel(a, a.mode)
    d = f.header() + dd + ch + f'VDD VDD 0 {a.vdd}\nVSS VSS 0 0\n'
    if a.mode == 'eye':
        stop = T0 + len(BITS) * UI + 5e-9
        d = corner(d, a.process, a.temp) + s.control(W, name, f'tran 5p {stop * 1e9:.1f}n 0 5p', 'v(TP_P) v(TP_N) v(H_P) v(H_N) v(PAD_P) v(PAD_N)')
        x = np.atleast_2d(s.run(W, name, d, timeout_s=7200))
        t = x[:, 0]; dtp = x[:, 1] - x[:, 2]; dh = x[:, 3] - x[:, 4]
        tpl = template1(t, dtp, T0); vh, vl, ed = levels_edges(t, dtp)
        lag = 5e-9 + float(np.argmax([np.dot(np.interp(t - 5e-9 - k * 5e-12, t, dtp), dh) for k in range(200)])) * 5e-12   # cable + host delay
        hh, hl, _ = levels_edges(t - lag, dh)
        r = dict(template1_tp=tpl, tp_level_mv=[round(vh * 1e3, 1), round(vl * 1e3, 1)], host_level_mv=[round(hh * 1e3, 1), round(hl * 1e3, 1)], host_lag_ns=round(lag * 1e9, 3),
                 edge_10_90_ps=dict(min=round(min(ed) * 1e12, 1), max=round(max(ed) * 1e12, 1), n=len(ed)) if ed else None,
                 level_ok=bool(360 <= vh * 1e3 <= 440 and -440 <= vl * 1e3 <= -360), edges_ok=bool(ed and min(ed) >= 500e-12))
    else:
        # AC: +-0.5 V from 45 ohm per leg at TP (cable / host absent)
        ac = 'VAP SP 0 DC 0 AC 0.5\nRSP SP TP_P 45\nVAN SN 0 DC 0 AC 0.5 180\nRSN SN TP_N 45\n'
        dac = corner(d + ac, a.process, a.temp) + s.control(W, name + '_ac', 'ac dec 40 10meg 1.5g', 'v(TP_P) v(TP_N) i(VAP) i(VAN)')
        x = np.atleast_2d(s.run(W, name + '_ac', dac, timeout_s=7200))
        fr = x[:, 0]; vp = x[:, 1] + 1j * x[:, 2]; vn = x[:, 3] + 1j * x[:, 4]; ip = -(x[:, 5] + 1j * x[:, 6])
        zdd = (vp - vn) / ip; rho = (zdd - 90) / (zdd + 90); rl = -20 * np.log10(np.abs(rho))
        pick = lambda fq: float(np.interp(fq, fr, rl))
        # TDR: differential 400 ps step, 45 ohm per leg; reflected = V_TP - incident (incident = Vs/2 per leg)
        tdr = 'VTP SP 0 PWL(0 0 1n 0 1.5n 0.25)\nRSP SP TP_P 45\nVTN SN 0 PWL(0 0 1n 0 1.5n -0.25)\nRSN SN TP_N 45\n'
        dt_ = corner(d + tdr, a.process, a.temp) + s.control(W, name + '_tdr', 'tran 2p 8n 0 2p', 'v(TP_P) v(TP_N) v(SP) v(SN)')
        y = np.atleast_2d(s.run(W, name + '_tdr', dt_, timeout_s=7200))
        tt = y[:, 0]; vd = y[:, 1] - y[:, 2]; vinc = (y[:, 3] - y[:, 4]) / 2
        m = tt > 1.6e-9; rho_t = vd[m] / np.maximum(vinc[m], 1e-6) - 1; zt = 90 * (1 + rho_t) / (1 - rho_t)
        r = dict(rl_db={f'{fq / 1e6:g}MHz': round(pick(fq), 2) for fq in (12e6, 60e6, 120e6, 240e6, 400e6, 480e6, 800e6, 1e9, 1.5e9)},
                 rl_min_db_to_480MHz=round(float(rl[fr <= 480e6].min()), 2), rl_min_db_to_1GHz=round(float(rl[fr <= 1e9].min()), 2),
                 zdd_ohm_240MHz=[round(float(np.interp(240e6, fr, zdd.real)), 2), round(float(np.interp(240e6, fr, zdd.imag)), 2)],
                 zdd_ohm_10MHz=round(float(abs(zdd[0])), 2),
                 tdr_zdiff_ohm=dict(min=round(float(zt.min()), 1), max=round(float(zt.max()), 1), final=round(float(zt[-1]), 1),
                                    t_min_ns=round(float(tt[m][zt.argmin()] * 1e9), 3)))
    out = dict(mode=a.mode, dut=a.dut, model_sha256=None if a.dut in ('ideal', 'ideal30', 'ctrl') else s.sha(a.dut), corner=[a.process, a.temp, a.vdd],
               term_code=code, hs_scale=HS_SCALE[0], cal=cal, bond=a.bond, tb_mm=a.tb_mm, gate_ramp_s=GATE_RAMP, channel=info, result=r)
    (HERE / 'bench').mkdir(exist_ok=True)
    (HERE / 'bench' / f'{a.tag}-hs{a.mode}.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(r))
    for q in list(W.glob('*.dat')) + list(W.glob('*.spice')) + list(W.glob('*.log')): q.unlink()


if __name__ == '__main__':
    main()
