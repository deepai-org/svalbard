#!/usr/bin/env python3
"""Extracted QVCO benches (r4, LO owner 2026-11-11): the laid-out core (qvco_layout.py, Magic C
extraction, hierarchical) + spiral model, for band extremes and transient-noise phase noise.

Netlist processing of the extracted core (stated in every record):
  * gate R re-inserted per PCell (the PDK models have rgatemod=0; extraction is C-only):
    nf=1 PCells contacted on one side: Rg = 7.3 ohm/sq * W / (3 L) + 8 ohm (poly sheet, contact).
    5 um / 0.28 um pair fingers -> 51.5 ohm (the README's conservative rgf=51 case).
  * cap_nmos_03v3_b instances -> the r3 behavioural varactor (pt_var_nwell, PDK C(V) through its
    charge) with AREA = c_width*c_length and 8 ohm well/accumulation series R per 42.3 um^2 unit
    (4 units per side = the schematic's 2 ohm per side).
  * wiring series R is NOT extracted (C-only): `--rwire` adds an estimated lumped R per tank side
    between the spiral terminal and the core port (default from the drawn trunk/track lengths,
    see wire_r_estimate()).

    python3 run_qvco_ext.py extremes [rwire]     # band 0 / VTUNE 3.0 and band 15 / VTUNE 0.3 at tt, ss lhi_lowq, ff llo
    python3 run_qvco_ext.py pnoise <case>        # transient-noise phase noise, see pnoise()
"""
import json
import math
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import timing_flow as tf  # noqa: E402
import run_lcvco as rl  # noqa: E402

ROOT = HERE.parents[4]
import os  # noqa: E402
CORE = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[1] == 'extremes' else Path(
    os.environ.get('QVCO_CORE', ROOT / 'scratch' / 'lo' / 'r4_layout' / 'core'))
WORK = ROOT / 'scratch' / 'lo' / 'r4_layout' / 'sim'
RES = HERE / 'results_ext.json'
CELL = 'pt_lc_qvco_core'
RSH_POLY, RCONT = 7.3, 8.0
RC = os.environ.get('QVCO_RC', '0') == '1'
RSH_M5, RSH_M4 = 0.040, 0.090


def processed_netlist(core=None):
    core = Path(core or CORE)
    rc = core / 'pt_lc_qvco_flat.rc.spice'
    if RC and rc.exists():
        # flat Magic RC extraction (extresist, analog-image Magic 8.3.678; the canary Magic segfaults):
        # wire and gate-poly R are physical here, so no RGATE is added
        t = rc.read_text().replace('pt_lc_qvco_flat', CELL)
        # extresist lumps each single-finger poly gate (contacted at one end) as its full end-to-end R into the
        # device's gate node; the distributed-gate equivalent is R/3 (Rsh W / 3L).  Gate-feeding R > 50 ohm -> /3.
        gates = {ln.split()[2] for ln in t.splitlines() if re.match(r'X\S* \S+ \S+ \S+ \S+ [np]fet_03v3 ', ln)}
        fixed = []
        for ln in t.splitlines():
            tok = ln.split()
            if ln.startswith('R') and len(tok) >= 4 and (tok[1] in gates or tok[2] in gates):
                try:
                    v = float(tok[3])
                    if v > 50:
                        tok[3] = f'{v / 3:.3f}'
                        ln = ' '.join(tok)
                except ValueError:
                    pass
            fixed.append(ln)
        t = '\n'.join(fixed)
    else:
        t = (core / f'{CELL}.ext.spice').read_text()
    out = []
    sub = None
    for line in t.splitlines():
        m = re.match(r'\.subckt (p_[np]fet_03v3_w(\S+)_l(\S+)) ', line)
        if m:
            sub = (float(m.group(2).replace('p', '.')), float(m.group(3).replace('p', '.')))
        elif line.startswith('.ends'):
            sub = None
        if sub and re.match(r'X\S* \S+ \S+ \S+ \S+ [np]fet_03v3 ', line):
            tok = line.split()
            g = tok[2]
            tok[2] = g + '_rg'
            w, l = sub
            out.append(' '.join(tok))
            out.append(f'RGATE {g} {g}_rg {RSH_POLY * w / (3 * l) + RCONT:.2f}')
            continue
        out.append(line.replace('cap_nmos_03v3_b', 'pt_var_ext'))
    out.append("""
.subckt pt_var_ext G W c_width=1e-6 c_length=1e-6
RS G M 8
XV M W pt_var_nwell AREA={c_width*c_length}
.ends
""")
    # the behavioural varactor from qvco.spice
    q = (HERE / 'qvco.spice').read_text()
    out.append(q[q.index('.subckt pt_var_nwell'):q.index('.ends', q.index('.subckt pt_var_nwell')) + 5])
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'core_ext.spice').write_text('\n'.join(out) + '\n')
    return 'core_ext.spice'


