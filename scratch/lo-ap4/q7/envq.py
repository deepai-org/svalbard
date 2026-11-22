#!/usr/bin/env python3
"""QVCO in its real environment (LO26, SG-3/SG-5; LO owner 2026-11-14).

RC-extracted RF cell (scratch/lo/r4_qvco2/rft6, = published pt_lc_qvco5 r6b) + schematic aux taps + spiral model,
as lcvco/run_qvco_r5_ext.py / scratch/lo/r5_pn/ext12.py, with the tank loads made real:
  loads = c230     : 230 fF per tank node (the old bench; must reproduce scratch/lo/r5_pn/ext12.json)
  loads = pub      : extracted published pt_lo_ext (mode 2) on all four nodes, flat-RC published pt_lo_mmd on IP/IN
                     (EN = 1, dividing, N given), published pt_lo_mmd_qdum on QP/QN, pt_lo_obs on I and Q (EN = 0)
  loads = stg      : same with the staged ap4 lo_mmd (flat RC) / lo_mmd_qdum / lo_obs and the cand2 lo_ext
  loads = none     : nothing (must-fail / sensitivity)
plus  top   : the tank wiring of the QVCO core top that the RF-cell extraction does not contain (C-only extraction
              of pt_lc_qvco5_core minus the RF cell, q7/topc: per-node C to ground and the IP-IN, IN-QP, QP-QN mutuals)
      route : chip-top route C per tank node to ground (two-sided: 0 / 40 fF; no routed top exists)
      fill  : extra C per tank node from fill (fF, from the fill-aware extraction; 0 with the keep-out markers)
      vq    : QVCO supply (regulated VDD_LO); the loads, band bits and VDDB stay on the die supply of the corner
One directory per run, result.json with a pass-independent record; limits are applied by the caller table.

usage: envq.py <tag> <case>...   case = corner:band:vtune:loads[:k=v,...]   k in vq, vdie, route, fill, n, top, ib, T
"""
import sys, json, math, re, shutil, hashlib, os
from pathlib import Path
T_ = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0, T_); sys.path.insert(0, T_ + '/lcvco'); sys.path.insert(0, '/home/ubuntu/svalbard/scratch/lo/r5_pn')
import timing_flow as tf
import run_timing as rt
import run_loop as rl
import run_lcvco as rlc
import run_qvco_r5_ext as rx
import corners  # noqa: adds PF115 / PF85 / OPT85 ... and the varactor-Q patch
HERE = Path(__file__).resolve().parent
AP = HERE.parent
RFW = __import__('os').environ.get('QRFW', '/home/ubuntu/svalbard/scratch/lo/r4_qvco2/rft6')
GEN = Path(T_) / 'generated'
NETS = dict(
    pub=dict(lo_ext=GEN / 'lo_ext.ext.spice', mmd=AP / 'rc/lo_mmd_old/pt_lo_mmd_flat.rc.spice',
             qdum=GEN / 'lo_mmd_qdum.ext.spice', obs=GEN / 'lo_obs.ext.spice'),
    # 2026-11-20 range fix r10: extracted lo_ext n4 (20-unit pair, loext3/lay/a4) + v7 divider (fixcap)
    r10=dict(lo_ext=AP / 'loext3/lay/a4/lo_ext/stage/lo_ext.ext.spice', mmd=AP / 'rc/lo_mmd_v7/pt_lo_mmd_flat.rcfix.spice',
             qdum=AP / 'run_lo_mmd_qdum_ap4/lo_mmd_qdum/stage/lo_mmd_qdum.ext.spice',
             obs=AP / 'run_lo_obs_ap4/lo_obs/stage/lo_obs.ext.spice'),
    # r17 (2026-11-21, coordinator: published lo_mmd stays the candidate, v7 dropped): published lo_mmd (fixcap16) +
    # published lo_mmd_qdum, lo_ext n4 (a4), staged lo_obs
    r17=dict(lo_ext=AP / 'loext3/lay/a4/lo_ext/stage/lo_ext.ext.spice', mmd=AP / 'rc/lo_mmd_old/pt_lo_mmd_flat.rcfix16.spice',
             qdum=GEN / 'lo_mmd_qdum.ext.spice', obs=AP / 'run_lo_obs_ap4/lo_obs/stage/lo_obs.ext.spice'),
    # r16: as r10 with the divider repaired by fixcap16 (ground C and dropped coupling vs C-only; port nets LP/LN)
    r16=dict(lo_ext=AP / 'loext3/lay/a4/lo_ext/stage/lo_ext.ext.spice', mmd=AP / 'rc/lo_mmd_v7/pt_lo_mmd_flat.rcfix16.spice',
             qdum=AP / 'run_lo_mmd_qdum_ap4/lo_mmd_qdum/stage/lo_mmd_qdum.ext.spice',
             obs=AP / 'run_lo_obs_ap4/lo_obs/stage/lo_obs.ext.spice'),
)
# QVCO core-top wiring not in the RF cell (fF): q7/topc (top.c.spice minus rft6 c.spice), see NOTES
_TOPCF = HERE / __import__('os').environ.get('QTOPC', 'topc.json')   # topc9f.json: r8 port tracks + MIM 9.0 core top
TOPC = json.loads(_TOPCF.read_text()) if _TOPCF.exists() else None
md5 = lambda p: hashlib.md5(Path(p).read_bytes()).hexdigest()


