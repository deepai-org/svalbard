#!/usr/bin/env python3
"""QVCO r5 (LO owner, 2026-11-11): band recentring + high-band start-up, sized against the
coordinator's PESSIMISTIC tank case instead of the bare schematic.

Why: r3's 2.33-2.53 GHz "guaranteed" range was schematic.  The r4 RC-extracted layout (results_ext.json
v2rcg, scratch/reviews/model-uncertainty-audit.md item 5) gives ss band-0 top 2.349 GHz and no start-up
at bands >= 12: ~0.73 pF differential of routing C and ~20 ohm of escape R in series with every band MIM.

Corner definitions (every check in this file):
  PESS  ss / 32 C / 3.15 V, L +10 % and low Q (pt_spiral_lhi_lowq or the r5 spiral equivalent),
        every MIM branch, switch and varactor with `rser` ohm series R, explicit gate R, and the
        layout parasitic C x 1.15 (cw_scale).
  OPT   ff / 22 C / 3.35 V, L -10 % (pt_spiral_llo), parasitic C x 0.90, no extra series R.
Window: the PESS band-0 / VTUNE 3.0 top must be >= 2.4835 GHz x 1.03 = 2.558 GHz and the OPT
band-15 / VTUNE 0.3 bottom <= 2.40 GHz / 1.03 = 2.330 GHz (3 % margin each side, every corner in
between lies inside these two).

Schematic-stage netlist: `net(p)` writes pt_lc_qvco5 with lumped layout parasitics (cw on each tank
node, cx on each band-switch internal node, rser in every capacitive branch, rfeed between spiral and
core).  The layout stage (qvco_rf_layout.py) replaces the lumped values with extraction.

    python3 qvco_r5.py point <tag> <corner> <code> <vt> [k=v ...]
    python3 qvco_r5.py sweep <tag> [k=v ...]       # PESS top, OPT bottom, start-up at every band end
"""
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import timing_flow as tf  # noqa: E402
import run_lcvco as rl  # noqa: E402

ROOT = HERE.parents[4]
WORK = ROOT / 'scratch' / 'lo' / 'r4_qvco2' / 'sim'
RES = ROOT / 'scratch' / 'lo' / 'r4_qvco2' / 'design.json'
PAR = int(os.environ.get('Q5_PAR', '2'))

# r5 defaults (see README 'round 4'); every value is a design parameter of the sweep
P0 = dict(
    nn=16, wn=5.0,           # NMOS cross pair: nn fingers x wn um per side
    ncp=5, wcp=4.8,          # coupling NMOS
    np=24, wp=5.0,           # PMOS cross pair
    ntail=24, wtail=50.0,    # tail mirror (x 10 uA reference: ratio = ntail*wtail/2 / 2 ... see net())
    cfix=0.0,                # fixed MIM side (um); 0 = none
    b0=7.1, bsw=2, nbits=4,  # band bit k: two MIMs of side b0*sqrt(2)^k ... (area doubles), switch 12 um x bsw*2^k
    wsw=12.0,
    var_area=169.0,          # varactor area per side (um^2)
    rser=0.0,                # extra series R per capacitive branch (MIM terminal, switch, varactor)
    rvar=2.0,                # varactor well/accumulation series R per side (schematic r3 value)
    cw=0.0,                  # lumped routing C per tank node to VSS (fF)
    cwd=0.0,                 # lumped routing C between the two tank nodes of a core (fF)
    cx=0.0,                  # lumped routing C per band-switch internal node (fF)
    rfeed=0.0,               # spiral feed R per side (ohm)
    cfeed=0.0,               # spiral feed C per side (fF)
    cw_scale=1.0,
    rgf=51.0,                # gate R per 5 um single-side-contacted finger (README conservative case)
    cl=230.0,                # pt_lo_ext CML input load per tank node (fF): 190 CML + ~40 LO11 pre-amp drains (fork C)
    spiral='pt_spiral',
    hdr_w=0.0,               # PMOS core header width per core (um, 5 um fingers); 0 = none (CMLSEL port tied off)
    cdec=0.0,                # decap on the header output VDDC per core (pF, MIM)
)


