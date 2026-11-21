"""Code x corner sweep on the bias-path bench (cheap): the pad (RT or C, termination OFF) with its tails biased by the block's
tail DACs (schematic wtx8_aux + 2 x wtx_idac2m from net/pt_wiredtx8.spice, the s16 snapshot, 10 uA IBIAS), the pad gates driven by
ideal 2.5 Gb/s sources at the block's measured output levels (full-chain anchor), POST = MAIN one core bit later, same sign
(POST_POL 1) or inverted (POL 0), and the same board (net100) and stream (stream.py) as the anchor.

    python3 sweep.py '{"tag":..,"corner":"ss","pess":true,"vdd":3.15,"code":255,"pad_model":"RT","gate":[lo,hi]}'
"""
import sys, json, time, re
from pathlib import Path
import numpy as np
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parent))
import chain16
from chain14 import C13
from chain13 import tools, CH, B, B4, I
import net100, stream, anchor

NETS = H.parent / 'net' / 'pt_wiredtx8.spice'
RES = H / 'results'; RUNS = H / 'runs'


def aux_text():
    t = NETS.read_text()
    blk = [re.search(rf'^\.subckt {n} .*?^\.ends {n}\s*$', t, re.S | re.M).group(0) for n in ('wtx_inv1', 'wtx_idac2m', 'wtx8_aux')]
    return '\n'.join(blk) + '\n'


def deck(w, *, corner, temp, vdd, pess, code, post_code, pol, pad_model, gate, sy, rate, vct, tr=50e-12):
    res = {'ss': 'ss', 'ff': 'ff'}.get(corner, 'typical')
    L = ['* fe100 bias-path bench', CH.pad_header(corner, temp, res), '.include aux.spice', '.include pad.spice']
    at = aux_text(); pt = B.clean(C13.PADFILE[pad_model].read_text())
    if pess:
        at, pt = B4.pess_all(at), B4.pess_all(pt)
    (w / 'aux.spice').write_text(at); (w / 'pad.spice').write_text(pt + '\n')
    L += [f'VDD VDD 0 {vdd}', 'VSS VSS 0 0', 'IB VDD IBIAS 10u']
    st = dict(SER_EN=1, IDLE=0, IDLE_MODE=0, WTX_EXT=0, DX=0, EN_MAIN=1, EN_POST=1, ISLAND_OFF=0, TAP_EN=0, INP=0, INN=0)
    L += [f'V{n} {n} 0 {vdd * v}' for n, v in st.items()]
    L += [f'VMC{i} MAIN_CODE{i} 0 {vdd * (code >> i & 1)}' for i in range(8)] + [f'VPC{i} POST_CODE{i} 0 {vdd * (post_code >> i & 1)}' for i in range(8)]
    L.append('XAUX SER_EN IDLE IDLE_MODE WTX_EXT DX EN_MAIN EN_POST ISLAND_OFF TAP_EN IBIAS ' + ' '.join(f'MAIN_CODE{i}' for i in range(8)) + ' '
             + ' '.join(f'POST_CODE{i}' for i in range(8)) + ' INP INN SERQ ENM EXT OVP OVN ENMAIN_G ENPOST_G MAIN_BIAS POST_BIAS TAP_P TAP_N '
             'WTX_EXT_DATA ATB_NBIAS ATB_PBIAS VDD VSS wtx8_aux')
    bits = stream.core_bits(sy, anchor.N); ui = 1 / rate; t0 = 3e-9
    post = [1 - bits[0]] + bits[:-1]     # POST starts opposite to MAIN: cancelled (0) state at the operating point, no DC in the magnetics
    if not pol:
        post = [1 - b for b in post]
    lo, hi = gate
    for nm, seq, inv in (('MAIN_N', bits, 0), ('MAIN_P', bits, 1), ('POST_N', post, 0), ('POST_P', post, 1)):
        # before t0 both legs of each bank on at mid level? no: start in the level of bit 0
        pts = ['0', f'{(hi if seq[0] ^ inv else lo):g}']; prev = seq[0] ^ inv
        for k, b in enumerate(seq):
            b ^= inv
            if b != prev:
                tk = t0 + k * ui
                pts += [f'{tk:.5e}', f'{(hi if prev else lo):g}', f'{tk + tr:.5e}', f'{(hi if b else lo):g}']; prev = b
        pr = [f'{pts[i]} {pts[i + 1]}' for i in range(0, len(pts), 2)]
        L.append(f'V{nm} {nm}_s 0 PWL(' + pr[0]); L += ['+ ' + ' '.join(pr[i:i + 6]) for i in range(1, len(pr), 6)]; L.append('+ )'); L.append(f'R{nm} {nm}_s {nm} 20'); L.append(f'C{nm} {nm} VSS 120f')
    L += [f'VCAS CAS_SRC 0 {vdd}', 'RCAS CAS_SRC CASCODE 50', 'VTB PTMDS_BIAS 0 0', 'VTP TMDS_P 0 0', 'VTN TMDS_N 0 0', 'VDE2 DETECT_ENABLE 0 0',
          f'VDP DETECT_PBIAS 0 {vdd}', 'VTE TERM_ENABLE 0 0', 'VTV TERM_VCM 0 1.65',
          'XPAD PAD_P PAD_N VDD VSS CASCODE MAIN_P MAIN_N MAIN_BIAS POST_P POST_N POST_BIAS TMDS_P TMDS_N PTMDS_BIAS '
          'DETECT_ENABLE DETECT_PBIAS TERM_ENABLE TERM_VCM ATBPAD tx_protected_pad', 'RATB ATBPAD 0 1meg']
    pk = []
    anchor._pkg(pk, 'P4', 0.0)
    for i, l in enumerate(pk):
        if l.startswith('LBW'):
            p = l.split(); pk[i] = f'{p[0]} {p[1]} {p[2]} {CH.BOND["pess"]:.4g}'
    pk = [l if not l.startswith('VCT') else f'VCT CT 0 {vct}' for l in pk]
    L += pk
    tstop = t0 + len(bits) * ui + 2e-9
    names = ['PAD_P', 'PAD_N', 'RJ_P', 'RJ_N', 'MAIN_BIAS', 'POST_BIAS', 'SUMP0', 'SUMN0']
    vecs = ' '.join(f'v({n})' for n in names[:6]) + ' v(xpad.xphysical.sum_p_d_0) v(xpad.xphysical.sum_n_d_0)' + ' i(VDD) i(VILP) i(VILN)'
    L += ['.options reltol=1e-3 method=gear interp rshunt=1e10', f'.tran 1.0e-11 {tstop:.6e} 0 10e-12', '.control', f'save {vecs}',
          'set wr_singlescale', 'run', f'wrdata wave.txt {vecs}', '.endc', '.end']
    (w / 'tb.sp').write_text('\n'.join(L) + '\n')
    return names + ['I', 'ILP', 'ILN'], t0


