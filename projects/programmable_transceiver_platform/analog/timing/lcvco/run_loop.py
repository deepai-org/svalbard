#!/usr/bin/env python3
"""LO frequency loop (LO13), transistor level: pt_lo_mmd, pt_lo_pfdcp, pt_lo_lf.
Benches (one ngspice process at a time, analog image via timing_flow.ngspice):
  mmd   : divider ratio at f_in / corner, tank-like differential sine on LP/LN
  cp    : UP/DN current and mismatch vs VTUNE, CP output noise PSD
  lock  : closed loop (MMD + PFD/CP + filter, schematic or extracted) with a
          BEHAVIOURAL VCO (B-source phase integrator, r3 Kvco; sine on LP/LN)
Gate resistance: every MOSFET gets a series gate resistor of RG_PER_UM ohm per um
of width (mandate 60-150 ohm per 10 um single-finger device; the layout engine
draws nf=1 with a one-sided gate contact -> upper end, 15 ohm/um).
Raw decks/logs: scratch/lo/r4_loop/sim/.  Results: lcvco/loop_tl.json.
"""
import argparse
import json
import math
import re
import shutil
import sys

import numpy as np
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import timing_flow as tf  # noqa: E402

REPO = tf.REPO
WORK = REPO / 'scratch' / 'lo' / 'r4_loop' / 'sim'
OUT = HERE / 'loop_tl.json'
RG_PER_UM = 15.0


def add_rg(text, per_um=RG_PER_UM):
    out = []
    for line in text.splitlines():
        m = re.match(r'^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+([np]fet_03v3)\b(.*)$', line)
        if m and 'w=' in line:
            w = float(re.search(r'\bw=([0-9.]+)u', line).group(1))
            name, d, g, s, b, mod, rest = m.groups()
            gi = f'{g}_rg{name}'.replace('#', '')
            mult = re.search(r'\bm=(\d+)', rest)
            # m parallel devices each carry their own gate contact: effective Rg / m (r4f)
            out.append(f'R{name}_g {g} {gi} {per_um * w / (int(mult.group(1)) if mult else 1):.1f}')
            if 'ad=' not in rest:   # schematic: add the layout engine's diffusion (nf=1, 0.44 um S/D)
                rest += f' ad={w * 0.44:.3g}p as={w * 0.44:.3g}p pd={2 * (w + 0.44):.3g}u ps={2 * (w + 0.44):.3g}u'
            out.append(f'{name} {d} {gi} {s} {b} {mod}{rest}')
        else:
            out.append(line)
    return '\n'.join(out) + '\n'


def stage(extracted=False):
    WORK.mkdir(parents=True, exist_ok=True)
    tf.stage_sources(WORK, None)
    for f in list(WORK.glob('*.spice')) + list((WORK / 'generated' / 'fast').glob('*.spice')):
        if f.name.startswith(('tb_', 'lk_', 'cp_', 'mmd_')):
            continue
        t = f.read_text()
        if '_rg' not in t:
            f.write_text(add_rg(t))


def header(corner, temp):
    c = {'tt': 'typical'}.get(corner, corner)
    return (tf.header(corner, temp) + f'.lib {tf.MODELS}/sm141064.ngspice mimcap_{c}\n'
            + f'.lib {tf.MODELS}/sm141064.ngspice moscap_{c}\n')   # fork G: C2 is an n-well varactor


def load():
    return json.loads(OUT.read_text()) if OUT.exists() else {}


def save(key, val):
    r = load()
    r[key] = val
    OUT.write_text(json.dumps(r, indent=1, default=float) + '\n')