def wire_r_estimate(core=None):
    """Lumped series R per tank side: the M5 port trunk from the top edge down to the lowest
    current-carrying row, distributed load -> R_trunk/2 (feed at one end, loads spread over the top
    half of the span), plus one M4 channel track per row, distributed -> R_track/3, in parallel over
    the rows it serves.  Order-of-magnitude only (C-only extraction)."""
    rep = json.loads((Path(core or CORE) / 'layout-report.json').read_text())
    top = rep['size_um'][1]
    width = rep['size_um'][0]
    rows = rep['rows']
    out = {}
    for n in ('IP', 'IN', 'QP', 'QN'):
        # tank current flows in the top 7 rows (pairs, PMOS, band, fixed caps); trunk span from their lowest track
        lowest = min(r['y_bottom'] for r in rows[-10:])
        span = top - lowest
        r_trunk = RSH_M5 * span / 3.0 / 2
        r_track = RSH_M4 * (width * 0.6) / 3.0 / 3       # each row's track ~0.6 of the width, 3 um wide
        nrow = 8
        out[n] = dict(span_um=span, r_trunk=r_trunk, r_track_each=r_track, r_total=r_trunk + r_track / nrow * 2)
    return out


def deck(corner, temp, v, variant, code, vt, T=30e-9, rwire=0.0, core=None, extra='', cfeed=0.0):
    bits = ''.join(f'VB{k} b{k} 0 {v if (code >> k) & 1 else 0}\n' for k in range(4))
    rl.WORK = WORK
    rl.WORK.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / 'spiral.spice', WORK / 'spiral.spice')
    sp = rl.spiral_file(variant)
    body = (f'.include {sp}\n.include {processed_netlist(core)}\n'
            f'VDD vdd 0 {v}\nVDDB vddb 0 {v}\nVEN en 0 {v}\nVT vt 0 {vt}\nIB vdd ibias 10u\n' + bits +
            'X1 en vt ibias b0 b1 b2 b3 pre ip in qp qn vdd vddb 0 pt_lc_qvco_core\n'
            f'RWIP ip lip {rwire / 2 + 1e-3}\nRWIN in lin {rwire / 2 + 1e-3}\n'
            f'RWQP qp lqp {rwire / 2 + 1e-3}\nRWQN qn lqn {rwire / 2 + 1e-3}\n'
            'XLI lip lin 0 pt_spiral\nXLQ lqp lqn 0 pt_spiral\n'
            + (''.join(f'CFE{n} l{n} 0 {cfeed}f\n' for n in ('ip', 'in', 'qp', 'qn')) if cfeed else '') +
            'EDI di 0 ip in 1\nEDQ dq 0 qp qn 1\nIK ip in pulse(0 200u 0.2n 50p 50p 0.3n 1)\n'
            + ''.join(f'CL{n} {n} 0 190f\n' for n in ('ip', 'in', 'qp', 'qn')) + 'CLP pre 0 30f\n' + extra)
    return rl.hdr(corner, temp) + body


def tb_ext(corner, temp, v, variant, code, vt, rwire=0.0, core=None, cfeed=0.0):
    T = 30e-9
    td = T - 8e-9
    d = deck(corner, temp, v, variant, code, vt, T, rwire, core, cfeed=cfeed) + f""".tran 1p {T}
.measure tran per trig v(di) val=0 td={td} rise=1 targ v(di) val=0 td={td} rise=11
.measure tran tiq trig v(di) val=0 td={td} rise=1 targ v(dq) val=0 td={td} rise=1
.measure tran dimax max v(di) from={td} to={T}
.measure tran ipmin min v(ip) from={td} to={T}
.measure tran ipmax max v(ip) from={td} to={T}
.measure tran ipavg avg v(ip) from={td} to={T}
.measure tran qpmin min v(qp) from={td} to={T}
.measure tran qpmax max v(qp) from={td} to={T}
.measure tran icore avg i(VDD) from={td} to={T}
.end
"""
    return d


