#!/usr/bin/env python3
"""Extracted-tank benches for QVCO r5 (qvco_rf_layout.py RF cell, Magic C-only or RC/extresist
extraction) + schematic bias/PRE-tap aux + spiral model + feed R/C + lo_ext load.

Netlist processing (stated in every record):
  * RC: flat extresist netlist (wire R and poly R physical); a poly-gate R > 50 ohm lumped by extresist at
    one end is divided by 3 (distributed gate, as run_qvco_ext.py).  C: C-only flat netlist, explicit gate R
    added per finger: one-side contacted (pair/coupling/PMOS fingers, 5 um) 7.3*W/(3L)+8; both-side
    (switch, tail, header) 7.3*W/(12L)+4.
  * cap_nmos_03v3_b -> behavioural pt_var_nwell (PDK C(V)) with RVW ohm accumulation/well R per finger, plus
    (C only) the finger's poly R 7.3*W/(3L)+8.
  * PESS adds rser ohm in series with every MIM (both plates' paths) and every varactor finger (x17 fingers
    = rser per side), and scales every extracted C by cw_scale.

    python3 run_qvco_r5_ext.py extremes <rfwork> <C|RC> [corners]   -> design.json key ext_<...>
"""
import json
import math
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import timing_flow as tf  # noqa: E402
import run_lcvco as rl  # noqa: E402

ROOT = HERE.parents[4]
SIM = ROOT / 'scratch' / 'lo' / 'r4_qvco2' / 'sim_ext'
RES = ROOT / 'scratch' / 'lo' / 'r4_qvco2' / 'design.json'
RVW = 15.0                     # accumulation-layer / well R per 10x1 um varactor finger (ohm)
PAR = int(os.environ.get('Q5_PAR', '2'))
NBITS = 4

CORNERS = {
    'PESS': dict(corner='ss', temp=32, v=3.15, spiral='pt_spiral_lhi_lowq', cw=1.15, rser=3.0),
    'OPT': dict(corner='ff', temp=22, v=3.35, spiral='pt_spiral_llo', cw=0.90, rser=0.0),
    'TT': dict(corner='tt', temp=27, v=3.3, spiral='pt_spiral', cw=1.0, rser=0.0),
    'SS': dict(corner='ss', temp=32, v=3.15, spiral='pt_spiral', cw=1.0, rser=0.0),
    'FF': dict(corner='ff', temp=22, v=3.35, spiral='pt_spiral', cw=1.0, rser=0.0),
    'SSLQ': dict(corner='ss', temp=32, v=3.15, spiral='pt_spiral_lowq', cw=1.15, rser=3.0),
    'FFLQ': dict(corner='ff', temp=22, v=3.35, spiral='pt_spiral_llo_lowq', cw=0.90, rser=3.0),
    'TTLHI': dict(corner='tt', temp=27, v=3.3, spiral='pt_spiral_lhi', cw=1.0, rser=0.0),
}


def val(v):
    m = {'f': 1e-15, 'p': 1e-12, 'a': 1e-18, 'n': 1e-9, 'u': 1e-6, 'k': 1e3, 'm': 1e-3}
    try:
        return float(v)
    except ValueError:
        return float(v[:-1]) * m[v[-1]]