def net(p):
    """pt_lc_qvco5 netlist text for parameter dict p."""
    s = p['cw_scale']
    bank = ''
    for k in range(p['nbits']):
        side = p['b0'] * math.sqrt(2) ** k
        m = int(p['bsw'] * 2 ** k)
        r = p['rser']
        bank += f"""XCA{k} P XA{k} cap_mim_2f0_m4m5_noshield c_width={side:.3f}u c_length={side:.3f}u
RA{k} XA{k} X{k} {r + 1e-3}
XCB{k} N XB{k} cap_mim_2f0_m4m5_noshield c_width={side:.3f}u c_length={side:.3f}u
RB{k} XB{k} Y{k} {r + 1e-3}
XS{k} X{k} B{k} Y{k} VSS nfet_03v3 w={p['wsw']}u l=0.28u m={m}
XGX{k} X{k} B{k} VSS VSS nfet_03v3 w=1u l=0.28u
XGY{k} Y{k} B{k} VSS VSS nfet_03v3 w=1u l=0.28u
""" + (f"CX{k} X{k} VSS {p['cx'] * s * 2 ** (k / 2)}f\nCY{k} Y{k} VSS {p['cx'] * s * 2 ** (k / 2)}f\n" if p['cx'] else '')
    bports = ' '.join(f'B{k}' for k in range(p['nbits']))
    rgn = p['rgf'] / p['nn']
    rgp = p['rgf'] / p['np']
    rgc = p['rgf'] / p['ncp']
    cfix = (f"XCF P N cap_mim_2f0_m4m5_noshield c_width={p['cfix']}u c_length={p['cfix']}u\n" if p['cfix'] else '')
    par = ''
    if p['cw']:
        par += f"CWP P VSS {p['cw'] * s}f\nCWN N VSS {p['cw'] * s}f\n"
    if p['cwd']:
        par += f"CWD P N {p['cwd'] * s}f\n"
    va = p['var_area'] * 1e-12
    if p['hdr_w']:
        m = max(1, int(round(p['hdr_w'] / 5)))
        hdr = ''.join(f"XH{c} VDDC{c} CMLSEL VDD VDD pfet_03v3 w=5u l=0.28u m={m}\n"
                      f"XHB{c} VDDC{c} CMLSEL VSS VSS nfet_03v3 w=0.5u l=2u\n" for c in 'IQ')   # bleed, on only in CMLSEL mode
        if p['cdec']:
            side = math.sqrt(p['cdec'] * 1e3 / 2)
            hdr += ''.join(f"XDC{c} VDDC{c} VSS cap_mim_2f0_m4m5_noshield c_width={side:.2f}u c_length={side:.2f}u\n" for c in 'IQ')
    else:
        hdr = 'RHI VDDCI VDD 1m\nRHQ VDDCQ VDD 1m\nRHS CMLSEL VSS 1m\n'
    return f"""* pt_lc_qvco5 (qvco_r5.py) params: {json.dumps(p, sort_keys=True)}
.subckt pt_lc_qvco5 EN CMLSEL VTUNE IBIAS {bports} IP IN QP QN VDD VSS
XEI EN ENB VDD VSS pt_t_inv1
XNB IBIAS IBIAS NBS VSS nfet_03v3 w=2u l=1u
XNBS NBS EN VSS VSS nfet_03v3 w=4u l=0.28u
XNBC IBIAS ENB VSS VSS nfet_03v3 w=1u l=0.28u
XCI IP IN QP QN TSI VTUNE IBIAS {bports} VDDCI VSS pt_lc_core5
XCQ QP QN IN IP TSQ VTUNE IBIAS {bports} VDDCQ VSS pt_lc_core5
{hdr}
.ends
.subckt pt_lc_core5 P N CP CN TS VTUNE IBIAS {bports} VDD VSS
XT TS IBIAS VSS VSS nfet_03v3 w={p['wtail']}u l=1u m={p['ntail']}
RG1 N GN1 {rgn:.3f}
RG2 P GN2 {rgn:.3f}
RG3 CN GC1 {rgc:.3f}
RG4 CP GC2 {rgc:.3f}
RG5 N GP1 {rgp:.3f}
RG6 P GP2 {rgp:.3f}
XN1 P GN1 TS VSS nfet_03v3 w={p['wn']}u l=0.28u m={p['nn']}
XN2 N GN2 TS VSS nfet_03v3 w={p['wn']}u l=0.28u m={p['nn']}
XC1 P GC1 TS VSS nfet_03v3 w={p['wcp']}u l=0.28u m={p['ncp']}
XC2 N GC2 TS VSS nfet_03v3 w={p['wcp']}u l=0.28u m={p['ncp']}
XP1 P GP1 VDD VDD pfet_03v3 w={p['wp']}u l=0.28u m={p['np']}
XP2 N GP2 VDD VDD pfet_03v3 w={p['wp']}u l=0.28u m={p['np']}
{cfix}RV1 P V1 {p['rvar'] + p['rser'] + 1e-3}
XV1 V1 VTUNE pt_var_nwell AREA={va:.4e}
RV2 N V2 {p['rvar'] + p['rser'] + 1e-3}
XV2 V2 VTUNE pt_var_nwell AREA={va:.4e}
{bank}{par}.ends
"""