def run(tag, corner='ss', pess=False, vdd=3.15, code=255, post_code=None, pol=1, pad_model='RT', gate=(0.0, 3.15), nsym=26, vct=3.3):
    post_code = code if post_code is None else post_code
    temp = anchor.TEMP[corner]; rate = anchor.RATE
    sy = stream.mlt3(anchor.START + nsym)[anchor.START:]
    w = RUNS / tag; w.mkdir(parents=True, exist_ok=True)
    names, t0 = deck(w, corner=corner, temp=temp, vdd=vdd, pess=pess, code=code, post_code=post_code, pol=pol, pad_model=pad_model,
                     gate=gate, sy=sy, rate=rate, vct=vct)
    ts0 = time.time(); tools.ngspice_host(w, 'tb.sp', timeout=20000)
    out = dict(tag=tag, bench='bias-path (schematic aux DAC + pad + ideal gate drive)', aux=str(NETS), corner=corner, pess=pess, temp=temp, vdd=vdd,
               vct=vct, main_code=code, post_code=post_code, post_pol=pol, pad=C13.PADLABEL[pad_model], gate_v=list(gate), core_rate=rate,
               n=anchor.N, board=net100.LABEL, sec=round(time.time() - ts0))
    if (w / 'wave.txt').exists():
        a = tools.read_wrdata(w / 'wave.txt', names)
        a['t_score'] = t0 + 6 * anchor.N / rate     # same scored symbols as the anchor (from symbol 6)
        out['meas'] = anchor.measure(a['time'], a, sy, anchor.N / rate, t0, vdd); out['ok'] = True
    else:
        out.update(ok=False, reason='no waveform')
    for f_ in w.glob('*'):
        if f_.name not in ('tb.sp', 'tb.sp.log'):
            f_.unlink()
    RES.mkdir(exist_ok=True); (RES / f'{tag}.json').write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == '__main__':
    o = run(**json.loads(sys.argv[1]))
    m = o.get('meas', {})
    print(o['tag'], o.get('sec'), m.get('amp_mv'), m.get('symmetry'), m.get('ILP'), m.get('ILN'), m.get('pad_min_v'), flush=True)