def processed(rfwork, kind, cw, rser):
    """Return the processed RF-cell netlist file name (in SIM) for extraction kind C/RC."""
    src = Path(rfwork) / ('pt_lc_qvco_rf.rc.spice' if kind == 'RC' else 'pt_lc_qvco_rf.c.spice')
    t = src.read_text()
    t = re.sub(r'\.subckt pt_lc_qvco_rf_\w+', '.subckt pt_lc_qvco_rf', t)
    t = re.sub(r'\.ends pt_lc_qvco_rf_\w+', '.ends', t)
    lines = t.splitlines()
    gates = set()
    if kind == 'RC':
        for ln in lines:
            if re.match(r'X\S* \S+ \S+ \S+ \S+ [np]fet_03v3 ', ln):
                gates.add(ln.split()[2])
            m = re.match(r'X\S* (\S+) (\S+) cap_nmos_03v3_b', ln)
            if m:
                gates.add(m.group(1))
    out = []
    k = 0
    for ln in lines:
        tok = ln.split()
        if not tok:
            out.append(ln)
            continue
        if ln.startswith('C') and len(tok) >= 4:
            tok[3] = f'{val(tok[3]) * cw:.6e}'
            out.append(' '.join(tok))
            continue
        if kind == 'RC' and ln.startswith('R') and len(tok) >= 4 and (tok[1] in gates or tok[2] in gates):
            v = val(tok[3])
            if v > 50:
                tok[3] = f'{v / 3:.3f}'
            out.append(' '.join(tok))
            continue
        m = re.match(r'(X\S*) (\S+) (\S+) (\S+) (\S+) ([np]fet_03v3) (.*)', ln)
        if m and kind == 'C':
            w = val(re.search(r'\bw=(\S+)', ln).group(1)) * 1e6
            l = val(re.search(r'\bl=(\S+)', ln).group(1)) * 1e6
            both = abs(w - 5.0) > 0.01 or m.group(4) in ('B0_I', 'B1_I', 'B2_I', 'B3_I', 'B0_Q', 'B1_Q', 'B2_Q', 'B3_Q')
            rg = 7.3 * w / (12 * l) + 4 if both else 7.3 * w / (3 * l) + 8
            k += 1
            out.append(f'{m.group(1)} {m.group(2)} g{k}_rg {m.group(4)} {m.group(5)} {m.group(6)} {m.group(7)}')
            out.append(f'RGX{k} {m.group(3)} g{k}_rg {rg:.2f}')
            continue
        m = re.match(r'(X\S*) (\S+) (\S+) cap_nmos_03v3_b (.*)', ln)
        if m:
            w = val(re.search(r'c_width=(\S+)', ln).group(1)) * 1e6
            l = val(re.search(r'c_length=(\S+)', ln).group(1)) * 1e6
            rpoly = (7.3 * w / (3 * l) + 8) if kind == 'C' else 0.0
            k += 1
            out.append(f'RVX{k} {m.group(2)} v{k}_m {RVW + rpoly + rser * 17:.2f}')
            out.append(f'{m.group(1)} v{k}_m {m.group(3)} pt_var_nwell AREA={w * l * 1e-12:.4e}')
            continue
        m = re.match(r'(X\S*) (\S+) (\S+) cap_mim_2f0_m4m5_noshield (.*)', ln)
        if m and rser:
            k += 1
            out.append(f'RMX{k} {m.group(2)} m{k}_t {rser / 2:.3f}')
            out.append(f'RMY{k} {m.group(3)} m{k}_b {rser / 2:.3f}')
            out.append(f'{m.group(1)} m{k}_t m{k}_b cap_mim_2f0_m4m5_noshield {m.group(4)}')
            continue
        out.append(ln)
    q = (HERE / 'qvco.spice').read_text()
    i = q.index('.subckt pt_var_nwell')
    out.append(q[i:q.index('.ends', i) + 5])
    for name in ('pt_lc_acinv', 'pt_lc_inv1'):
        i = q.index(f'.subckt {name} ')
        out.append(q[i:q.index('.ends', i) + 5])
    SIM.mkdir(parents=True, exist_ok=True)
    fn = f'rf_{Path(rfwork).name}_{kind}_cw{cw:g}_rs{rser:g}.spice'
    (SIM / fn).write_text('\n'.join(out) + '\n')
    return fn


def ports(rfwork, kind):
    src = Path(rfwork) / ('pt_lc_qvco_rf.rc.spice' if kind == 'RC' else 'pt_lc_qvco_rf.c.spice')
    t = src.read_text()
    m = re.search(r'\.subckt \S+ (.*?)\n(?!\+)', t, re.S)
    return m.group(1).replace('\n+', ' ').split()


