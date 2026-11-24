"""r11 bench B: capture with the REAL sampler bank and REAL clocks (run through ../../slot.sh; host ngspice).
Ring replay (r11/ring/ph_*.npz) -> extracted pt_ptrim (trim codes from clk.json) -> CKP0..7 -> extracted pt_slicer + extracted
pt_wrx_cap r7e (+ 30 fF route and 20 fF wordclk load).  SL: ideal differential PRBS7, 120 mVppd at the corner's SL common mode,
25 ohm / 50 fF, bit boundaries 0.25 UI before the mean edge-sampler instant (capture.bench convention: edge words deterministic,
every transition votes UP).  LDE: ideal one-period pulse per word, lde_delay after the ACTUAL CKP0 rise at the capture pin.
Judged by capture.bench's own analysis (DW / EW words, votes, WSTB).
  rb11.py <ck> <rate> [rcs=0|1] [psel=N] [words=N] [neg=s2] [cap=PATH] [codes=auto|0] [vd=0.12]      -> capb.json"""
import sys, json, re, time
from pathlib import Path
import numpy as np
import rc11
from rc11 import L, H, MODE
W = L.W
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r10cap')
import stagee            # points capture at the r7e staging directory
import capture
CAP = Path('/home/ubuntu/svalbard/scratch/wired_rx/r10cap/r7e/gen/wrx_cap.ext.spice')
MIN_BITS = {4: 150, 2: 120, 1: 60}