def run_point(name, corner, temp, v, variant, code, vt, rwire, core=None, cfeed=0.0):
    m = tf.ngspice(WORK, name, tb_ext(corner, temp, v, variant, code, vt, rwire, core, cfeed))
    f = 10 / m['per'] if m.get('per') else None
    ph = ((m['tiq'] * f * 360 + 180) % 360 - 180) if f and m.get('tiq') else None
    return dict(case=name, corner=corner, temp_c=temp, vdd_v=v, spiral=variant, band=code, vtune_v=vt, rwire_ohm=rwire,
                cfeed_ff=cfeed, f_hz=f, q_minus_i_tank_deg=ph, tank_diff_peak_v=m.get('dimax'), tank_cm_v=m.get('ipavg'),
                tank_ip_v=[m.get('ipmin'), m.get('ipmax')], i_vdd_ma=-m.get('icore', math.nan) * 1e3,
                oscillates=bool(f and (m.get('dimax') or 0) > 0.3), errors=m.get('_errors'),
                netlist=f'extracted core {CORE.name} ' + ('(flat RC extresist: wire + gate poly R, gate R /3 distributed)' if RC else '(C-only) + gate R') + f' + behavioural varactor + {variant} + rwire (feeds)')


def save(key, out):
    res = json.loads(RES.read_text()) if RES.exists() else {}
    res.setdefault(key, {}).update(out)
    RES.write_text(json.dumps(res, indent=1, default=str) + '\n')


EXT = [('tt', 27, 3.3, 'pt_spiral'), ('ss', 32, 3.15, 'pt_spiral_lhi_lowq'), ('ff', 22, 3.35, 'pt_spiral_llo')]


def extremes(rwire, tag, cfeed=0.0, only=None):
    jobs = []
    for c, t, v, sp in EXT:
        for code, vt in ((0, 3.0), (15, 0.3)):
            if only and c not in only:
                continue
            jobs.append((f'{tag}_{c}_b{code}_vt{vt}', c, t, v, sp, code, vt, rwire, None, cfeed))
    out = {}
    with ThreadPoolExecutor(1) as ex:
        for r in ex.map(lambda j: run_point(*j), jobs):
            out[r['case']] = r
            print(r['case'], round((r['f_hz'] or 0) / 1e9, 4), r['tank_diff_peak_v'], r['q_minus_i_tank_deg'], r['i_vdd_ma'], flush=True)
    save('extremes_' + tag, out)