def deck(rfwork, kind, cname, code, vt, T=60e-9, rfeed=0.5, cfeed=15.0, cl=230.0, extra=''):
    c = CORNERS[cname]
    fn = processed(rfwork, kind, c['cw'], c['rser'])
    rl.WORK = SIM
    import shutil
    shutil.copy(HERE / 'spiral.spice', SIM / 'spiral.spice')
    sp = rl.spiral_file(c['spiral'])
    pn = ports(rfwork, kind)
    v = c['v']
    conn = {'VSS': '0', 'IP': 'ip', 'IN': 'in', 'QP': 'qp', 'QN': 'qn', 'TSI': 'tsi', 'TSQ': 'tsq',
            'VDDCI': 'vddci', 'VDDCQ': 'vddcq'}
    for n in pn:
        b = re.match(r'(B\d)_[IQ]', n)
        if b:
            conn[n] = b.group(1).lower()
        elif n.startswith('VDD_'):
            conn[n] = 'vdd'
        elif n.startswith('VTUNE'):
            conn[n] = 'vt'
        elif n.startswith('IBIAS'):
            conn[n] = 'ibias'
        elif n.startswith('CMLSEL'):
            conn[n] = 'cmlsel'
    xline = 'XRF ' + ' '.join(conn[n] for n in pn) + ' pt_lc_qvco_rf'
    bits = ''.join(f'VB{k} b{k} 0 {v if (code >> k) & 1 else 0}\n' for k in range(NBITS))
    cf = cfeed * c['cw']
    td = T - 8e-9
    return rl.hdr(c['corner'], c['temp']) + f""".include {sp}
.include {fn}
VDD vdd 0 {v}
VDDB vddb 0 {v}
VCS cmlsel 0 0
VT vt 0 {vt}
IB vdd ibias 10u
XNB ibias ibias 0 0 nfet_03v3 w=2u l=1u
VENB enb 0 0
{bits}{xline}
""" + ''.join(f'RF{n} {n} l{n} {rfeed}\nCF{n} l{n} 0 {cf}f\nCL{n} {n} 0 {cl}f\n' for n in ('ip', 'in', 'qp', 'qn')) + f"""XLI lip lin 0 pt_spiral
XLQ lqp lqn 0 pt_spiral
XBP ip preb enb vddb 0 pt_lc_acinv
XBP2 preb pre vddb 0 pt_lc_inv1
XBD1 in dd1 enb vddb 0 pt_lc_acinv
XBD2 qp dd2 enb vddb 0 pt_lc_acinv
XBD3 qn dd3 enb vddb 0 pt_lc_acinv
CLP pre 0 30f
EDI di 0 ip in 1
EDQ dq 0 qp qn 1
IK ip in pulse(0 200u 0.2n 50p 50p 0.3n 1)
{extra}.tran 1p {T}
.measure tran per trig v(di) val=0 td={td} rise=1 targ v(di) val=0 td={td} rise=11
.measure tran tiq trig v(di) val=0 td={td} rise=1 targ v(dq) val=0 td={td} rise=1
.measure tran dimax max v(di) from={td} to={T}
.measure tran dimax2 max v(di) from={td - 15e-9} to={td - 10e-9}
.measure tran ipavg avg v(ip) from={td} to={T}
.measure tran icore avg i(VDD) from={td} to={T}
.measure tran vdc avg v(vddci) from={td} to={T}
.end
"""


def point(tag, rfwork, kind, cname, code, vt, **kw):
    name = f'{tag}_{kind}_{cname}_b{code}_vt{vt}'
    m = tf.ngspice(SIM, name, deck(rfwork, kind, cname, code, vt, **kw))
    f = 10 / m['per'] if m.get('per') else None
    ph = ((m['tiq'] * f * 360 + 180) % 360 - 180) if f and m.get('tiq') else None
    amp = m.get('dimax') or 0
    return dict(case=name, cname=cname, extraction=kind, band=code, vtune=vt, f_hz=f, q_minus_i_deg=ph,
                diff_peak_v=amp, diff_peak_15ns_earlier_v=m.get('dimax2'), cm_v=m.get('ipavg'),
                vddc_v=m.get('vdc'), i_vdd_ma=-m.get('icore', math.nan) * 1e3,
                oscillates=bool(f and amp > 0.5 and abs(abs(ph or 0) - 90) < 10), errors=m.get('_errors'))