def loads_text(wd, kind, v, n, obs_en=0, qdum_en=None, mmd_en=1, sel='emo'):
    if kind in ('c230', 'none'):
        return ''.join(f'CL{x} {x} 0 230f\n' for x in ('ip', 'in', 'qp', 'qn')) if kind == 'c230' else '', {}
    N = NETS[kind]
    inc = ''
    t = rt.rg_wrap_locml(N['lo_ext'].read_text())
    (wd / 'lo_ext.spice').write_text(tf.uniquify_subckts(t, 'loext', keep=('pt_lo_ext', 'ct_locml', 'ct_locml_core')))
    (wd / 'mmd.spice').write_text(N['mmd'].read_text().replace('.subckt pt_lo_mmd_flat', '.subckt pt_lo_mmd').replace('.ends pt_lo_mmd_flat', '.ends'))
    (wd / 'qdum.spice').write_text(tf.uniquify_subckts(N['qdum'].read_text(), 'qd', keep=('pt_lo_mmd_qdum',)))
    (wd / 'obs.spice').write_text(tf.uniquify_subckts(N['obs'].read_text(), 'ob', keep=('pt_lo_obs',)))
    inc = '.include lo_ext.spice\n.include mmd.spice\n.include qdum.spice\n.include obs.spice\n'
    qdum_en = mmd_en if qdum_en is None else qdum_en
    s = inc + f'VDIE vdie 0 {v}\nVEXT ext 0 0\nVINT int 0 {v}\nVMEN men 0 {v * mmd_en}\nVQEN qen 0 {v * qdum_en}\nVOEN oen 0 {v * obs_en}\n'
    s += ''.join(f'RP{x} pad{x} 0 50\nCP{x} pad{x} 0 1p\n' for x in ('ip', 'in', 'qp', 'qn'))
    s += ''.join(f'XRX{x} rxd lo{x} rxs 0 nfet_03v3 w=5u l=0.28u m=12\nXTX{x} txd lo{x} txs 0 nfet_03v3 w=10u l=0.28u m=4\nCW{x} lo{x} 0 22f\n'
                 for x in ('ip', 'in', 'qp', 'qn'))
    s += f'VRXD rxd 0 {v / 2}\nVRXS rxs 0 {v / 2}\nVTXD txd 0 2.5\nVTXS txs 0 1.0\n'
    if 'e' in sel:
        s += 'XLE padip padin padqp padqn ip in qp qn ext int 0 loip loin loqp loqn atbvb vdie 0 pt_lo_ext\n'
    s += ''.join(f'VN{k} n{k} 0 {v * b}\n' for k, b in enumerate(rl.nbits(n)))
    if 'm' in sel:
        s += 'XMMD ip in men n0 n1 n2 n3 n4 n5 fb vdie 0 pt_lo_mmd\nCFB fb 0 50f\n'
        s += 'XQD qp qn qen qdp qdn vdie 0 pt_lo_mmd_qdum\n'
    if 'o' in sel:
        s += 'XOI ip in oen obsi vdie 0 pt_lo_obs\nXOQ qp qn 0 obsq vdie 0 pt_lo_obs\nCOB obsi 0 2p\n'
    return s, {k: md5(p) for k, p in N.items()}


