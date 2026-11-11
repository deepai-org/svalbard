"""Schematic bench of the half-rate CMOS 2:1 (wtx_omux2) + CML final 2:1 (wtx_cml2), quarter-rate timing.

Ring phases (tanh, 150 ohm) -> per-phase CMOS buffer (INV4 -> INV16, as the core's QW drivers) -> QW k.
Streams F k (inverted data, as the core's sreg5 streams) are ideal 50 ps edges launched at
C(k+2) + tcq (tcq swept: the core's extracted clock-to-Q spans ~0.1-1.8 UI over rates/corners).
Gate resistance is added to every CML device (cml_ser.add_gate_r).  Y / YB / DP / DPB decoded as in
sim_core.

    python3 sim_cml.py --rate 3.24e9 --corner ss --temp 22 --vdd 3.15 --tcq 0.55e-9
"""
import argparse
import json
from pathlib import Path

import numpy as np

import cml_ser
import serq4_macro as M
import sim_wiredtx as S
import tools


def res_lib(corner):
    return {'ss': 'res_ss', 'ff': 'res_ff'}.get(corner, 'res_typical')


WIRE_SKIP = {'VDD', 'VSS', 'NB', 'RT', 'ENB', 'EN'}
WIRE_X2 = {'KP', 'KPB'}       # pre-driver output fans out to the four clock drivers
# converter-internal nets (level shifter -> converter pair -> CMOS inverters): abutted cells, local wiring
WIRE_LOCAL = {f'{o}{s}' for o in ('Y', 'YB', 'DP', 'DPB') for s in ('U', 'V')} | {'YCS', 'YCBS', 'DCS', 'DCBS'}
WIRE_LOCAL_FF = 10.0


def add_wire_c(text, c_ff):
    """Pre-layout parasitic estimate: c_ff (fF) of grounded wire capacitance on every signal net of
    wtx_cml2 (2x on the pre-driver output KP/KPB), placed inside the subckt before .ends."""
    nets = set()
    body = text[text.index('.subckt wtx_cml2'):text.index('.ends wtx_cml2')]
    for l in body.splitlines()[1:]:
        tk = l.split()
        if not tk or not tk[0][0] in 'XR':
            continue
        for x in tk[1:]:
            if '=' in x or x.startswith(('wtx_', 'nfet', 'pfet', 'ppolyf')) or x.startswith('rg_'):
                continue
            nets.add(x)
    nets -= WIRE_SKIP
    val = lambda n: min(c_ff, WIRE_LOCAL_FF) if n in WIRE_LOCAL else c_ff * (2 if n in WIRE_X2 else 1)
    cl = [f'CW_{n} {n} VSS {val(n):g}f' for n in sorted(nets)]
    return text.replace('.ends wtx_cml2', '\n'.join(cl) + '\n.ends wtx_cml2')


def deck(*, rate, corner, temp, vdd, tcq, bits, tstop, rcorner=None, rg=True, load_f=20e-15, wirec=0.0):
    ui = 1 / rate
    T = 4 * ui
    tr = min(50e-12, T / 16)
    cml = cml_ser.spice()
    if rg:
        cml = cml_ser.add_gate_r(cml)
    if wirec:
        cml = add_wire_c(cml, wirec)
    _, _, onet = M.omux2()
    _, _, i4 = M.row_of('b4', [('a', 'INV4', 'A', 'AN'), ('b', 'INV16', 'AN', 'Y')], ['A', 'Y'])
    L = ['* omux2 + cml2 bench', tools.model_header(corner, temp),
         *([f'.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice {res_lib(rcorner)}'] if rcorner else []),
         cml, M.subckt('wtx_omux2', M.omux2()[1], onet), M.subckt('phbuf', ['A', 'Y', 'VDD', 'VSS'], i4),
         f'VDD VDD 0 {vdd}', 'VSS VSS 0 0', f'VEN EN 0 PWL(0 0 0.5n 0 0.6n {vdd})']
    t0 = 2e-9
    for k in range(4):
        kk = 2.197 / tr
        p_ = f'(time-{t0 + k * ui + tr / 2:.6e})'
        L.append(f'BPH{k} PH{k}_drv 0 V={vdd}*(0.5+0.5*tanh({kk * T / (2 * np.pi):.6e}'
                 f'*sin(2*3.141592653589793*{p_}/{T:.6e})))')
        L.append(f'RPH{k} PH{k}_drv PH{k} {S.R_PHASE:g}')
        L.append(f'XB{k} PH{k} QW{k} VDD VSS phbuf')
    nper = len(bits) // 4
    for k in range(4):
        # F k carries NOT(bit 4m+k); changes at C(k+2) + tcq of period m-1 (shows bit 4m+k in window 4m+k+2.. )
        tv = [(0.0, 1 - bits[k])]
        for m in range(nper):
            tv.append((t0 + (k + 2) * ui + (m - 1) * T + tcq, 1 - bits[4 * m + k]))
        L.append(S.pwl_bits(f'F{k}', f'F{k}', tv, vdd))
    L.append('XO QW0 QW1 QW2 QW3 F0 F1 F2 F3 E EB O OB VDD VSS wtx_omux2')
    L.append('XC E EB O OB QW0 QW1 QW2 QW3 EN Y YB DP DPB VDD VSS wtx_cml2')
    for o in ('Y', 'YB', 'DP', 'DPB'):
        L.append(f'C{o} {o} 0 {load_f}')
    probes = ['Y', 'YB', 'DP', 'DPB', 'E', 'O', 'xc.KX', 'xc.KXB', 'xc.P0', 'xc.P2', 'xc.CKE', 'xc.YC', 'xc.YCB', 'xc.NB', 'xc.CKBE', 'xc.EF', 'xc.EFB', 'xc.OF', 'xc.OFB', 'xc.YU', 'xc.YCS']
    import os
    probes += [x for x in os.environ.get('CML_PROBES', '').split(',') if x]    # debug: extra internal nets
    vecs = ' '.join(f'v({p})' for p in probes) + ' i(VDD)'
    L += ['.options reltol=1e-3 method=gear', f'.tran 5e-12 {tstop:.6e} 0 4e-12', '.control', f'save {vecs}',
          'set wr_singlescale', 'run', 'wrdata wave.txt ' + vecs, '.endc', '.end']
    return '\n'.join(L) + '\n', probes + ['I_VDD']