def save(key, d):
    res = json.loads(RES.read_text()) if RES.exists() else {}
    res.setdefault(key, {}).update(d)
    RES.write_text(json.dumps(res, indent=1, default=str) + '\n')


def extremes(rfwork, kind, cnames, tag):
    jobs = []
    for cn in cnames:
        for code, vt in ((0, 3.0), (15, 0.3)):
            jobs.append((cn, code, vt))
    out = {}
    with ThreadPoolExecutor(PAR) as ex:
        for r in ex.map(lambda j: point(tag, rfwork, kind, *j), jobs):
            out[r['case']] = r
            print(f"{r['case']:34s} f={(r['f_hz'] or 0) / 1e9:.4f} amp={r['diff_peak_v']:.3f} QI={r['q_minus_i_deg']} "
                  f"I={r['i_vdd_ma']:.1f}mA vddc={r['vddc_v']} osc={r['oscillates']}", flush=True)
    save(f'ext_{tag}_{kind}', out)
    return out


def pnoise(tag, rfwork, kind, cname, code, vt, T=1.0e-6, nt=2e-12):
    """Transient phase noise, same method as run_qvco_ext.pnoise (fork A): white current noise injected at each
    tank node, i_n^2 = 4kT (1+gamma) G_side with G from the spiral Q at f0 (gamma = 2); zero-crossing jitter of DI
    -> S_phi (Welch) -> L(f) = S_phi/2.  T = 1 us (~2500 cycles, 256-sample segments -> ~10 MHz bins; a 1024-sample
    Welch over the full run gives ~2.5 MHz bins for the 1-3 MHz points).  Device noise models are NOT used and
    flicker up-conversion is not included (stated in the record)."""
    import numpy as np
    from scipy.signal import welch
    k, Tk = 1.380649e-23, 300.15
    c = CORNERS[cname]
    q = {'pt_spiral': 8.5, 'pt_spiral_lhi_lowq': 5.2, 'pt_spiral_llo': 7.8, 'pt_spiral_lowq': 5.0}.get(c['spiral'], 8.5)
    lval = {'pt_spiral': 2.65e-9, 'pt_spiral_lhi_lowq': 2.91e-9, 'pt_spiral_llo': 2.38e-9}.get(c['spiral'], 2.65e-9)
    f0 = 2.45e9
    xl = 2 * math.pi * f0 * lval
    rp = q * xl
    s_i = 4 * k * Tk * (2 / rp) * 3.0
    sigma = math.sqrt(s_i / (2 * nt))
    extra = ''.join(f'INZ{n} {n} 0 dc 0 trnoise({sigma:.4e} {nt:.3e} 0 0)\n' for n in ('ip', 'in', 'qp', 'qn'))
    d = deck(rfwork, kind, cname, code, vt, T=T, extra=extra)
    d = d[:d.index('.tran')] + f""".save v(di)
.control
tran 1p {T} 0 2p
wrdata {tag}_di.txt v(di)
quit
.endc
.end
"""
    tf.ngspice(SIM, tag, d, timeout=200000)
    data = np.loadtxt(SIM / f'{tag}_di.txt')
    tt, x = data[:, 0], data[:, 1]
    s = np.where((x[:-1] < 0) & (x[1:] >= 0))[0]
    tc = tt[s] - x[s] * (tt[s + 1] - tt[s]) / (x[s + 1] - x[s])
    tc = tc[tc > 0.08e-6]
    n = np.arange(len(tc))
    p = np.polyfit(n, tc, 1)
    fosc = 1 / p[0]
    phi = 2 * math.pi * fosc * (tc - np.polyval(p, n))
    rec = dict(case=tag, cname=cname, band=code, vtune=vt, extraction=kind, f_osc_hz=fosc, cycles=len(tc), t_sim_s=T,
               tank_q_assumed=q, injected_a2_hz_per_node=s_i)
    for nps in (256, 1024):
        if len(phi) < nps:
            continue
        fr, sphi = welch(phi - phi.mean(), fs=fosc, nperseg=nps, detrend='linear')
        lf = sphi / 2
        def at(fx):
            i = (fr > fx / 1.35) & (fr < fx * 1.35)
            return float(10 * np.log10(np.mean(lf[i]))) if i.any() else None
        sel = (fr > 4e6) & (fr < 80e6)
        fit = float(10 * np.log10(np.mean(lf[sel] * (fr[sel] / 1e6) ** 2)))
        rec[f'welch{nps}'] = dict(bin_hz=fosc / nps, L_1MHz=at(1e6), L_3MHz=at(3e6), L_20MHz=at(20e6),
                                  L_1MHz_from_1f2_fit_4_80MHz=fit)
    rec['method'] = 'transient + injected white tank/device current noise (fork A method), no device noise models, no flicker'
    print(json.dumps(rec, indent=1), flush=True)
    save('pnoise', {tag: rec})
    return rec