def deck(cname, code, vt, kind, vq=None, vdie=None, route=0.0, fill=0.0, n=48, top=1, ib=10.0, T=60e-9, obs_en=0, qdum_en=None, wd=None, sel='emo', seed=0):
    c = rx.CORNERS[cname]
    v = vdie or c['v']
    vq = vq or v
    fn = rx.processed(RFW, 'RC', c['cw'], c['rser'])
    shutil.copy(rx.SIM / fn, wd / fn)
    rlc.WORK = wd
    sp = rlc.spiral_file(c['spiral'])
    pn = rx.ports(RFW, 'RC')
    conn = {'VSS': '0', 'IP': 'ip', 'IN': 'in', 'QP': 'qp', 'QN': 'qn', 'TSI': 'tsi', 'TSQ': 'tsq', 'VDDCI': 'vddci', 'VDDCQ': 'vddcq'}
    for p in pn:
        b = re.match(r'(B\d)_[IQ]', p)
        if b:
            conn[p] = b.group(1).lower()
        elif p.startswith('VDD_'):
            conn[p] = 'vdd'
        elif p.startswith('VTUNE'):
            conn[p] = 'vt'
        elif p.startswith('IBIAS'):
            conn[p] = 'ibias'
        elif p.startswith('CMLSEL'):
            conn[p] = 'cmlsel'
    xline = 'XRF ' + ' '.join(conn[p] for p in pn) + ' pt_lc_qvco_rf'
    bits = ''.join(f'VB{k} b{k} 0 {v if (code >> k) & 1 else 0}\n' for k in range(4))
    cf = 15.0 * c['cw']
    td = T - 8e-9
    ld, hashes = loads_text(wd, kind, v, n, obs_en, qdum_en, sel=sel)
    par = ''
    if top and TOPC:
        for x, val in TOPC['gnd'].items():
            par += f'CTG{x} {x} 0 {val * c["cw"]}f\n'
        for (a, b), val in ((k.split('-'), vv) for k, vv in TOPC['mut'].items()):
            par += f'CTM{a}{b} {a} {b} {val * c["cw"]}f\n'
    if route or fill:
        par += ''.join(f'CRT{x} {x} 0 {route + fill}f\n' for x in ('ip', 'in', 'qp', 'qn'))
    fbm = ''
    if kind in ('pub', 'stg'):
        tdf = T - 2.4 * n / 2.2e9          # two FB periods before the end; only meaningful when tdf >= 25 ns (T >= 80 ns at N 48)
        fbm = ((f'.measure tran tfb1 when v(fb)={v / 2} td={tdf} rise=1\n'
                f'.measure tran tfb2 when v(fb)={v / 2} td={tdf} rise=2\n' if 'm' in sel and tdf >= 25e-9 else '') +
               f'.measure tran imm avg i(VDIE) from={td} to={T}\n' +
               (f'.measure tran lomax max v(loip) from={td} to={T}\n.measure tran lomin min v(loip) from={td} to={T}\n' if 'e' in sel else ''))
    d = rlc.hdr(c['corner'], c['temp']) + (f'.param sw_stat_mismatch=1\n.option seed={seed}\n' if seed else '') + f""".include {sp}
.include {fn}
VDD vdd 0 {vq}
VDDB vddb 0 {v}
VCS cmlsel 0 0
VT vt 0 {vt}
IB vdd ibias {ib}u
XNB ibias ibias 0 0 nfet_03v3 w=1.44u l=1u
VENB enb 0 0
{bits}{xline}
""" + ''.join(f'RF{x} {x} l{x} 0.5\nCF{x} l{x} 0 {cf}f\n' for x in ('ip', 'in', 'qp', 'qn')) + f"""XLI lip lin 0 pt_spiral
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
{ld}{par}.tran 1p {T}
.measure tran per trig v(di) val=0 td={td} rise=1 targ v(di) val=0 td={td} rise=11
.measure tran tiq trig v(di) val=0 td={td} rise=1 targ v(dq) val=0 td={td} rise=1
.measure tran dimax max v(di) from={td} to={T}
.measure tran dqmax max v(dq) from={td} to={T}
.measure tran dimax2 max v(di) from={td - 15e-9} to={td - 10e-9}
.measure tran ipavg avg v(ip) from={td} to={T}
.measure tran ipmax max v(ip) from={td} to={T}
.measure tran ipmin min v(ip) from={td} to={T}
.measure tran icore avg i(VDD) from={td} to={T}
{fbm}.end
"""
    return d, hashes


