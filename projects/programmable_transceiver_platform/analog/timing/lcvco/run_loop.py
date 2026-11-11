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
    elif a.bench == 'lf':
        vals = json.loads(a.cases) if a.cases else {}
        save('loop_filter', write_lf(**vals))
