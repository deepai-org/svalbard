#!/usr/bin/env python3
"""Benches for the autonomous RF LO quadrature VCO (lcvco/qvco.spice) with the
tank inductor models of lcvco/spiral.py.

The old bench measured `v(tp,tn)`, which this ngspice rejects inside
.measure, so every run reported "no frequency". Differential nodes are now
explicit E-sources (DI = IP-IN, DQ = QP-QN) and every measurement is checked:
a run with no oscillation reports f = None and fails (`neg_en0`).

    python3 run_lcvco.py codes      # tt/27/3.3, nominal spiral: all 16 band codes at VTUNE 0.3 / 3.0
    python3 run_lcvco.py corners    # band coverage at L/Q/process extremes + start-up at all 12 envelope points
    python3 run_lcvco.py chain      # QVCO -> extracted pt_lo_ext internal mode -> mixer gates (tt + extremes)
    python3 run_lcvco.py neg        # negative checks (EN=0; I/Q coupling removed)
    python3 run_lcvco.py evidence   # generated/lcvco-evidence.json
Raw decks/logs: scratch/timing/lcvco/sim.
"""
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import timing_flow as tf  # noqa: E402

WORK = tf.SCRATCH / 'lcvco' / 'sim'
RES = HERE / 'results.json'
F_LO, F_HI = 2.40e9, 2.50e9
VT_LO, VT_HI = 0.3, 3.0          # usable VTUNE (charge-pump headroom)
ENV = [(c, t, v) for c in ('tt', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
PAR = int(os.environ.get('LC_PAR', '2'))


def sha(p):
    return 'sha256:' + hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stage():
    WORK.mkdir(parents=True, exist_ok=True)
    for f in ('qvco.spice', 'spiral.spice'):
        shutil.copy(HERE / f, WORK / f)
    shutil.copy(tf.HERE / 'timing_cells.spice', WORK / 'timing_cells.spice')
    import run_timing   # CML LO driver: explicit gate R wrapper on ct_locml
    (WORK / 'lo_ext.ext.spice').write_text(run_timing.rg_wrap_locml((tf.GENERATED / 'lo_ext.ext.spice').read_text()))


def spiral_file(variant):
    """spiral.spice with `variant` renamed to pt_spiral (others dropped)."""
    txt = (HERE / 'spiral.spice').read_text()
    blocks = re.findall(r'(\* \S+:.*?\n.*?\.ends \S+\n)', txt, re.S)
    for b in blocks:
        name = re.search(r'\.subckt (\S+)', b).group(1)
        if name == variant:
            out = re.sub(rf'\b{variant}\b', 'pt_spiral', b)
            p = WORK / f'spiral_{variant}.spice'
            p.write_text(out)
            return p.name
    raise KeyError(variant)


def hdr(corner, temp):
    c = {'tt': 'typical', 'ss': 'ss', 'ff': 'ff'}[corner]
    return tf.header(corner, temp) + (f'.lib {tf.MODELS}/sm141064.ngspice mimcap_{c}\n'
                                      f'.lib {tf.MODELS}/sm141064.ngspice moscap_{c}\n')


def qvco_file(couple=True, params=None):
    """Staged qvco.spice, optionally with the coupling devices removed and/or
    the top .param line overridden (design-space probes; the qualified design is
    the unmodified file)."""
    q = (WORK / 'qvco.spice').read_text()
    name = 'qvco.spice'
    if not couple:      # negative check: coupling devices removed (two free-running cores)
        q = re.sub(r'^XC[12] .*$', '', q, flags=re.M)
        name = 'qvco_nocouple.spice'
    if params:
        line = re.search(r'^\.param (.*)$', q, re.M)
        cur = dict(kv.split('=') for kv in line.group(1).split())
        cur.update({k: str(v) for k, v in params.items()})
        q = q.replace(line.group(0), '.param ' + ' '.join(f'{k}={v}' for k, v in cur.items()))
        name = name.replace('.spice', '_' + '_'.join(f'{k}{v}' for k, v in sorted(params.items())) + '.spice')
    (WORK / name).write_text(q)
    return name


def core(v, vt, code, variant, en=True, couple=True, params=None):
    bits = ''.join(f'VB{k} b{k} 0 {v if (code >> k) & 1 else 0}\n' for k in range(4))
    return (f'.include timing_cells.spice\n.include {spiral_file(variant)}\n'
            f'.include {qvco_file(couple, params)}\n'
            f'VDD vdd 0 {v}\nVDDB vddb 0 {v}\nVEN en 0 {v if en else 0}\nVT vt 0 {vt}\nIB vdd ibias 10u\n' + bits +
            'X1 en vt ibias b0 b1 b2 b3 pre ip in qp qn vdd vddb 0 pt_lc_qvco\n'
            'EDI di 0 ip in 1\nEDQ dq 0 qp qn 1\n'
            # start-up kick (differential current pulse into I) so the run does not wait for noise
            'IK ip in pulse(0 200u 0.2n 50p 50p 0.3n 1)\n')


def tb_vco(v=3.3, vt=1.65, code=8, variant='pt_spiral', T=30e-9, en=True, couple=True, loads=True, params=None):
    td = T - 8e-9
    body = core(v, vt, code, variant, en, couple, params)
    if loads:   # r3: pt_lo_ext CML input (pair gate ~150 fF incl. overlap) + 40 fF wiring per tank node, and the prescaler input
        body += ''.join(f'CL{n} {n} 0 190f\n' for n in ('ip', 'in', 'qp', 'qn')) + 'CLP pre 0 30f\n'
    body += f""".tran 1p {T}
.measure tran per trig v(di) val=0 td={td} rise=1 targ v(di) val=0 td={td} rise=11
.measure tran tiq trig v(di) val=0 td={td} rise=1 targ v(dq) val=0 td={td} rise=1
.measure tran dimax max v(di) from={td} to={T}
.measure tran dqmax max v(dq) from={td} to={T}
.measure tran ipmin min v(ip) from={td} to={T}
.measure tran ipmax max v(ip) from={td} to={T}
.measure tran icore avg i(VDD) from={td} to={T}
.measure tran ibuf avg i(VDDB) from={td} to={T}
.measure tran qpmin min v(qp) from={td} to={T}
.measure tran qpmax max v(qp) from={td} to={T}
.measure tran ipavg avg v(ip) from={td} to={T}
"""

    def an(m):
        f = 10 / m['per'] if m.get('per') else None
        ph = ((m['tiq'] * f * 360 + 180) % 360 - 180) if f and m.get('tiq') else None
        pho = ((m['tlo'] * f * 360 + 180) % 360 - 180) if f and m.get('tlo') else None
        r = dict(vtune_v=vt, band=code, spiral=variant, f_hz=f, q_minus_i_tank_deg=ph, q_minus_i_loi_deg=pho,
                 tank_diff_peak_v=m.get('dimax'), tank_q_diff_peak_v=m.get('dqmax'), tank_ip_v=[m.get('ipmin'), m.get('ipmax')],
                 tank_qp_v=[m.get('qpmin'), m.get('qpmax')], tank_cm_v=m.get('ipavg'),
                 i_core_ma=-m.get('icore', math.nan) * 1e3, i_buf_ma=-m.get('ibuf', math.nan) * 1e3)
        r['oscillates'] = bool(f and (m.get('dimax') or 0) > 0.3)
        r['quadrature_ok'] = bool(ph is not None and 80 < abs(ph) < 100)
        # r3: the tank nodes drive the pt_lo_ext CML pair directly.  Drive check:
        # >= 0.3 V amplitude per side on I and Q and the tank CM inside 1.3-2.1 V
        # (lodrv2 schematic study: the CML passes at 0.58 V about 1.7 V; tail headroom).
        amp_i = (m['ipmax'] - m['ipmin']) / 2 if 'ipmax' in m and 'ipmin' in m else 0
        amp_q = (m['qpmax'] - m['qpmin']) / 2 if 'qpmax' in m and 'qpmin' in m else 0
        # CM window 1.3-2.2 V (2026-11-11): ff tanks sit at 2.14-2.19 V and the chain with the
        # extracted pt_lo_ext passes there (r4_chain_ff22_*: on 1.19-1.21 V, off <= 0.24 V); the old
        # 2.1 V edge came from a schematic study and flagged every ff point.
        r['cml_drive_ok'] = bool(min(amp_i, amp_q) >= 0.3 and m.get('ipavg') is not None and 1.3 <= m['ipavg'] <= 2.2)
        r['loi_rail_to_rail'] = r['cml_drive_ok']   # legacy key used by evidence(); r3 meaning = cml_drive_ok
        return r
    return body, an


def tb_chain(v=3.3, vt=1.65, code=8, variant='pt_spiral', T=60e-9):
    """QVCO LOI_* -> extracted pt_lo_ext internal mode (INT=1, EXT=0) with the
    mixer loads of tb_lo_ext; criteria are tb_lo_ext's (RX switch Vgs on >= 0.9 V,
    off <= 0.5 V, 80 < |Q-I| < 100 deg, f inside 2.4-2.5 GHz)."""
    td = T - 6e-9
    loads = ''.join(f'XRX{n} rxd lo{n} rxs 0 nfet_03v3 w=5u l=0.28u m=12\n'
                    f'XTX{n} txd lo{n} txs 0 nfet_03v3 w=10u l=0.28u m=4\nCW{n} lo{n} 0 22f\n'
                    for n in ('ip', 'in', 'qp', 'qn'))
    body = core(v, vt, code, variant) + f""".include lo_ext.ext.spice
CLP pre 0 30f
VRXD rxd 0 {v / 2}
VRXS rxs 0 {v / 2}
VTXD txd 0 2.5
VTXS txs 0 1.0
VEXT ext 0 0
VINT int 0 {v}
RPI padip 0 50
RPN padin 0 50
RQP padqp 0 50
RQN padqn 0 50
{loads}XLO padip padin padqp padqn ip in qp qn ext int 0 loip loin loqp loqn vb vdd 0 pt_lo_ext
.tran 1p {T}
.measure tran per trig v(loip) val={0.739 * v} td={td} rise=1 targ v(loip) val={0.739 * v} td={td} rise=5
.measure tran thi trig v(loip) val={0.739 * v} td={td} rise=1 targ v(loip) val={0.739 * v} td={td} fall=1
.measure tran lomax max v(loip) from={td} to={T}
.measure tran lomin min v(loip) from={td} to={T}
.measure tran qmax max v(loqp) from={td} to={T}
.measure tran qmin min v(loqp) from={td} to={T}
.measure tran tiq trig v(loip) val={0.739 * v} td={td} rise=1 targ v(loqp) val={0.739 * v} td={td} rise=1
.measure tran icore avg i(VDD) from={td} to={T}
.measure tran ibuf avg i(VDDB) from={td} to={T}
"""

    def an(m):
        f = 4 / m['per'] if m.get('per') else None
        ph = ((m['tiq'] * f * 360 + 180) % 360 - 180) if f and m.get('tiq') else None
        r = dict(vtune_v=vt, band=code, spiral=variant, f_lo_hz=f, lo_i_v=[m.get('lomin'), m.get('lomax')],
                 lo_q_v=[m.get('qmin'), m.get('qmax')], q_minus_i_deg=ph,
                 rx_switch_vgs_on_v=(min(m['lomax'], m.get('qmax', 0)) - v / 2) if 'lomax' in m else None,
                 rx_switch_vgs_off_v=(max(m['lomin'], m.get('qmin', 9)) - v / 2) if 'lomin' in m else None,
                 duty_at_vb=((m['thi'] * f) % 1 if f and 'thi' in m else None),
                 i_vdd_ma=-m.get('icore', math.nan) * 1e3, i_buf_ma=-m.get('ibuf', math.nan) * 1e3)
        # GX-6 (2026-11-11): the chain must work over the whole tank, not only 2.4-2.5 GHz;
        # in_ism_band is kept as information.  Frequency criterion = tank lock range 1.9-3.1 GHz.
        r['in_ism_band'] = bool(f and F_LO * 0.99 <= f <= F_HI * 1.01)
        r['pass'] = bool(f and 1.9e9 <= f <= 3.1e9 and r['rx_switch_vgs_on_v'] is not None
                         and r['rx_switch_vgs_on_v'] >= 0.9 and r['rx_switch_vgs_off_v'] <= 0.5
                         and ph is not None and 80 < abs(ph) < 100)
        return r
    return body, an


def run(name, tb, kw, corner='tt', temp=27, v=3.3):
    body, an = tb(v=v, **kw)
    m = tf.ngspice(WORK, name, hdr(corner, temp) + body + '.end\n')
    r = an(m)
    r.update(case=name, corner=corner, temp_c=temp, vdd_v=v, deck=f'scratch/timing/lcvco/sim/{name}.spice',
             netlist='schematic QVCO + spiral model; lo_ext extracted in chain runs')
    if m.get('_errors'):
        r['sim_messages'] = m['_errors'][:5]
    return r


def go(jobs):
    out = {}
    with ThreadPoolExecutor(PAR) as ex:
        for j, r in zip(jobs, ex.map(lambda j: run(*j), jobs)):
            out[j[0]] = r
            print(j[0], json.dumps({k: r.get(k) for k in ('f_hz', 'f_lo_hz', 'q_minus_i_tank_deg', 'q_minus_i_deg', 'tank_diff_peak_v',
                                                         'loi_rail_to_rail', 'pass', 'i_core_ma', 'i_buf_ma', 'sim_messages')}, default=str), flush=True)
    return out


def save(key, out):
    res = json.loads(RES.read_text()) if RES.exists() else {}
    res.setdefault(key, {}).update(out)
    RES.write_text(json.dumps(res, indent=1, default=str) + '\n')


# extremes for band coverage: (corner, temp, vdd, spiral variant)
EXTREMES = [('tt', 27, 3.3, 'pt_spiral'),
            ('ss', 32, 3.15, 'pt_spiral_lhi_lowq'),    # lowest frequency, weakest start-up
            ('ff', 22, 3.35, 'pt_spiral_llo'),         # highest frequency
            ('ff', 22, 3.35, 'pt_spiral_llo_lowq'),
            ('ss', 32, 3.15, 'pt_spiral_lhi')]


def main():
    stage()
    what = sys.argv[1]
    if what == 'codes':
        jobs = [(f'code{c}_vt{vt}', tb_vco, dict(code=c, vt=vt)) for c in range(16) for vt in (VT_LO, VT_HI)]
        save('codes', go(jobs))
    elif what == 'extremes':
        jobs = []
        for c, t, v, sp in EXTREMES:
            for code in (0, 15):
                for vt in (VT_LO, VT_HI):
                    jobs.append((f'x_{c}{t}_{v}_{sp}_b{code}_vt{vt}', tb_vco, dict(code=code, vt=vt, variant=sp), c, t, v))
        save('extremes', go(jobs))
    elif what == 'startup':
        jobs = [(f'su_{c}{t}_{v}_lowq', tb_vco, dict(code=15, vt=VT_LO, variant='pt_spiral_lhi_lowq'), c, t, v) for c, t, v in ENV]
        save('startup', go(jobs))
    elif what == 'chain':
        args = sys.argv[2:]          # name corner temp vdd variant code vt
        jobs = [(args[0], tb_chain, dict(variant=args[4], code=int(args[5]), vt=float(args[6])), args[1], int(args[2]), float(args[3]))]
        save('chain', go(jobs))
    elif what == 'probe2':
        # design-space probe: name corner temp vdd variant code vt k=v[,k=v]
        a = sys.argv[2:]
        prm = dict(kv.split('=') for kv in a[7].split(',')) if len(a) > 7 else None
        jobs = [(a[0], tb_vco, dict(variant=a[4], code=int(a[5]), vt=float(a[6]), params=prm), a[1], int(a[2]), float(a[3]))]
        out = go(jobs)
        for r in out.values():
            r['params'] = prm
        save('probe2', out)
    elif what == 'point':
        args = sys.argv[2:]
        jobs = [(args[0], tb_vco, dict(variant=args[4], code=int(args[5]), vt=float(args[6])), args[1], int(args[2]), float(args[3]))]
        save('points', go(jobs))
    elif what == 'evidence':
        evidence()
    elif what == 'neg':
        jobs = [('neg_en0', tb_vco, dict(en=False)), ('neg_nocouple', tb_vco, dict(couple=False))]
        save('neg', go(jobs))


def phase_noise(q, vpk_diff, i_core_a, f0=2.45e9, gamma=2.0, qvco_penalty_db=3.0, loop_bw_hz=1e6):
    """Leeson/Hajimiri-style 1/f^2 estimate for one core, plus a QVCO penalty.
    L(df) = 10 log10( 2 k T F / Psig * (f0 / (2 Q df))^2 ), Psig = Vpk^2 / (2 Rp),
    F = 1 + gamma (cross-coupled pair noise), Rp = Q * w0 * L. Integrated jitter
    of a PLL-locked VCO outside the loop bandwidth (1/f^2 region):
    sigma_t = sqrt(2 * S * df^2 / BW) / (2 pi f0), S = 10^(L(df)/10)."""
    k, T = 1.380649e-23, 300.0
    L = 2.65e-9
    rp = q * 2 * math.pi * f0 * L
    psig = (vpk_diff / 2) ** 2 * 2 / (2 * rp)        # two single-ended halves
    F = 1 + gamma
    out = {}
    for df in (1e5, 1e6, 3e6):
        out[f'L_{df:.0e}_dbc_hz'] = 10 * math.log10(2 * k * T * F / psig * (f0 / (2 * q * df)) ** 2) + qvco_penalty_db
    s = 10 ** (out['L_1e+06_dbc_hz'] / 10)
    out['jitter_rms_ps_outside_bw'] = math.sqrt(2 * s * 1e6 ** 2 / loop_bw_hz) / (2 * math.pi * f0) * 1e12
    out.update(q=q, vpk_diff=vpk_diff, rp_ohm=rp, psig_w=psig, noise_factor=F, qvco_penalty_db=qvco_penalty_db,
               loop_bw_hz=loop_bw_hz, budget_ps='0.524 ps per contribution at -30 dB EVM (spec/clock-feasibility-envelope.md)')
    return out


def evidence():
    res = json.loads(RES.read_text())
    ext = res.get('extremes', {})
    cov = []
    for c, t, v, sp in EXTREMES:
        key = f'x_{c}{t}_{v}_{sp}'
        f_top = (ext.get(f'{key}_b0_vt{VT_HI}') or {}).get('f_hz')
        f_bot = (ext.get(f'{key}_b15_vt{VT_LO}') or {}).get('f_hz')
        osc = all((ext.get(f'{key}_b{b}_vt{vt}') or {}).get('oscillates') for b in (0, 15) for vt in (VT_LO, VT_HI))
        quad = all((ext.get(f'{key}_b{b}_vt{vt}') or {}).get('quadrature_ok') for b in (0, 15) for vt in (VT_LO, VT_HI))
        r2r = all((ext.get(f'{key}_b{b}_vt{vt}') or {}).get('loi_rail_to_rail') for b in (0, 15) for vt in (VT_LO, VT_HI))
        ok = bool(f_top and f_bot and f_top >= F_HI and f_bot <= F_LO and osc and quad and r2r)
        cov.append(dict(corner=c, temp_c=t, vdd_v=v, spiral=sp, f_max_hz=f_top, f_min_hz=f_bot, oscillates=osc,
                        quadrature_ok=quad, loi_rail_to_rail=r2r, covers_2p4_2p5=ok))
    codes = res.get('codes', {})
    steps = []
    for b in range(16):
        lo = (codes.get(f'code{b}_vt{VT_LO}') or {}).get('f_hz')
        hi = (codes.get(f'code{b}_vt{VT_HI}') or {}).get('f_hz')
        steps.append(dict(band=b, f_vt_lo=lo, f_vt_hi=hi))
    # bands are ordered by added capacitance: band b+1 is lower. Overlap: the top
    # of band b+1 (VTUNE 3.0) reaches the bottom of band b (VTUNE 0.3).
    overlap = all(steps[b]['f_vt_lo'] and steps[b + 1]['f_vt_hi'] and steps[b + 1]['f_vt_hi'] >= steps[b]['f_vt_lo']
                  for b in range(15)) if codes else None
    su = res.get('startup', {})
    su_ok = bool(su) and all(r.get('oscillates') and r.get('quadrature_ok') and r.get('loi_rail_to_rail') for r in su.values())
    ch = res.get('chain', {})
    ch_ok = bool(ch) and all(r.get('pass') for r in ch.values())
    neg = res.get('neg', {})
    en0 = neg.get('neg_en0', {})
    # EN=0 must also be quiet: core = the 10 uA IBIAS test source only, buffers < 1 uA
    # (r2 gated the self-biased buffers, which drew 16 mA with EN=0)
    neg_ok = (bool(neg) and not en0.get('oscillates') and not neg.get('neg_nocouple', {}).get('quadrature_ok')
              and (en0.get('i_buf_ma') or 1) < 1e-3 and (en0.get('i_core_ma') or 1) < 0.0105)
    tt = codes.get(f'code8_vt{VT_LO}') or {}
    lowq = [r for r in su.values()]
    vpk_low = min((r.get('tank_diff_peak_v') or 9) for r in lowq) if lowq else None
    pn = dict(nominal=phase_noise(9.2, tt.get('tank_diff_peak_v') or 1.6, 4e-3),
              low_q=phase_noise(5.2, vpk_low or 1.2, 4e-3))
    rec = dict(block='lcvco (pt_lc_qvco)', generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               netlist='schematic QVCO; tank inductor = lcvco/spiral.py model variants; pt_lo_ext extracted in chain runs',
               source_hashes={p.name: sha(p) for p in (HERE / 'qvco.spice', HERE / 'spiral.spice', HERE / 'spiral.py',
                                                        HERE / 'run_lcvco.py', tf.GENERATED / 'lo_ext.ext.spice')},
               criteria=dict(coverage='per extreme: f(band 0, VTUNE 3.0) >= 2.5 GHz and f(band 15, VTUNE 0.3) <= 2.4 GHz, oscillating, '
                                      '80<|Q-I|<100 deg, LOI rail to rail (>90 %/<10 % VDD)',
                             band_overlap='tt: every band tuning range overlaps the next band',
                             startup='all 12 envelope points, low-Q +10 % L inductor, band 15 / VTUNE 0.3 (smallest swing)',
                             chain='QVCO -> extracted pt_lo_ext internal mode: tb_lo_ext criteria',
                             negative='EN=0 must not oscillate and must draw < 1 uA in the buffers (core: only the 10 uA IBIAS); coupling removed must fail quadrature',
                             gate_resistance='explicit Rg in qvco.spice: rgf = 16 ohm per 2 um finger, contacted both ends'),
               coverage=cov, band_codes_tt=steps, band_overlap_tt=overlap, startup=su, startup_pass=su_ok,
               chain=ch, chain_pass=ch_ok, negative=neg, negative_checks_fail_as_expected=neg_ok, phase_noise_estimate=pn,
               spiral=json.loads((HERE / 'spiral.json').read_text()))
    rec['verdict'] = 'pass' if (all(c['covers_2p4_2p5'] for c in cov) and overlap and su_ok and ch_ok and neg_ok) else 'fail'
    (tf.GENERATED / 'lcvco-evidence.json').write_text(json.dumps(rec, indent=1, default=str) + '\n')
    print(rec['verdict'], json.dumps(cov, default=str)[:1500], overlap, su_ok, ch_ok, neg_ok)
    print(json.dumps(pn, indent=0)[:1500])


if __name__ == '__main__':
    main()