def varactor_model():
    q = (HERE / 'qvco.spice').read_text()
    i = q.index('.subckt pt_var_nwell')
    return q[i:q.index('.ends', i) + 5] + '\n'


CORNERS = {
    'PESS': dict(corner='ss', temp=32, v=3.15, spiral_var='lhi_lowq', cw_scale=1.15, rser_on=True),
    'OPT': dict(corner='ff', temp=22, v=3.35, spiral_var='llo', cw_scale=0.90, rser_on=False),
    'TT': dict(corner='tt', temp=27, v=3.3, spiral_var='', cw_scale=1.0, rser_on=False),
    'SSN': dict(corner='ss', temp=32, v=3.15, spiral_var='', cw_scale=1.0, rser_on=False),
    'FFN': dict(corner='ff', temp=22, v=3.35, spiral_var='', cw_scale=1.0, rser_on=False),
    'SSLQ': dict(corner='ss', temp=32, v=3.15, spiral_var='lowq', cw_scale=1.15, rser_on=True),
    'FFLQ': dict(corner='ff', temp=22, v=3.35, spiral_var='llo_lowq', cw_scale=0.90, rser_on=True),
}


def spiral_name(base, var):
    return base if not var else f'{base}_{var}'


def deck(p, cname, code, vt, T=None, rser_pess=3.0):
    T = T or float(os.environ.get('Q5_T', '30e-9'))
    c = CORNERS[cname]
    q = dict(p)
    q['cw_scale'] = c['cw_scale']
    if c['rser_on']:
        q['rser'] = max(q['rser'], rser_pess)
    else:
        q['rser'] = 0.0
    rl.WORK = WORK
    WORK.mkdir(parents=True, exist_ok=True)
    src = Path(os.environ.get('Q5_SPIRALS', HERE / 'spiral.spice'))
    import shutil
    shutil.copy(src, WORK / 'spiral.spice')
    import re
    txt = (WORK / 'spiral.spice').read_text()
    var = spiral_name(p['spiral'], c['spiral_var'])
    blk = re.search(rf'(\.subckt {var} .*?\.ends {var}\n)', txt, re.S).group(1).replace(var, 'pt_spiral_x')
    (WORK / f'sp_{var}.spice').write_text(blk)
    nb = q['nbits']
    bits = ''.join(f'VB{k} b{k} 0 {c["v"] if (code >> k) & 1 else 0}\n' for k in range(nb))
    bports = ' '.join(f'b{k}' for k in range(nb))
    nm = f"n_{abs(hash(json.dumps(q, sort_keys=True))) % 10**10}.spice"
    (WORK / nm).write_text(net(q) + varactor_model() + """.subckt pt_t_inv1 A Y VDD VSS
XP Y A VDD VDD pfet_03v3 w=2u l=0.28u
XN Y A VSS VSS nfet_03v3 w=1u l=0.28u
.ends
""")
    rf = q['rfeed'] / 1 + 1e-3
    cf = q['cfeed'] * c['cw_scale']
    feed = ''.join(f'RF{n} {n} l{n} {rf}\n' + (f'CF{n} l{n} 0 {cf}f\n' if cf else '') for n in ('ip', 'in', 'qp', 'qn'))
    td = T - 8e-9
    return rl.hdr(c['corner'], c['temp']) + f""".include sp_{var}.spice
.include {nm}
VDD vdd 0 {c['v']}
VEN en 0 {c['v']}
VT vt 0 {vt}
IB vdd ibias 10u
{bits}VCS cmlsel 0 0
X1 en cmlsel vt ibias {bports} ip in qp qn vdd 0 pt_lc_qvco5
{feed}XLI lip lin 0 pt_spiral_x
XLQ lqp lqn 0 pt_spiral_x
EDI di 0 ip in 1
EDQ dq 0 qp qn 1
IK ip in pulse(0 200u 0.2n 50p 50p 0.3n 1)
""" + ''.join(f'CL{n} {n} 0 {q["cl"]}f\n' for n in ('ip', 'in', 'qp', 'qn')) + f""".tran 1p {T}
.measure tran per trig v(di) val=0 td={td} rise=1 targ v(di) val=0 td={td} rise=11
.measure tran tiq trig v(di) val=0 td={td} rise=1 targ v(dq) val=0 td={td} rise=1
.measure tran dimax max v(di) from={td} to={T}
.measure tran ipavg avg v(ip) from={td} to={T}
.measure tran icore avg i(VDD) from={td} to={T}
.end
"""