def passive_deck(rfwork, kind, cname, code, vt, rload=300.0):
    """LO11 mode (fork C): EN=0 (tails off), CMLSEL=1 (core header off): the tank is a passive resonant load,
    tank common mode from the lo_ext pre-amp's 300 ohm loads to VDD.  AC current into IP-IN; resonance = peak |Z|."""
    d = deck(rfwork, kind, cname, code, vt)
    d = d.replace('VCS cmlsel 0 0', f"VCS cmlsel 0 {CORNERS[cname]['v']}").replace('IB vdd ibias 10u', 'IB vdd ibias 0')
    # AC analysis aborts on the behavioural varactor (ngspice "doAnalyses: not found"): ring-down instead,
    # 1 mA x 50 ps kick, frequency from the zero crossings 1-6 ns after the kick
    d = d.replace('IK ip in pulse(0 200u 0.2n 50p 50p 0.3n 1)', 'IK ip in pulse(0 1m 0.2n 20p 20p 50p 1)')
    d = d[:d.index('.tran')] + ''.join(f'RL{n} {n} vdd {rload}\n' for n in ('ip', 'in', 'qp', 'qn')) + """.tran 1p 8n
.measure tran per trig v(di) val=0 td=1.5n rise=1 targ v(di) val=0 td=1.5n rise=8
.measure tran a1 max v(di) from=1.5n to=2.5n
.measure tran a2 max v(di) from=5.5n to=6.5n
.end
"""
    return d


def passive(tag, rfwork, kind, cnames, codes, vt):
    out = {}
    jobs = [(c, b) for c in cnames for b in codes]
    def run(j):
        c, b = j
        name = f'{tag}_{kind}_{c}_b{b}_vt{vt}'
        m = tf.ngspice(SIM, name, passive_deck(rfwork, kind, c, b, vt))
        f = 7 / m['per'] if m.get('per') else None
        q = (math.pi * f * 4e-9 / math.log(m['a1'] / m['a2'])) if f and m.get('a1') and m.get('a2') and m['a2'] > 0 else None
        return name, dict(cname=c, band=b, vtune=vt, f_res_hz=f, q_loaded=q, errors=m.get('_errors'))
    with ThreadPoolExecutor(PAR) as ex:
        for name, r in ex.map(run, jobs):
            out[name] = r
            print(name, r['f_res_hz'], r['q_loaded'], flush=True)
    save('passive_' + tag, out)


if __name__ == '__main__':
    if sys.argv[1] == 'pnoise':
        a = sys.argv[2:]
        pnoise(a[0], a[1], a[2], a[3], int(a[4]), float(a[5]), T=float(a[6]) if len(a) > 6 else 1.0e-6)
    elif sys.argv[1] == 'passive':
        a = sys.argv[2:]
        passive(a[0], a[1], a[2], a[3].split(','), [int(x) for x in a[4].split(',')], float(a[5]))
    elif sys.argv[1] == 'extremes':
        extremes(sys.argv[2], sys.argv[3], (sys.argv[4] if len(sys.argv) > 4 else 'PESS,OPT,TT').split(','),
                 sys.argv[5] if len(sys.argv) > 5 else 'x')