# ---------------------------------------------------------------- phase noise
def pnoise(case, corner, temp, v, variant, code, vt, rwire, T=0.4e-6, nt=2e-12, cfeed=0.0):
    """Transient-noise phase noise (ngspice `.tran` with `trnoise` is not device noise; ngspice
    `.option noise`... is unavailable for transient).  Method: device thermal/flicker noise is NOT
    produced by ngspice transient, so the noise is injected explicitly: the dominant 1/f^2 sources
    of an LC VCO are the tank loss conductance and the active-device channel noise, both white
    current noise across the tank.  Each tank side gets a white noise current with density
    i_n^2 = 4kT (G_tank,side * (1 + gamma)) where G_tank,side is the measured small-signal tank loss
    (1/Rp from the spiral model at f0, same as the Leeson estimate) and gamma = 2 (short channel).
    The time-domain run is long (2.2 us), the zero-crossing times of DI are extracted, and the
    excess phase phi(t) gives S_phi(f) by Welch; L(f) = S_phi/2.  This is a transient,
    large-signal method (it includes the cyclostationary ISF effect of the real waveform and the
    extracted parasitics), but the noise source magnitudes are set by hand from the tank Q, not by
    the device noise models; flicker upconversion is not included."""
    k, Tk = 1.380649e-23, 300.15
    f0 = 2.45e9
    meta = json.loads((HERE / 'spiral.json').read_text()) if (HERE / 'spiral.json').exists() else {}
    # tank parallel R from the variant (Q_eff at 2.45 GHz from spiral.json / README table)
    q = {'pt_spiral': 8.5, 'pt_spiral_lhi_lowq': 5.2, 'pt_spiral_llo': 7.8}.get(variant, 8.5)
    lval = {'pt_spiral': 2.65e-9, 'pt_spiral_lhi_lowq': 2.91e-9, 'pt_spiral_llo': 2.38e-9}.get(variant, 2.65e-9)
    xl = 2 * math.pi * f0 * lval
    q = xl / (xl / q + rwire)          # estimated wiring series R (differential) lowers the tank Q
    rp_diff = q * xl
    g_side = 2 / rp_diff               # each side to AC ground: Rp/2
    gamma = 2.0
    s_i = 4 * k * Tk * g_side * (1 + gamma)            # A^2/Hz single-sided
    # ngspice trnoise: sigma per sample with time step nt: white with two-sided PSD sigma^2 * nt -> single-sided 2 sigma^2 nt
    sigma = math.sqrt(s_i / (2 * nt))
    extra = ''.join(f'INZ{n} {n} 0 dc 0 trnoise({sigma:.4e} {nt:.3e} 0 0)\n' for n in ('ip', 'in', 'qp', 'qn'))
    d = deck(corner, temp, v, variant, code, vt, T, rwire, extra=extra, cfeed=cfeed)
    d += f""".save v(di)
.control
tran 1p {T} 0 2p
wrdata {case}_di.txt v(di)
quit
.endc
.end
"""
    name = case
    tf.ngspice(WORK, name, d, timeout=60000)
    data = np.loadtxt(WORK / f'{case}_di.txt')
    t, x = data[:, 0], data[:, 1]
    # zero crossings (rising), linear interpolation
    s = np.where((x[:-1] < 0) & (x[1:] >= 0))[0]
    tc = t[s] - x[s] * (t[s + 1] - t[s]) / (x[s + 1] - x[s])
    tc = tc[tc > 0.05e-6]
    n = np.arange(len(tc))
    p = np.polyfit(n, tc, 1)
    fosc = 1 / p[0]
    jit = tc - np.polyval(p, n)                  # absolute timing jitter per cycle (s)
    phi = 2 * math.pi * fosc * jit               # excess phase (rad), sampled at fosc
    from scipy.signal import welch
    fr, sphi = welch(phi - phi.mean(), fs=fosc, nperseg=min(len(phi), 256), detrend='linear')
    lf = 10 * np.log10(sphi / 2)                 # one-sided S_phi -> L(f) = S_phi/2
    def at(fx):
        i = (fr > fx / 1.3) & (fr < fx * 1.3)
        return float(10 * np.log10(np.mean(10 ** (lf[i] / 10)))) if i.any() else None
    l1 = at(1e6)
    l20 = at(20e6)
    # 1/f^2 fit over 1-50 MHz -> normalized at 1 MHz
    sel = (fr > 8e6) & (fr < 80e6)
    fit = float(10 * np.log10(np.mean(sphi[sel] / 2 * (fr[sel] / 1e6) ** 2))) if sel.any() else None   # linear average (log-average is biased ~-1.7 dB)
    rec = dict(case=case, corner=corner, temp_c=temp, vdd_v=v, spiral=variant, band=code, vtune_v=vt, rwire_ohm=rwire,
               f_osc_hz=fosc, cycles=len(tc), t_sim_s=T, injected_noise_a2_hz_per_side=s_i, tank_q=q, gamma=gamma,
               L_1MHz_dbc_hz=l1, L_20MHz_dbc_hz=l20, L_1MHz_from_1f2_fit_8_80MHz=fit,
               L_20MHz_from_fit=(fit - 20 * math.log10(20)) if fit is not None else None,
               rms_period_jitter_fs=float(np.std(np.diff(tc)) * 1e15),
               method='transient with explicit white tank/device current noise (see pnoise docstring); resolution bw '
                      f'{fosc / min(len(phi), 256) / 1e6:.1f} MHz; 1 MHz value extrapolated from the 1/f^2 fit over 8-80 MHz')
    np.savetxt(WORK / f'{case}_lf.txt', np.c_[fr, lf])
    print(json.dumps(rec, indent=1), flush=True)
    save('pnoise', {case: rec})
    return rec


if __name__ == '__main__':
    what = sys.argv[1]
    if what == 'extremes':
        rw = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
        cf = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
        only = sys.argv[6].split(',') if len(sys.argv) > 6 else None
        tag = (sys.argv[4] if len(sys.argv) > 4 else 'x') + f'_rw{rw:g}' + (f'_cf{cf:g}' if cf else '')
        extremes(rw, tag, cf, only)
    elif what == 'rwire':
        print(json.dumps(wire_r_estimate(), indent=1))
    elif what == 'pnoise':
        a = sys.argv[2:]
        pnoise(a[0], a[1], int(a[2]), float(a[3]), a[4], int(a[5]), float(a[6]), float(a[7]),
               T=float(a[8]) if len(a) > 8 else 0.4e-6, cfeed=float(a[9]) if len(a) > 9 else 0.0)