def point(tag, p, cname, code, vt):
    name = f'{tag}_{cname}_b{code}_vt{vt}'
    m = tf.ngspice(WORK, name, deck(p, cname, code, vt))
    f = 10 / m['per'] if m.get('per') else None
    ph = ((m['tiq'] * f * 360 + 180) % 360 - 180) if f and m.get('tiq') else None
    amp = m.get('dimax') or 0
    return dict(case=name, cname=cname, band=code, vtune=vt, f_hz=f, q_minus_i_deg=ph, diff_peak_v=amp,
                cm_v=m.get('ipavg'), i_ma=-m.get('icore', math.nan) * 1e3, oscillates=bool(f and amp > 0.3),
                errors=m.get('_errors'))


def sweep(tag, p, jobs=None):
    top = 2.4835e9 * 1.03
    bot = 2.40e9 / 1.03
    hi = 2 ** p['nbits'] - 1
    jobs = jobs or [('PESS', 0, 3.0), ('OPT', hi, 0.3), ('PESS', hi, 0.3), ('OPT', 0, 3.0),
                    ('FFLQ', hi, 0.3), ('TT', 0, 3.0), ('TT', hi, 0.3)]
    with ThreadPoolExecutor(PAR) as ex:
        rs = list(ex.map(lambda j: point(tag, p, *j), jobs))
    out = {r['case']: r for r in rs}
    for r in rs:
        print(f"{r['case']:32s} f={((r['f_hz'] or 0) / 1e9):.4f} amp={r['diff_peak_v']:.3f} QI={r['q_minus_i_deg']} I={r['i_ma']:.1f}mA osc={r['oscillates']}", flush=True)
    pt = out.get(f'{tag}_PESS_b0_vt3.0', {}).get('f_hz') or 0
    ob = out.get(f'{tag}_OPT_b{hi}_vt0.3', {}).get('f_hz') or 9e9
    summ = dict(tag=tag, params=p, pess_top_hz=pt, opt_bottom_hz=ob, top_ok=pt >= top, bottom_ok=ob <= bot,
                all_start=all(r['oscillates'] for r in rs))
    print(json.dumps({k: summ[k] for k in ('pess_top_hz', 'opt_bottom_hz', 'top_ok', 'bottom_ok', 'all_start')}), flush=True)
    res = json.loads(RES.read_text()) if RES.exists() else {}
    res[tag] = dict(summary=summ, points=out)
    RES.parent.mkdir(parents=True, exist_ok=True)
    RES.write_text(json.dumps(res, indent=1, default=str) + '\n')
    return summ


def parse_kv(args):
    p = dict(P0)
    for a in args:
        k, v = a.split('=')
        p[k] = type(P0[k])(v) if k in P0 and not isinstance(P0[k], str) else v
    return p


if __name__ == '__main__':
    if sys.argv[1] == 'sweep':
        sweep(sys.argv[2], parse_kv(sys.argv[3:]))
    elif sys.argv[1] == 'point':
        a = sys.argv
        print(json.dumps(point(a[2], parse_kv(a[6:]), a[3], int(a[4]), float(a[5])), indent=1))