def nbits(n):
    """pt_lo_mmd r2: total ratio n = 2 x N[5:0] (n even, 32..126)."""
    assert n % 2 == 0 and 32 <= n <= 126, n
    return [((n // 2) >> k) & 1 for k in range(6)]


# ------------------------------------------------------------------- MMD bench
def tb_mmd(inc, f, n, v, amp=0.5, cm=1.7, ncyc=6):
    ic = '' if 'ext' in inc else '.ic v(x1.pqp)=3.0 v(x1.pqn)=2.4\n'   # break the exact schematic symmetry
    T = (ncyc + 1) * n / f + 8e-9
    bits = ''.join(f'VN{k} n{k} 0 {v * b}\n' for k, b in enumerate(nbits(n)))
    body = f"""* MMD ratio bench f={f} N={n}
.include {inc}
VDD vdd 0 {v}
VEN en 0 {v}
VLP lp 0 sin({cm} {amp} {f})
VLN ln 0 sin({cm} {-amp} {f})
{bits}X1 lp ln en n0 n1 n2 n3 n4 n5 fb vdd 0 pt_lo_mmd
CL fb 0 50f
{ic}.tran 2p {T}
.measure tran per trig v(fb) val={v / 2} td={T - (ncyc - 1) * n / f - 1e-9} rise=1 targ v(fb) val={v / 2} td={T - (ncyc - 1) * n / f - 1e-9} rise=4
.measure tran per1 trig v(fb) val={v / 2} td={T - (ncyc - 1) * n / f - 1e-9} rise=1 targ v(fb) val={v / 2} td={T - (ncyc - 1) * n / f - 1e-9} rise=2
.measure tran wid trig v(fb) val={v / 2} td={T - (ncyc - 1) * n / f - 1e-9} rise=1 targ v(fb) val={v / 2} td={T - (ncyc - 1) * n / f - 1e-9} fall=1
.measure tran idd avg i(VDD) from={T / 2} to={T}
"""
    return body


def run_mmd(cases, extracted=False, tag=''):
    stage()
    inc = 'lo_mmd.ext.spice' if extracted else 'lo_mmd.spice'
    res = []
    for (corner, temp, v, f, n, amp, cm) in cases:
        name = f'mmd{tag}_{"x" if extracted else "s"}_{corner}{temp}_{v}_{f / 1e9:.2f}_{n}_{amp}_{cm}'
        m = tf.ngspice(WORK, name, header(corner, temp) + tb_mmd(inc, f, n, v, amp, cm) + '.end\n')
        nmeas = (m.get('per', 0) / 3) * f if m.get('per') else None
        r = dict(corner=corner, temp_c=temp, vdd=v, f_in_hz=f, n_set=n, amp_v=amp, cm_v=cm,
                 n_measured=nmeas, n_single=(m.get('per1', 0) * f if m.get('per1') else None),
                 fb_width_ns=m.get('wid', 0) * 1e9, idd_ma=-m.get('idd', math.nan) * 1e3,
                 netlist='extracted' if extracted else 'schematic', deck=str((WORK / name).relative_to(REPO)) + '.spice')
        r['pass'] = bool(nmeas and abs(nmeas - n) < 0.02 and r['n_single'] and abs(r['n_single'] - n) < 0.05)
        if m['_errors']:
            r['msg'] = m['_errors'][:3]
        print(json.dumps(r), flush=True)
        res.append(r)
    return res


# ------------------------------------------------------------------- PFD/CP benches
VT_GRID = (0.3, 0.5, 0.8, 1.2, 1.65, 2.1, 2.5, 2.7, 2.9, 3.0)


def code_bits(code):
    return [(code >> k) & 1 for k in range(3)]


def tb_cp_dc(inc, v, code, which):
    """Static pump current into an ideal VTUNE source: REF (UP) or FB (DN) steps once
    at 2 ns and the other input never rises, so UP (DN) stays on; VTUNE swept."""
    b = code_bits(code)
    ref = f'pwl(0 0 2n 0 2.05n {v})' if which == 'up' else '0'
    fb = f'pwl(0 0 2n 0 2.05n {v})' if which == 'dn' else '0'
    loop = ' '.join(f'{x}' for x in VT_GRID)
    return f"""* CP static current {which} code {code}
.include {inc}
VDD vdd 0 {v}
IB vdd ib 10u
VREF ref 0 {ref}
VFB fb 0 {fb}
VEN en 0 {v}
VPRE pre 0 pwl(0 {v} 1n {v} 1.05n 0)
VVT vt 0 1.65
X1 ref fb en pre ib vt vdd 0 pt_lo_pfdcp vdd vdd
.control
let k = 0
foreach vv {loop}
  alter VVT dc = $vv
  tran 20p 12n
  meas tran ii avg i(VVT) from=8n to=12n
end
.endc
"""


def run_cp_dc(corners, codes=(0,)):
    stage()
    res = []
    for corner, temp, v in corners:
        for code in codes:
            row = dict(corner=corner, temp_c=temp, vdd=v, code=code, icp_nominal_ua=100 * (code + 1), vtune=list(VT_GRID))
            for which in ('up', 'dn'):
                name = f'cpdc_{which}_{corner}{temp}_{v}_c{code}'
                tf.ngspice(WORK, name, header(corner, temp) + tb_cp_dc('lo_pfdcp.spice', v, code, which) + '.end\n')
                log = (WORK / f'{name}.log').read_text(errors='replace')
                vals = [float(x) for x in re.findall(r'^ii\s*=\s*([-+0-9.eE]+)', log, re.M)]
                if len(vals) == 2 * len(VT_GRID):      # ngspice echoes each meas twice inside .control loops
                    vals = vals[::2]
                assert len(vals) == len(VT_GRID), (name, len(vals))
                row[which + '_ua'] = [abs(x) * 1e6 for x in vals]
            mm = [(u - d) / ((u + d) / 2) * 100 if (u + d) > 0 else None for u, d in zip(row['up_ua'], row['dn_ua'])]
            row['mismatch_pct'] = mm
            inside = [m for vt, m in zip(VT_GRID, mm) if 0.5 <= vt <= 2.7 and m is not None]
            row['max_abs_mismatch_pct_0p5_2p7'] = max(abs(m) for m in inside) if inside else None
            print(json.dumps(row), flush=True)
            res.append(row)
    return res


def noise_netlist():
    """pt_lo_cpnoise: pt_lo_pfdcp with the PFD removed and both pump switches ON into VTUNE
    (the reset-overlap state), steering switches OFF."""
    t = (HERE.parent / 'lo_pfdcp.spice').read_text()
    s = t.index('.subckt pt_lo_pfdcp')
    e = t.index('.ends', s)
    body = t[s:e].replace('.subckt pt_lo_pfdcp', '.subckt pt_lo_cpnoise')
    lines = []
    for ln in body.splitlines():
        if ln.startswith(('XSU ', 'XSD ', 'XRS', 'XU1', 'XD1', 'XD2', 'XKU', 'XKD')):   # PFD + keepers (floating UP/DN)
            continue
        ln = re.sub(r'^(XSU1 \S+) UPB ', r'\1 VSS ', ln)
        ln = re.sub(r'^(XSU2 \S+) UP ', r'\1 VDD ', ln)
        ln = re.sub(r'^(XSD1 \S+) DN ', r'\1 VDD ', ln)
        ln = re.sub(r'^(XSD2 \S+) DNBB ', r'\1 VSS ', ln)
        lines.append(ln)
    return '.include timing_cells.spice\n' + '\n'.join(lines) + '\n.ends\n'


def tb_cp_noise(v, code, vt=1.65, tag='x'):
    b = code_bits(code)
    return f"""* CP output current noise, UP and DN both on, code {code}, VTUNE {vt}
.include cpnoise.spice
VDD vdd 0 {v}
IB vdd ib 10u
VEN en 0 {v}
VPRE pre 0 0
VVT vts 0 {vt} ac 0
LBIG vts vt 1e6
IAC 0 vt dc 0 ac 1
X1 0 0 en pre ib vt vdd 0 pt_lo_cpnoise
.control
ac dec 10 1e3 1e8
wrdata cp_z_{tag}.txt mag(v(vt))
noise v(vt) IAC dec 10 1e3 1e8
setplot noise1
wrdata cp_n_{tag}.txt onoise_spectrum
.endc
"""


def run_cp_noise(corner='tt', temp=27, v=3.3, codes=(0,), t_on=None):
    import numpy as np
    stage()
    (WORK / 'cpnoise.spice').write_text(add_rg(noise_netlist()))
    res = []
    for code in codes:
        name = f'cpnoise_{corner}{temp}_c{code}'
        for f in WORK.glob(f'cp_[zn]_{name}.txt'):
            f.unlink()
        tf.ngspice(WORK, name, header(corner, temp) + tb_cp_noise(v, code, tag=name) + '.end\n')
        z = np.loadtxt(WORK / f'cp_z_{name}.txt')
        n = np.loadtxt(WORK / f'cp_n_{name}.txt')
        f = z[:, 0]
        in2 = (n[:, 1] / z[:, 1]) ** 2
        icp = 100e-6 * (code + 1)
        pick = {fx: float(np.interp(np.log10(fx), np.log10(f), in2)) for fx in (1e4, 1e5, 1e6)}
        row = dict(corner=corner, temp_c=temp, vdd=v, code=code, icp_a=icp, in2_a2_hz_both_on=pick)
        if t_on:
            fom = {fx: 10 * math.log10((2 * math.pi) ** 2 * t_on * val / (2 * icp ** 2)) for fx, val in pick.items()}
            row.update(t_on_s=t_on, fom_dbc_hz_1hz=fom,
                       inband_dbc_hz_fpfd50M_n49={fx: x + 10 * math.log10(50e6) + 20 * math.log10(49) for fx, x in fom.items()})
        print(json.dumps(row), flush=True)
        res.append(row)
    return res


def tb_pfd_pulse(inc, v, code=0, skew=0.0, vt=1.65):
    """REF and FB at 50 MHz with FB delayed by `skew`: UP/DN pulse widths (reset pulse)
    and net charge per cycle into an ideal VTUNE source."""
    b = code_bits(code)
    return f"""* PFD reset pulse
.include {inc}
VDD vdd 0 {v}
IB vdd ib 10u
VREF ref 0 pulse(0 {v} 5n 50p 50p 9.9n 20n)
VFB fb 0 pulse(0 {v} {5e-9 + skew} 50p 50p 9.9n 20n)
VEN en 0 {v}
VPRE pre 0 0
VVT vt 0 {vt}
X1 ref fb en pre ib vt vdd 0 pt_lo_pfdcp vdd vdd
.tran 5p 125n
.measure tran wup trig v(x1.up) val={v / 2} td=84n rise=1 targ v(x1.up) val={v / 2} td=84n fall=1
.measure tran wdn trig v(x1.dn) val={v / 2} td=84n rise=1 targ v(x1.dn) val={v / 2} td=84n fall=1
.measure tran qnet integ i(VVT) from=85n to=125n
"""

# ------------------------------------------------------------------- closed-loop lock
def tb_lock(mmd_inc, cp_inc, v, n=48, fref=50e6, kv=60e6, df0=-2e6, vt0=1.65, code=0, amp=0.5, t_end=6e-6,
            dphi0=0.3, cm=1.7, step=20e-12, behav_div=False, c2node='x'):
    """MMD + PFD/CP + filter (transistor level) with a BEHAVIOURAL VCO: excess phase
    dphi (cycles) integrated on a 1 F node, d(dphi)/dt = kv (VTUNE - vt0) + df0;
    LP/LN = cm +- amp sin(2 pi (n fref t + dphi)).  VTUNE and the filter start at vt0
    (band-search preset hand-off), initial phase offset dphi0 cycles."""
    b = code_bits(code)
    nb = ''.join(f'VN{k} n{k} 0 {v * x}\n' for k, x in enumerate(nbits(n)))
    w = 6.283185307179586
    if behav_div:   # BEHAVIOURAL divider too: FB = rising edge each n VCO cycles (no MMD delay)
        mmd_line, vco_lines = '', ''
        div_line = f'BFB fb 0 v={{ {v / 2} * (1 + tanh(40 * sin({w} * ({fref} * time + v(dphi) / {n})))) }}'
    else:
        mmd_line = f'.include {mmd_inc}'
        vco_lines = (f'BLP lp 0 v={{ {cm} + {amp} * sin({w} * ({n * fref} * time + v(dphi))) }}\n'
                     f'BLN ln 0 v={{ {cm} - {amp} * sin({w} * ({n * fref} * time + v(dphi))) }}')
        div_line = 'XM lp ln en n0 n1 n2 n3 n4 n5 fb vdd 0 pt_lo_mmd'
    return f"""* closed-loop lock, N={n}, Kv={kv / 1e6:g} MHz/V, df0={df0 / 1e6:g} MHz
{mmd_line}
.include {cp_inc}
.include lo_lf.spice
VDD vdd 0 {v}
IB vdd ib 10u
VEN en 0 {v}
VPRE pre 0 0
VREF ref 0 pulse(0 {v} 2n 100p 100p {0.5 / fref - 100e-12} {1 / fref})
{nb}CPH dphi 0 1
GPH 0 dphi cur={{ {kv} * (v(vt) - {vt0}) + {df0} }}
{vco_lines}
{div_line}
XP ref fb en pre ib vtune vdd 0 pt_lo_pfdcp vdd vdd
XL vtune vt 0 pt_lo_lf
.ic v(dphi)={dphi0} v(vtune)={vt0} v(vt)={vt0} v(xl.{c2node})={vt0}
.option interp
.tran {step} {t_end}
.control
run
wrdata lock_out.txt v(ref) v(fb) v(vt) v(dphi)
.endc
"""


def analyse_lock(path, fref=50e6, n=49, kv=60e6, v=3.3):
    import numpy as np
    d = np.loadtxt(path)
    t, ref, fb, vt, ph = d[:, 0], d[:, 1], d[:, 3], d[:, 5], d[:, 7]

    def edges(x):
        i = np.where((x[:-1] < v / 2) & (x[1:] >= v / 2))[0]
        return t[i] + (v / 2 - x[i]) / (x[i + 1] - x[i]) * (t[i + 1] - t[i])
    er, ef = edges(ref), edges(fb)
    # pair each ref edge with the nearest fb edge
    dt = np.array([ef[np.argmin(abs(ef - r))] - r for r in er]) if len(ef) else np.array([])
    out = dict(n_ref_edges=len(er), n_fb_edges=len(ef))
    if len(dt) < 20:
        return out
    tail = dt[-20:]
    spo = float(np.median(tail))
    lo_deg = (dt - spo) * n * fref * 360
    bad = np.where(abs(lo_deg) > 2.0)[0]
    out.update(static_phase_offset_ps=spo * 1e12,
               t_lock_2deg_lo_s=float(er[bad[-1] + 1]) if len(bad) and bad[-1] + 1 < len(er) else None,
               t_lock_10ps_s=(float(er[min(np.where(abs(dt - spo) > 10e-12)[0][-1] + 1, len(er) - 1)]) if np.any(abs(dt - spo) > 10e-12) else 0.0),
               last20_dt_pp_ps=float((tail.max() - tail.min()) * 1e12),
               vtune_final_v=float(vt[-1]))
    s = t > t[-1] - 1e-6
    ts = np.linspace(t[s][0], t[-1], 2 ** 14)
    vi = np.interp(ts, t, vt)
    vi = vi - vi.mean()
    a1 = 2 * abs(np.sum(vi * np.exp(-2j * np.pi * fref * ts))) / len(ts)
    out.update(vtune_ripple_pp_mv=float((vi.max() - vi.min()) * 1e3), vtune_ripple_fref_amp_uv=float(a1 * 1e6),
               ref_spur_dbc_from_ripple=float(20 * np.log10(kv * a1 / (2 * fref))) if a1 > 0 else None,
               freq_err_last1us_hz=float((ph[-1] - ph[s][0]) / (t[-1] - t[s][0])))
    return out


def run_lock(extracted=False, corner='tt', temp=27, v=3.3, tag='', **kw):
    stage()
    mi = 'lo_mmd.ext.spice' if extracted else 'lo_mmd.spice'
    ci = 'lk_pfdcp.spice'
    if extracted:
        src = (HERE.parent / 'generated' / 'lo_pfdcp.ext.spice').read_text()
        lf = (HERE.parent / 'generated' / 'lo_lf.ext.spice').read_text()
        (WORK / 'lk_lf.spice').write_text(tf.uniquify_subckts(lf, 'lf', keep=('pt_lo_lf',)))
        # fork G: the extracted C2 node is not named X; find the net shared with R (X R0 other end) and the C2 units
        body = lf[lf.index('.subckt pt_lo_lf'):]
        body = body[:body.index('.ends')]
        c2n = {ln.split()[1] for ln in body.splitlines() if ln.startswith('XXC2_')}
        assert len(c2n) == 1, c2n
        kw.setdefault('c2node', c2n.pop())
    else:
        strip = lambda s: '\n'.join(l for l in s.splitlines() if not l.lower().startswith('.include'))
        src = '\n'.join(strip((HERE.parent / f).read_text()) for f in ('timing_cells.spice', 'pll.spice', 'lo_pfdcp.spice'))
    (WORK / ci).write_text(add_rg(tf.uniquify_subckts(src, 'pc', keep=('pt_lo_pfdcp',))))
    name = f'lock{tag}_{"x" if extracted else "s"}_{corner}{temp}'
    deck = header(corner, temp) + tb_lock(mi, ci, v, **kw) + '.end\n'
    deck = deck.replace('lock_out.txt', f'{name}.txt')
    if extracted:   # extracted filter too
        deck = deck.replace('.include lo_lf.spice', '.include lk_lf.spice')
    tf.ngspice(WORK, name, deck, timeout=11 * 3600)
    r = analyse_lock(WORK / f'{name}.txt', n=kw.get('n', 48), kv=kw.get('kv', 60e6), v=v)
    r.update(corner=corner, temp_c=temp, vdd=v, netlist='extracted' if extracted else 'schematic', settings=kw,
             vco='BEHAVIOURAL (B-source phase integrator, sine on LP/LN)', deck=str((WORK / name).relative_to(REPO)) + '.spice')
    print(json.dumps(r), flush=True)
    return r

# ------------------------------------------------------------------- loop filter
LF_DEFAULT = dict(r_ohm=22.1e3, c1_f=5.2e-12, c2_f=67e-12)   # LO13 values (loop_design.json)
MIM_F_PER_UM2 = 2e-15
MIM_SIDE_MAX = 50.0


def write_lf(r_ohm=13.09e3, c1_f=6.96e-12, c2_f=347e-12, r3_ohm=10e3, c3_f=15.9e-12, rsq_ohm=1000.0,
             c2_mos=True, mos_f_per_um2=4.6e-15, mos_side=20.0, c2_var=True, var_f_per_um2=3.6e-15, var_side=40.0):
    """Generate lo_lf.spice (round 4): 4th-order passive filter.  CP drives node CP:
    C1 (MIM) on CP, R + C2 from CP (C2 = NMOS inversion cap, gate on X, S/D/B on VSS,
    valid for VTUNE >= ~0.8 V, the lock window), R3 from CP to VT and C3 (MIM) on VT.
    The VCO varactor sees VT."""
    def caps(name, a, b, c):
        area = c / MIM_F_PER_UM2
        n = max(1, math.ceil(area / MIM_SIDE_MAX ** 2))
        side = round(math.sqrt(area / n), 1)
        return ''.join(f'X{name}{k} {a} {b} cap_mim_2f0_m4m5_noshield c_width={side}u c_length={side}u\n' for k in range(n)), n * side * side * MIM_F_PER_UM2

    def res(name, a, b, r):
        nsq = r / rsq_ohm
        nseg = max(1, math.ceil(nsq / 40))
        out = ''
        for k in range(nseg):
            x = a if k == 0 else f'{name}{k}'
            y = b if k == nseg - 1 else f'{name}{k + 1}'
            out += f'X{name}{k} {x} {y} VSS ppolyf_u_1k r_width=1u r_length={nsq / nseg:.2f}u\n'
        return out
    c1, c1a = caps('C1', 'CP', 'VSS', c1_f)
    c3, c3a = caps('C3', 'VT', 'VSS', c3_f)
    if c2_var:   # round 4 fork G: n-well accumulation varactor, gate X / well VSS: valid over VTUNE 0.3-3.0 V
        unit = var_side * var_side * var_f_per_um2   # (tt 3.6-4.0 fF/um2 for 0.3-3.0 V; ff 0.3 V 3.3; ss 4.0-4.4)
        m = math.ceil(c2_f / unit)
        c2 = ''.join(f'XC2_{k} X VSS cap_nmos_03v3_b c_width={var_side}u c_length={var_side}u\n' for k in range(m))
        c2a = m * unit
    elif c2_mos:
        unit = mos_side * mos_side * mos_f_per_um2
        m = math.ceil(c2_f / unit)
        c2 = ''.join(f'XC2_{k} VSS X VSS VSS nfet_03v3 w={mos_side}u l={mos_side}u\n' for k in range(m))
        c2a = m * unit
    else:
        c2, c2a = caps('C2', 'X', 'VSS', c2_f)
    c2desc = ('n-well accumulation varactor (gate X, well VSS), design ' + str(var_f_per_um2 * 1e15) + ' fF/um2, valid VTUNE 0.3-3.0 V') if c2_var else (('NMOS inversion cap, design value ' + str(mos_f_per_um2 * 1e15) + ' fF/um2') if c2_mos else 'MIM')
    text = (f'* SPDX-License-Identifier: Apache-2.0\n* pt_lo_lf: RF-LO loop filter (round 4, 4th order), generated by lcvco/run_loop.py write_lf\n'
            f'* R = {r_ohm / 1e3:.2f} k, C1 = {c1a * 1e12:.2f} pF MIM, C2 = {c2a * 1e12:.1f} pF '
            f'({c2desc}), '
            f'R3 = {r3_ohm / 1e3:.2f} k, C3 = {c3a * 1e12:.2f} pF MIM (pole {1 / (2 * math.pi * r3_ohm * c3a) / 1e6:.2f} MHz)\n'
            f'.subckt pt_lo_lf CP VT VSS\n{c1}{res("R", "CP", "X", r_ohm)}{c2}{res("R3_", "CP", "VT", r3_ohm)}{c3}.ends\n')
    (HERE.parent / 'lo_lf.spice').write_text(text)
    return dict(r_ohm=r_ohm, c1_f=c1a, c2_f=c2a, r3_ohm=r3_ohm, c3_f=c3a, c2_mos=c2_mos and not c2_var, c2_var=c2_var)



# ------------------------------------------------------------------- r5 lock ladder (audit lo-lock-sim-audit.md)
# One directory per run (scratch/lo/r5_ladder/<run>/) with copied includes + md5; pass limits fixed in
# LADDER_LIMITS before any run; start from the band-search hand-off (VTUNE preset, frequency offset df0,
# dphi0 = 0); reltol 1e-4; VCO excess phase dphi in cycles starts at 0.
LADDER = REPO / 'scratch' / 'lo' / 'r5_ladder'
LF_R4 = dict(r_ohm=13.09e3, c1_f=6.96e-12, c2_f=351e-12, r3_ohm=10e3, c3_f=15.9e-12)
LADDER_LIMITS = dict(               # fixed 2026-11-11 before the first ladder run; do not edit after results
    t_lock_max_s=50e-6,             # loop settling to 2 deg LO (IX-5 75 us budget incl. ~25 us band search)
    hold_window_s=20e-6,            # last 20 us = hold window, split in two 10 us halves
    lo_phase_err_deg=2.0,           # |FB-REF - spo| x N fref x 360 over the hold window
    spo_drift_ps=1.0,               # spo(half 1) - spo(half 2)
    spo_abs_max_ps=1000.0,          # static phase offset bound
    f_err_max_hz=1e3,               # VCO frequency vs N fref over the hold window (from dphi)
    vtune_window_v=(0.8, 2.5),      # CP mismatch-valid window (r2 extracted)
    step_match_rel=0.05)            # rung-1 small step: |sim - analytic| peak and rms <= 5 % of analytic peak


def icp_lo18(kv):
    """LO18: Icp = 100 uA x min(1, 60 MHz/V / Kv), realised as 25 uA x (1 + ICP0 + 2 ICP1); nearest code."""
    want = 100e-6 * min(1.0, 60e6 / kv) if kv > 0 else 100e-6
    k = min(range(4), key=lambda k: abs(25e-6 * (k + 1) - want))
    return 25e-6 * (k + 1), k


def z_lf(s, f):
    """Impedance CP->(VTUNE at C3) transfer: Vvt/Icp for the 4th-order filter (C1 // (R+C2)) then R3-C3."""
    z1 = 1 / (s * f['c1_f'] + 1 / (f['r_ohm'] + 1 / (s * f['c2_f'])))
    zc3 = 1 / (s * f['c3_f'])
    zin = 1 / (1 / z1 + 1 / (f['r3_ohm'] + zc3))   # CP node impedance
    return zin * zc3 / (f['r3_ohm'] + zc3)


def g_open(f_hz, lf, icp, kv, n):
    s = 2j * math.pi * np.asarray(f_hz)
    return icp * z_lf(s, lf) * kv / (n * s)        # PFD Icp/2pi x 2pi Kv/s / N (phase in cycles)


def loop_margins(lf, icp, kv, n):
    f = np.logspace(3, 8, 40000)
    g = g_open(f, lf, icp, kv, n)
    i = np.argmin(abs(abs(g) - 1))
    return float(f[i]), float(180 + math.degrees(np.angle(g[i])))


def step_analytic(t, lf, icp, kv, n, df):
    """Linear (averaged-PFD) known answer: VCO excess phase phi (cycles) after the loop, locked at t=0, sees a
    VCO frequency step df.  States vCP, vX, vVT, phi; i_cp = -Icp phi / N; exact discretisation (expm)."""
    from scipy.linalg import expm
    c1, c2, c3, r, r3 = lf['c1_f'], lf['c2_f'], lf['c3_f'], lf['r_ohm'], lf['r3_ohm']
    A = np.array([[-1 / (r * c1) - 1 / (r3 * c1), 1 / (r * c1), 1 / (r3 * c1), -icp / (n * c1)],
                  [1 / (r * c2), -1 / (r * c2), 0, 0],
                  [1 / (r3 * c3), 0, -1 / (r3 * c3), 0],
                  [0, 0, kv, 0]])
    B = np.array([0, 0, 0, df])
    h = 2e-9
    M = np.zeros((5, 5)); M[:4, :4] = A * h; M[:4, 4] = B * h
    E = expm(M)
    x = np.zeros(4); tt = np.arange(0, t[-1] + h, h); ph = np.empty(len(tt))
    for k in range(len(tt)):
        ph[k] = x[3]
        x = E[:4, :4] @ x + E[:4, 4]
    return np.interp(t, tt, ph)


def hop4(lf, icp, kv, n, df0, fref=50e6, t_end=80e-6, m_div=None):
    """Cycle-accurate reference (cf. loop_design.hop_sim, extended to the r4 4th-order filter): per reference
    cycle, the tri-state PFD charge Icp x |FB-REF| (clipped at 0.95 Tref, sign kept, no slip), then exact
    linear free evolution (expm) of C1/R-C2/R3-C3 + VCO phase.  Returns t_lock (2 deg LO, last violation)."""
    from scipy.linalg import expm
    m_div = m_div or n
    c1, c2, c3, r, r3 = lf['c1_f'], lf['c2_f'], lf['c3_f'], lf['r_ohm'], lf['r3_ohm']
    tr = 1 / fref
    A = np.zeros((5, 5))
    A[:3, :3] = [[-1 / (r * c1) - 1 / (r3 * c1), 1 / (r * c1), 1 / (r3 * c1)], [1 / (r * c2), -1 / (r * c2), 0],
                 [1 / (r3 * c3), 0, -1 / (r3 * c3)]]
    A[3, 2] = kv; A[3, 4] = 1.0          # phi' = kv vvt + (df0 + n fref - m fref)
    E = expm(A * tr)
    x = np.array([0, 0, 0, 0, df0 + (n - m_div) * fref])
    err = []
    for k in range(int(t_end / tr)):
        dt_e = -(x[3] / m_div) * tr                   # FB late (phi<0) -> UP
        w = min(abs(dt_e), 0.95 * tr)
        x[0] += (icp if dt_e > 0 else -icp) * w / c1
        x = E @ x
        err.append(-(x[3] / m_div) * tr * n * fref * 360)
    e = np.array(err)
    final = np.mean(e[-200:])
    bad = np.where(abs(e - final) > 2.0)[0]
    return dict(t_lock_2deg_s=float((bad[-1] + 1) * tr) if len(bad) else 0.0, vt_final_dv=float(x[2]),
                f_err_final_hz=float(kv * x[2] + x[4]))


def md5(p):
    import hashlib
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def tb_ladder(v, n, m_div, fref, kv, df0, vt0, icp, t_end, pfd='ideal', lf='ideal', lfv=None, en=True,
              t_rst=150e-12, icp_bits=(1, 1), tmax=None, df_step_at=None):
    """Ladder deck.  pfd 'ideal' = XSPICE tri-state PFD (d_dff + reset AND with t_rst) + ideal +-Icp sources;
    pfd 'x' = extracted pt_lo_pfdcp (lk_pfdcp.spice) with ICP code.  lf 'ideal' = ideal R/C1/C2/R3/C3 (lfv),
    'x' = extracted pt_lo_lf (lk_lf.spice).  VCO behavioural: f = n fref + kv (VT - vt0) + df0;
    divider (behavioural) divides by m_div (m_div != n = wrong-N must-fail case)."""
    w = 6.283185307179586
    lfv = lfv or LF_R4
    out = [f'* lock ladder: N={n} M={m_div} Kv={kv / 1e6:g} MHz/V df0={df0 / 1e6:g} MHz Icp={icp * 1e6:g} uA pfd={pfd} lf={lf}',
           f'VDD vdd 0 {v}', f'VREF ref 0 pulse(0 {v} 2n 50p 50p {0.5 / fref - 50e-12} {1 / fref})',
           'CPH dphi 0 1', f'GPH 0 dphi cur={{ {kv} * (v(vt) - {vt0}) + {df0} }}',
           f'BFB fb 0 v={{ {v / 2} * (1 + tanh(200 * sin({w} * ({fref * n / m_div} * (time - 2.025e-9) + v(dphi) / {m_div})))) }}']
    if pfd == 'ideal':
        out += ['AAD [ref fb] [dref dfb] adcb', '.model adcb adc_bridge(in_low=1.0 in_high=2.0)',
                'ADU one dref rst upd dmy1 dff', 'ADD one dfb rst dnd dmy2 dff', 'AON one onesrc',
                '.model onesrc d_pullup', '.model dff d_dff(clk_delay=1e-12 reset_delay=1e-12 set_delay=1e-12)',
                'ADS nset zsrc', '.model zsrc d_pulldown',
                'AAND [upd dnd] rst andg', f'.model andg d_and(rise_delay={t_rst} fall_delay=1e-12)',
                'ADA [upd dnd] [upa dna] dacb', '.model dacb dac_bridge(out_low=0 out_high=1 t_rise=1e-12 t_fall=1e-12)',
                f'GCP 0 vtune cur={{ {icp if en else 0} * (v(upa) - v(dna)) }}']
        # d_dff ports: data clk set reset out nout -> fix order below
        out[out.index('ADU one dref rst upd dmy1 dff')] = 'ADU one dref nset rst upd dmy1 dff'
        out[out.index('ADD one dfb rst dnd dmy2 dff')] = 'ADD one dfb nset rst dnd dmy2 dff'
    else:
        out += ['.include lk_pfdcp.spice', 'IB vdd ib 10u', f'VEN en 0 {v if en else 0}', 'VPRE pre 0 0',
                f'VI0 icp0 0 {v * icp_bits[0]}', f'VI1 icp1 0 {v * icp_bits[1]}',
                'XP ref fb en pre ib vtune vdd 0 icp0 icp1 pt_lo_pfdcp']
    if lf == 'ideal':
        f = lfv
        out += [f'C1 vtune 0 {f["c1_f"]}', f'R1 vtune x {f["r_ohm"]}', f'C2 x 0 {f["c2_f"]}',
                f'R3 vtune vt {f["r3_ohm"]}', f'C3 vt 0 {f["c3_f"]}']
        c2node = 'x'
    else:
        out += ['.include lk_lf.spice', 'XL vtune vt 0 pt_lo_lf']
        c2node = None
    ic = f'.ic v(dphi)=0 v(vtune)={vt0} v(vt)={vt0}' + (f' v({c2node})={vt0}' if c2node else '')
    out += [ic, '.option reltol=1e-4 interp' if False else '.option reltol=1e-4',
            '.save v(ref) v(fb) v(vt) v(dphi)', f'.tran 10p {t_end} 0 {tmax or 10e-12}',
            '.control', 'set filetype=binary', 'run', 'write lad.raw v(ref) v(fb) v(vt) v(dphi)', '.endc']
    return '\n'.join(out) + '\n'


def read_raw(path):
    """ngspice binary rawfile (real transient): returns dict name -> array."""
    b = Path(path).read_bytes()
    k = b.index(b'Binary:\n') + 8
    hdr = b[:k].decode(errors='replace').splitlines()
    nv = int([l for l in hdr if l.startswith('No. Variables')][0].split(':')[1])
    names = []
    i = hdr.index('Variables:')
    for l in hdr[i + 1:i + 1 + nv]:
        names.append(l.split()[1].lower())
    d = np.frombuffer(b[k:], dtype='<f8')
    d = d[:len(d) // nv * nv].reshape(-1, nv)
    return {nm: d[:, j] for j, nm in enumerate(names)}


def analyse_ladder(path, fref, n, v, t_end, lim=LADDER_LIMITS, analytic=None):
    w = read_raw(path)
    t, ref, fb, vt, ph = w['time'], w['v(ref)'], w['v(fb)'], w['v(vt)'], w['v(dphi)']

    def edges(x):
        i = np.where((x[:-1] < v / 2) & (x[1:] >= v / 2))[0]
        return t[i] + (v / 2 - x[i]) / (x[i + 1] - x[i]) * (t[i + 1] - t[i])
    er, ef = edges(ref), edges(fb)
    r = dict(n_ref_edges=int(len(er)), n_fb_edges=int(len(ef)), dphi_max_abs_cyc=float(abs(ph).max()),
             vtune_final_v=float(vt[-1]), vtune_min_v=float(vt.min()), vtune_max_v=float(vt.max()))
    h0, hm = t_end - lim['hold_window_s'], t_end - lim['hold_window_s'] / 2
    halves = [(h0, hm), (hm, t_end)]
    cnt = [(int(((er >= a) & (er < b)).sum()), int(((ef >= a) & (ef < b)).sum())) for a, b in halves]
    r['hold_edge_counts_ref_fb'] = cnt
    ok = dict(edge_counts=all(a == b and a > 0 for a, b in cnt))
    # pair each ref edge with nearest fb edge
    dt = np.array([ef[np.argmin(abs(ef - x))] - x for x in er]) if len(ef) else np.full(len(er), np.nan)
    spos = [float(np.median(dt[(er >= a) & (er < b)])) if ((er >= a) & (er < b)).any() else math.nan for a, b in halves]
    spo = float(np.nanmean(spos))
    deg = (dt - spo) * n * fref * 360
    hold = er >= h0
    r.update(spo_ps=spo * 1e12, spo_halves_ps=[x * 1e12 for x in spos],
             hold_phase_err_max_deg=float(np.nanmax(abs(deg[hold]))) if hold.any() else math.nan)
    bad = np.where(~(abs(deg) <= lim['lo_phase_err_deg']))[0]
    r['t_lock_2deg_s'] = (float(er[bad[-1] + 1]) if bad[-1] + 1 < len(er) else None) if len(bad) else float(er[0])
    s = t >= h0
    r['f_err_hold_hz'] = float((ph[-1] - ph[s][0]) / (t[-1] - t[s][0]))
    ok.update(phase_err=r['hold_phase_err_max_deg'] <= lim['lo_phase_err_deg'],
              spo_drift=abs(spos[0] - spos[1]) * 1e12 <= lim['spo_drift_ps'],
              spo_abs=abs(spo) * 1e12 <= lim['spo_abs_max_ps'],
              f_err=abs(r['f_err_hold_hz']) <= lim['f_err_max_hz'],
              vtune_window=lim['vtune_window_v'][0] <= r['vtune_final_v'] <= lim['vtune_window_v'][1],
              t_lock=r['t_lock_2deg_s'] is not None and r['t_lock_2deg_s'] <= lim['t_lock_max_s'])
    if analytic is not None:     # rung-1 small-step comparison on dphi (cycles)
        a = step_analytic(t, *analytic)
        pk = float(abs(a).max())
        r.update(step_sim_peak_cyc=float(abs(ph).max()), step_analytic_peak_cyc=pk,
                 step_t_peak_sim_s=float(t[np.argmax(abs(ph))]), step_t_peak_analytic_s=float(t[np.argmax(abs(a))]),
                 step_err_peak_rel=float(abs(abs(ph).max() - pk) / pk),
                 step_err_rms_rel=float(np.sqrt(np.mean((np.interp(np.linspace(0, t_end, 4000), t, ph)
                                                        - np.interp(np.linspace(0, t_end, 4000), t, a)) ** 2)) / pk))
        ok['step_match'] = r['step_err_peak_rel'] <= lim['step_match_rel'] and r['step_err_rms_rel'] <= lim['step_match_rel']
    r['checks'] = ok
    r['pass'] = bool(all(ok.values()))
    return r


def run_ladder(run, rung, corner='tt', temp=27, v=3.3, n=49, m_div=None, fref=50e6, kv=60e6, df0=-30e6, vt0=1.65,
               icp=None, t_end=80e-6, pfd='ideal', lf='ideal', lfv=None, en=True, expect='pass', small_step=False,
               tmax=None):
    import numpy  # noqa
    wd = LADDER / run
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    m_div = m_div or n
    code = None
    if icp is None:
        icp, code = icp_lo18(kv) if kv > 0 else (100e-6, 3)
    else:
        code = round(icp / 25e-6) - 1
    bits = (code & 1, (code >> 1) & 1)
    inc = {}
    if pfd == 'x':
        src = (HERE.parent / 'generated' / 'lo_pfdcp.ext.spice').read_text()
        (wd / 'lk_pfdcp.spice').write_text(add_rg(tf.uniquify_subckts(src, 'pc', keep=('pt_lo_pfdcp',))))
        inc['generated/lo_pfdcp.ext.spice'] = md5(HERE.parent / 'generated' / 'lo_pfdcp.ext.spice')
    if lf == 'x':
        src = (HERE.parent / 'generated' / 'lo_lf.ext.spice').read_text()
        txt = tf.uniquify_subckts(src, 'lf', keep=('pt_lo_lf',))
        # C2 (cap_nmos_03v3_b units, PDK C(V) = k (c1 + c2 tanh(c3 V + c4))) -> ONE element i = C(V) dV/dt
        # (dV/dt from a 1 F copy cap), same PDK constants and corner factor.  The 61 voltage-dependent
        # 'c=' capacitors stall ngspice (gear, reltol 1e-4) at ~61-68 us (two identical stalls, r2 first attempt).
        lines = txt.splitlines()
        c2 = [l for l in lines if l.startswith('XXC2_')]
        assert c2 and len({l.split()[1] for l in c2}) == 1, 'C2 units'
        node = c2[0].split()[1]
        w_um, l_um = (float(x) for x in re.search(r'_w(\d+)_l(\d+)', c2[0].split()[-1]).groups())
        k = len(c2) * w_um * l_um * 1e-12
        cv = (f'{k:.6g}*cap_nmos_03v3_b_corner*(0.002458 + 0.001533*tanh(1.515152*v({node},VSS)+0.560606))')
        out, inside = [], False
        for l in lines:
            if l.startswith('.subckt pt_lo_lf'):
                inside = True
            if inside and l.startswith('XXC2_'):
                continue
            if inside and l.startswith('.ends'):
                out += [f'EC2C c2cp VSS {node} VSS 1', 'VC2M c2cp c2cm 0', 'CC2U c2cm VSS 1',
                        f'BC2Q {node} VSS i={{ {cv} * i(VC2M) }}']   # i = C(V) dV/dt (PDK c= form)
                inside = False
            out.append(l)
        (wd / 'lk_lf.spice').write_text('\n'.join(out) + '\n')
        inc['generated/lo_lf.ext.spice'] = md5(HERE.parent / 'generated' / 'lo_lf.ext.spice')
        inc['c2_model'] = f'{len(c2)} x cap_nmos_03v3_b w{w_um:g} l{l_um:g} -> one B-source i = C(V) dV/dt (PDK C(V), same constants and corner factor)'
    for f in wd.glob('lk_*.spice'):
        inc[f.name] = md5(f)
    lfv = lfv or LF_R4
    hdr = header(corner, temp).replace('reltol=1e-3', 'reltol=1e-4') if (pfd == 'x' or lf == 'x') else ''
    deck = '* ' + run + '\n' + hdr + tb_ladder(v, n, m_div, fref, kv, df0, vt0, icp, t_end, pfd, lf, lfv, en,
                                                icp_bits=bits, tmax=tmax) + '.end\n'
    tf.ngspice(wd, 'lad', deck, timeout=11 * 3600)
    fc, pm = loop_margins(lfv, icp, kv, n) if kv > 0 else (0.0, 0.0)
    an = (lfv, icp, kv, n, df0) if small_step else None
    try:
        r = analyse_ladder(wd / 'lad.raw', fref, n, v, t_end, analytic=an)
    except Exception as e:  # noqa
        r = dict(error=repr(e)[:300], log_tail=(wd / 'lad.log').read_text(errors='replace')[-800:])
        r['pass'] = False
    r.update(run=run, rung=rung, corner=corner, temp_c=temp, vdd=v, n=n, m_div=m_div, kv_hz_v=kv, df0_hz=df0, vt0=vt0,
             icp_a=icp, icp_code=code, cp_enabled=en, pfd=pfd, lf=lf, lf_values=lfv, t_end_s=t_end,
             analytic_fc_hz=fc, analytic_pm_deg=pm, expect=expect, limits=LADDER_LIMITS,
             includes_md5=inc, deck_md5=md5(wd / 'lad.spice'), dir=str(wd.relative_to(REPO)),
             vco='behavioural phase integrator', divider='behavioural (exact /m_div of VCO phase)')
    if pfd == 'ideal' and lf == 'ideal' and not small_step:
        r['hop4_reference'] = hop4(lfv, icp if en else 0.0, kv, n, df0, fref, t_end, m_div)
    r['as_expected'] = (r['pass'] == (expect == 'pass')) and 'error' not in r   # a crash is never 'as expected'
    (wd / 'result.json').write_text(json.dumps(r, indent=1, default=float) + '\n')
    print(json.dumps({k: r.get(k) for k in ('run', 'pass', 'as_expected', 'checks', 't_lock_2deg_s', 'f_err_hold_hz',
                                            'spo_ps', 'vtune_final_v', 'analytic_fc_hz', 'analytic_pm_deg',
                                            'step_err_peak_rel', 'step_err_rms_rel', 'hop4_reference', 'error')}, default=float), flush=True)
    return r


MMD_RC = LADDER / 'mmd_rc_c' / 'pt_lo_mmd_flat.rc.spice'   # Magic extresist (analog image) of generated/lo_mmd.gds


def run_mmd_rc(cases, expect='pass'):
    """Rung 4a: open-loop ratio check of the RC-extracted MMD (flat extresist netlist, wire + poly R; supplies
    not resisted).  Pass = measured ratio within 0.02 of the set ratio (3 periods) and single period within 0.05."""
    src = MMD_RC.read_text().replace('.subckt pt_lo_mmd_flat', '.subckt pt_lo_mmd').replace('.ends pt_lo_mmd_flat', '.ends')
    out = []
    for (corner, temp, v, f, n, amp, cm) in cases:
        run = f'r4_mmdrc_{corner}{temp}_{v}_{f / 1e9:.2f}_{n}_{amp}_{cm}'
        wd = LADDER / run
        if wd.exists():
            shutil.rmtree(wd)
        wd.mkdir(parents=True)
        (wd / 'mmd_rc.spice').write_text(src)
        m = tf.ngspice(wd, 'mmd', header(corner, temp) + tb_mmd('mmd_rc.spice', f, n, v, amp, cm) + '.end\n')
        nm = (m.get('per', 0) / 3) * f if m.get('per') else None
        n1 = m.get('per1', 0) * f if m.get('per1') else None
        r = dict(run=run, rung=4, corner=corner, temp_c=temp, vdd=v, f_in_hz=f, n_set=n, amp_v_per_leg=amp, cm_v=cm,
                 n_measured=nm, n_single=n1, fb_width_ns=m.get('wid', 0) * 1e9, idd_ma=-m.get('idd', math.nan) * 1e3,
                 netlist='RC-extracted flat (Magic extresist, analog image), no add_rg', includes_md5={
                     'mmd_rc.spice': md5(wd / 'mmd_rc.spice'), 'generated/lo_mmd.gds': md5(HERE.parent / 'generated' / 'lo_mmd.gds')},
                 errors=m['_errors'][:3], expect=expect)
        r['pass'] = bool(nm and abs(nm - n) < 0.02 and n1 and abs(n1 - n) < 0.05)
        r['as_expected'] = r['pass'] == (expect == 'pass')
        (wd / 'result.json').write_text(json.dumps(r, indent=1) + '\n')
        print(json.dumps(r), flush=True)
        out.append(r)
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('bench')
    ap.add_argument('--extracted', action='store_true')
    ap.add_argument('--cases', default='')
    a = ap.parse_args()
    if a.bench == 'mmd':
        cases = json.loads(a.cases) if a.cases else [('ss', 32, 3.15, 2.98e9, 32, 0.5, 1.7)]
        r = run_mmd([tuple(c) for c in cases], a.extracted)
        key = 'mmd_' + ('extracted' if a.extracted else 'schematic')
        old = load().get(key, [])
        keep = [o for o in old if o['deck'] not in {x['deck'] for x in r}]
        save(key, keep + r)
    elif a.bench == 'cpdc':
        corners = json.loads(a.cases) if a.cases else [('tt', 27, 3.3), ('ss', 32, 3.15), ('ff', 22, 3.35)]
        save('cp_dc', run_cp_dc([tuple(c) for c in corners]))
    elif a.bench == 'pfd':
        stage()
        res = []
        for corner, temp, v in ([('tt', 27, 3.3), ('ss', 32, 3.15), ('ff', 22, 3.35)]):
            for skew in (0.0, 20e-12, -20e-12):
                name = f'pfd_{corner}{temp}_{skew * 1e12:.0f}'
                m = tf.ngspice(WORK, name, header(corner, temp) + tb_pfd_pulse('lo_pfdcp.spice', v, skew=skew) + '.end\n')
                r = dict(corner=corner, temp_c=temp, vdd=v, skew_s=skew, w_up_ps=m.get('wup', math.nan) * 1e12,
                         w_dn_ps=m.get('wdn', math.nan) * 1e12, q_per_cycle_fc=-m.get('qnet', math.nan) / 2 * 1e15)
                print(json.dumps(r), flush=True)
                res.append(r)
        save('pfd_pulse', res)
    elif a.bench == 'cpnoise':
        t_on = load().get('t_on_s', 300e-12)
        save('cp_noise', run_cp_noise(t_on=t_on) + run_cp_noise('ss', 32, 3.15, t_on=t_on))
    elif a.bench == 'lock':
        kw = json.loads(a.cases) if a.cases else {}
        r = run_lock(a.extracted, **kw)
        old = [o for o in load().get('lock', []) if o['deck'] != r['deck']]
        save('lock', old + [r])
    elif a.bench == 'ladder':
        kw = json.loads(a.cases)
        r = run_ladder(**kw)
        old = [o for o in load().get('ladder', []) if o['run'] != r['run']]
        save('ladder', old + [r])
    elif a.bench == 'mmdrc':
        c = json.loads(a.cases)
        r = run_mmd_rc([tuple(x) for x in c['cases']], c.get('expect', 'pass'))
        old = [o for o in load().get('ladder_mmd_rc', []) if o['run'] not in {x['run'] for x in r}]
        save('ladder_mmd_rc', old + r)
    elif a.bench == 'lf':
        vals = json.loads(a.cases) if a.cases else {}
        save('loop_filter', write_lf(**vals))