def run(ck, rate, rcs=0, psel=0, words=None, neg=None, cap=CAP, codes='auto', vd=0.12, lde_delay=0.3e-9):
    c, temp, vdd, bound = L.CORN[ck]
    mode, fring, bpc = MODE[rate]
    key = f'{ck}_{rate:g}G_r{rcs}' + (f'_p{psel}' if bpc == 1 else '') + ('' if codes == 'auto' else f'_codes{codes}') + (f'_neg{neg}' if neg else '') + (f'_lde{lde_delay * 1e12:.0f}' if lde_delay != 0.3e-9 else '') + ('' if cap == CAP else '_' + Path(cap).parent.parent.name)
    if key in rc11.jload('capb.json') and 'bit_errors' in rc11.jload('capb.json')[key]: return
    L.RUN = H / 'run'; L.RUN.mkdir(exist_ok=True)
    words = words or {4: 12, 2: 12, 1: 6}[bpc]
    P = 1e-6 / fring; ui = P / bpc
    ap = rc11.jload('aperture.json')[ck]; A = np.array(ap['A_ps']) * 1e-12
    cinfo = rc11.solve_codes(ck, fring)
    if codes == 'auto': tcodes = cinfo['codes']; cdelay = np.array([x['delay_ps'] for x in cinfo['trimmed']]) * 1e-12
    else: tcodes = [int(codes)] * 8; cdelay = np.array([x['delay_ps'] for x in cinfo['code0']]) * 1e-12
    body, ctl, an = capture.bench(bpc, f=fring * 1e6, words=words, corner=c, temp=temp, vdd=vdd, rcs=rcs, psel=psel, lde_delay=lde_delay)
    t0 = 2e-9                                   # capture.bench: ideal CKP0 rises at t0 + n*P ; make the ACTUAL CKP0 do that
    tph = t0 - cdelay[0]
    while tph < 0.3e-9: tph += P
    keep = [l for l in body.splitlines() if not re.match(r'(VS\d|VCK\d|VDD) ', l)]
    cl, P_, vring = rc11.clock_lines(ck, fring, tcodes, real_slicer=True, real_capture=True, t0=tph)
    cl = [re.sub(r'\bck(\d)\b', r'ckp\1', x) for x in cl]
    # sampler instants relative to t0 (CKP0's own rise = 0)
    inst = np.arange(8) * P / 8 + (cdelay - cdelay[0]) + A
    dj = {4: [0, 2, 4, 6], 2: [0, 4], 1: [psel]}[bpc]
    ej = {4: [1, 3, 5, 7], 2: [2, 6], 1: [(psel + 4) % 8]}[bpc]
    # ideal positions: data sampler of bit m at t0 + m*ui (+ dj[0]*P/8 in full rate), edge sampler half a UI later
    de = float(np.mean([inst[q] - q * P / 8 for q in ej]))            # mean edge-sampler lateness vs the ideal grid
    ncyc = {4: 5, 2: 10, 1: 20}[bpc] * words + 12
    bits = capture.prbs(int(ncyc * bpc) + 64)
    cm = rc11.SLCM[ck]
    pp, pn = [(0, cm - vd / 2)], [(0, cm + vd / 2)]
    for m in range(len(bits) - 1):
        ts = t0 + dj[0] * P / 8 + de + (m - 0.75) * ui                 # bit m starts 0.75 UI before its (ideal-grid) data instant
        if ts < 0: continue
        v = vd / 2 if bits[m] else -vd / 2
        pp += [(ts, pp[-1][1]), (ts + 0.2 * min(ui, 0.6e-9), cm + v)]
        pn += [(ts, pn[-1][1]), (ts + 0.2 * min(ui, 0.6e-9), cm - v)]
        if ts > t0 + ncyc * P: break
    sp = L.net('slicer', 'pub', bound); cp = L.net('wrx_cap', str(cap), bound)
    sm = dict(VDD_WIRE_SW='vdd', VSS='0', slicer_en='en', SL_P='inp', SL_N='inn', QCK='qck',
              D0='s0', E0='s1', D1='s2', E1='s3', D2='s4', E2='s5', D3='s6', E3='s7')
    sm.update({f'CKP{k}': f'ckp{k}' for k in range(8)})
    for q in ('VTAP', 'VTAN', 'VTBP', 'VTBN'): sm[q] = 'vt08'
    b = L.hdr(ck, f'r11 capB {key}') + keep + cl
    b += [f'VIP inps 0 {capture.sims_pwl(pp)}', f'VIN inns 0 {capture.sims_pwl(pn)}', 'RSP inps inp 25', 'RSN inns inn 25', 'CSP inp 0 50f', 'CSN inn 0 50f',
          f'.include {sp}', 'VVT vt08 0 0.8', L.inst('XSL', sp, 'pt_slicer', sm, default='0'), 'CQCK qck 0 20f', f'.include {cp}']
    if neg == 's2': b += ['RNEG s2 0 5']      # negative control: sampler output D1 shorted low
    import os
    if os.environ.get('R11_TEND'):        # speed test only: shortened run, no analysis
        ctl = re.sub(r'tran 2p \S+ 0 10p', f"tran 2p {os.environ['R11_TEND']} 0 10p", ctl); key += '_short'
    ctl = ctl.replace('wrdata out.txt', f'wrdata cb_{key}.txt')
    b += ['.control', ctl, '.endc', '.end']
    t_ = time.time(); log = L.run(f'cb_{key}', b, timeout=10 * 3600)
    f_ = L.RUN / f'cb_{key}.txt'
    try:
        r = an(log, f_)
    except Exception as exc:
        r = dict(error=repr(exc)[:300], log_tail=log[-400:])
    if f_.exists(): f_.unlink()
    r = {k: (v if not isinstance(v, (np.floating, np.integer)) else float(v)) for k, v in r.items()}
    r.update(key=key, corner=ck, rate_gbps=rate, mode=mode, ring_MHz=fring, rcs=rcs, psel=psel, trim_codes=tcodes, vd=vd, neg=neg, seconds=round(time.time() - t_),
             netlists=dict(slicer=L.sha(L.G / 'slicer.ext.spice'), wrx_cap=L.sha(cap), ptrim=L.sha(rc11.PTRIM[0]), ring_tag=cinfo.get('ring_tag')))
    r['pass'] = bool(r.get('pass_') and (r.get('bits') or 0) >= MIN_BITS[bpc])
    rc11.jstore('capb.json', key, json.loads(json.dumps(r, default=str)))
    print(key, {k: r.get(k) for k in ('words', 'bits', 'bit_errors', 'edge_errors', 'pd_ok', 'gear_ok', 'strobe_word_errors', 'i_mA', 'pass', 'error', 'seconds')}, flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]; kw = dict(x.split('=', 1) for x in a if '=' in x); pos = [x for x in a if '=' not in x]
    run(pos[0], float(pos[1]), rcs=int(kw.get('rcs', 0)), psel=int(kw.get('psel', 0)), words=int(kw['words']) if 'words' in kw else None, neg=kw.get('neg'),
        cap=Path(kw['cap']) if 'cap' in kw else CAP, codes=kw.get('codes', 'auto'), vd=float(kw.get('vd', 0.12)), lde_delay=float(kw.get('lde', 0.3)) * 1e-9)