def run(work, *, rate, corner='typical', temp=27, vdd=3.3, tcq=0.4e-9, nbits=160, rcorner=None, rg=True, wirec=0.0):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    bits = S.prbs7_bits(nbits)
    ui = 1 / rate
    tstop = 2e-9 + (nbits + 6) * ui
    d, names = deck(rate=rate, corner=corner, temp=temp, vdd=vdd, tcq=tcq, bits=bits, tstop=tstop,
                    rcorner=rcorner, rg=rg, wirec=wirec)
    (work / 'tb.sp').write_text(d)
    _, log = tools.ngspice(work, 'tb.sp')
    ab = S.sim_abort(log)
    if ab:
        return dict(ok=False, reason=ab)
    w = tools.read_wrdata(work / 'wave.txt', names)
    ta, tb_ = 2e-9 + 12 * ui, tstop - 3 * ui
    res = dict(rate=rate, corner=corner, rcorner=rcorner or corner, temp=temp, vdd=vdd, tcq_s=tcq, rg=rg, wire_c_ff=wirec)
    for node, inv in (('Y', False), ('YB', True), ('DP', False), ('DPB', True)):
        dd = S.decode(w, node, rate, ta, tb_)
        if dd is None:
            res[node] = dict(ok=False, reason='no transitions')
            continue
        b = 1 - dd['bits'] if inv else dd['bits']
        lat, err = S.align(b, bits)
        res[node] = dict(bits=int(len(b)), errors=int(err), latency=int(lat),
                         jitter_pp_ps=round(dd['jitter_pp'] * 1e12, 1),
                         eye_width_ps=round(dd['eye_width_est'] * 1e12, 1), vmargin_v=round(dd['vertical_margin'], 3))
    res['idd_avg_a'] = float(-np.mean(w['I_VDD'][w['time'] > ta]))
    ck = w['xc.CKE']
    res['ck_swing_v'] = round(float(np.percentile(ck[w['time'] > ta], 98) - np.percentile(ck[w['time'] > ta], 2)), 3)
    res['ok'] = all(res.get(n, {}).get('errors', 1) == 0 for n in ('Y', 'YB', 'DP', 'DPB')) and \
        res['DP'].get('latency', -9) == res['Y'].get('latency', -9) - 1
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--rate', type=float, default=3.24e9)
    ap.add_argument('--corner', default='typical')
    ap.add_argument('--rcorner', default=None)
    ap.add_argument('--temp', type=float, default=27)
    ap.add_argument('--vdd', type=float, default=3.3)
    ap.add_argument('--tcq', type=float, default=0.4e-9)
    ap.add_argument('--nbits', type=int, default=160)
    ap.add_argument('--norg', action='store_true')
    ap.add_argument('--tag', default=None)
    ap.add_argument('--wirec', type=float, default=0.0, help='pre-layout wire C per CML net (fF)')
    a = ap.parse_args()
    tag = a.tag or f'cml_{a.rate / 1e9:g}_{a.corner}_{a.rcorner or a.corner}_{a.temp:g}_{a.vdd:g}_{a.tcq * 1e12:.0f}' + (f'_w{a.wirec:g}' if a.wirec else '')
    r = run(tools.SCRATCH / 'cml' / tag, rate=a.rate, corner=a.corner, temp=a.temp, vdd=a.vdd, tcq=a.tcq,
            nbits=a.nbits, rcorner=a.rcorner, rg=not a.norg, wirec=a.wirec)
    print(json.dumps(r))
    (tools.SCRATCH / 'cml' / f'{tag}.json').write_text(json.dumps(r, indent=1))