def one(tag, case):
    f = case.split(':')
    cname, code, vt, kind = f[0], int(f[1]), float(f[2]), f[3]
    kw = {}
    if len(f) > 4 and f[4]:
        for kv in f[4].split(','):
            k, val = kv.split('=')
            kw[k] = val if k == 'sel' else float(val) if k not in ('n', 'top', 'obs_en', 'qdum_en', 'seed') else int(val)
    wd = HERE / tag / case.replace(':', '_').replace(',', '_').replace('=', '')
    if (wd / 'result.json').exists():
        return json.loads((wd / 'result.json').read_text())
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    rx.SIM = HERE / 'proc'
    rx.SIM.mkdir(exist_ok=True)
    d, hashes = deck(cname, code, vt, kind, wd=wd, **kw)
    m = tf.ngspice(wd, 'q', d, timeout=8 * 3600)
    fo = 10 / m['per'] if m.get('per') else None
    ph = ((m['tiq'] * fo * 360 + 180) % 360 - 180) if fo and m.get('tiq') is not None else None
    n = kw.get('n', 48)
    fbp = (m['tfb2'] - m['tfb1']) if m.get('tfb1') and m.get('tfb2') else None
    r = dict(case=case, tag=tag, cname=cname, band=code, vtune=vt, loads=kind, opts=kw, f_hz=fo, q_minus_i_deg=ph,
             diff_peak_i_v=m.get('dimax'), diff_peak_q_v=m.get('dqmax'), diff_peak_15ns_earlier_v=m.get('dimax2'),
             cm_v=m.get('ipavg'), ip_max_v=m.get('ipmax'), ip_min_v=m.get('ipmin'),
             i_qvco_ma=-m.get('icore', math.nan) * 1e3, i_die_loads_ma=(-m['imm'] * 1e3 if m.get('imm') else None),
             lo_gate_max_v=m.get('lomax'), lo_gate_min_v=m.get('lomin'),
             mmd_ratio=(fbp * fo if fbp and fo else None), mmd_n=n, md5=hashes, errors=m.get('_errors'))
    r['oscillates'] = bool(fo and (m.get('dimax') or 0) > 0.5 and abs(abs(ph or 0) - 90) < 10)
    if kind in ('pub', 'stg') and m.get('tfb1'):
        r['mmd_divides'] = bool(r['mmd_ratio'] and abs(r['mmd_ratio'] - n) < 0.05)
    (wd / 'result.json').write_text(json.dumps(r, indent=1, default=str) + '\n')
    return r


if __name__ == '__main__':
    tag = sys.argv[1]
    for case in sys.argv[2:]:
        r = one(tag, case)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ('md5', 'tag', 'opts', 'cname', 'band', 'vtune', 'loads')}), flush=True)
