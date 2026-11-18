"""r11 real-clock chain bench A (run every command through ../../slot.sh; host ngspice, one at a time).

TX 50 ohm/leg -> [6 dB reference channel] -> AC caps -> COB P2 -> pad_hspad (published extraction; padr=40 = today's ~140 ohm
termination, padr=0 = the intended ~100 ohm) -> pt_ctle r4 (staged extraction) -> SL -> extracted pt_slicer (+ rxselect r2 off,
wmon_sel off, 30 fF route).  CLOCKS: one steady-state period of the extracted RX ring's PH0..7 at the ptrim pins (r11/ring/ph_*.npz,
ring on its regulated supply, 30 ohm / 60 fF route) replayed as periodic PWL -> extracted pt_ptrim (trim codes) -> CKP0..7 ->
slicer clock pins + the capture's clock-pin load (lumped C per pin from the r7e extraction) + 30 fF route + wordclk 20 fF on CKP0.

  rc11.py ap    <ck>                       sampler aperture (effective sampling instant after the CKP edge at the slicer pin), ideal clocks
  rc11.py clk   <ck> <fring_MHz> [codes=auto|0|a,b,..]     clock-only run (lumped loads): CKP instants, trim-code solve -> clk.json
  rc11.py tran  <ck> <rate_Gbps> <stim> [padr=40] [codes=auto|0] [clock=ideal] [neg=sl3p|ph2] [code=N]   -> tran.json
Modes: 0.48 full (ring 480), 1.25 half (ring 625), 2.5 / 2.7 / 3.24 quarter (ring 625 / 675 / 810), ONE slicer bank (the built hardware).
"""
import sys, json, time, os
from pathlib import Path
import numpy as np
H = Path(__file__).resolve().parent
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r10ctle')
import lib10 as L
import ch10
RING = H.parent / 'ring'
# Pad: the republished pad_hspad (PC-22, 2026-11-18) with resistance extracted.  R11_PAD = typ | high | low (metal corner).
# The capacitance-only physical.spice and the padr= variants of r10 are INVALID for the published cell.
PADV = os.environ.get('R11_PAD', 'typ')
ch10.PAD = Path(f'/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads/generated/stress-safe-families/wired-receive-hs/physical-r-{PADV}.spice')
ch10.ACD = H / f'ac_r{PADV}'; ch10.ACD.mkdir(exist_ok=True)
L.H = H; L.RUN = H / 'run'; L.RUN.mkdir(exist_ok=True)      # chain_ac.json etc. of the new pad stay in r11/chain
# termination trim code per corner = the code that gives 100 ohm in the pads record pc22-hspad-rxpath-r-<metal>.json
TCODE = dict(typ=dict(tt=5, ss315=8, ssp315=8, ss350=7, ssp350=7, ff=3, sf=5, fs=5), high=dict(tt=7, ss315=10, ssp315=10, ss350=9, ssp350=9, ff=4, sf=7, fs=7),
             low=dict(tt=4, ss315=6, ssp315=6, ss350=6, ssp350=6, ff=3, sf=4, fs=4))[PADV]
PTRIM = [Path(os.environ.get('R11_PTRIM', '/home/ubuntu/svalbard/scratch/wired_rx/r10ptrim/final/gen/ptrim.ext.spice'))]
CAP_PIN_F = [774.3, 216.7, 304.1, 210.5, 267.5, 227.8, 221.2, 213.9]      # r7e capture clock pins (r10ptrim/pin_cap_r7e.json)
SLI_PIN_F = [207.8, 171.7, 157.6, 157.7, 210.7, 206.0, 199.5, 188.8]      # slicer clock pins (pin_slicer.json), clock-only runs
WCK_F, ROUTE_F = 20.0, 30.0
L.CORN.update(sf=('sf', 32, 3.15, 'nom'), fs=('fs', 32, 3.15, 'nom'))
RINGTAG = {'sf': 'sf', 'fs': 'fs', 'tt': 'tt', 'ss315': 'ss315', 'ss350': 'ss350', 'ff': 'ff', 'ssp315': 'ss315', 'ssp350': 'ss350'}   # pessimistic: nominal-ss ring waveform
MODE = {0.48: ('full', 480.0, 1), 1.25: ('half', 625.0, 2), 2.5: ('quarter', 625.0, 4), 2.7: ('quarter', 675.0, 4), 3.24: ('quarter', 810.0, 4), 3.125: ('quarter', 781.25, 4),
        1.92: ('quarter', 480.0, 4)}     # 1.92 = quarter mode at ring 480 MHz (bench B only: the capture path used for 0.48 Gb/s with digital phase picking)
T0 = 3e-9
# KLU sparse solver (host ngspice-42): 3.8x faster on the capture bench (12 ns: 391 s -> 103 s).  Validated against the default
# solver on tt 2.5 Gb/s T2 (see STATUS.md).  R11_KLU=0 switches it off.
KLU = os.environ.get('R11_KLU', '1') == '1'
_run0 = L.run
def _run(tag, lines, timeout=7200):
    # rshunt: the R-aware pad model has a floating metal island (m3_32896_117300#) -> singular matrix in the operating point
    # sf / fs: the PDK has no res_/diode_/mimcap_ sections for the skewed corners -> typical passives (as wrx_flow.sim_header does)
    lines = [l.replace('res_sf', 'res_typical').replace('res_fs', 'res_typical').replace('diode_sf', 'diode_typical').replace('diode_fs', 'diode_typical')
              .replace('mimcap_sf', 'mimcap_typical').replace('mimcap_fs', 'mimcap_typical') if l.startswith('.lib') else l for l in lines]
    return _run0(tag, lines[:1] + ['.option rshunt=1e13'] + (['.option klu'] if KLU else []) + lines[1:], timeout=timeout)
L.run = _run
NSUB = 4            # PWL replay uses 100 points per ring period (12-21 ps): the 400-point table forced 4 ps steps (run time x5)


def jload(name):
    p = H / name
    return json.loads(p.read_text()) if p.exists() else {}


def jstore(name, key, val):
    d = jload(name); d[key] = val; (H / name).write_text(json.dumps(d, indent=1))


def edges(t, v, th, rising=True):
    s = v > th; i = np.where(s[1:] != s[:-1])[0]; i = i[s[i + 1] == rising]
    return t[i] + (th - v[i]) * (t[i + 1] - t[i]) / (v[i + 1] - v[i])


def clock_lines(ck, fring, codes, real_slicer, shift=None, real_capture=False, t0=None):
    """PH replay -> ptrim -> ck0..7.  real_slicer False: the slicer pin C is lumped too (clock-only runs)."""
    c, temp, vdd, bound = L.CORN[ck]
    k = dict(nom=1.0, pess=1.15, opt=0.85)[bound]
    z = np.load(RING / f'ph_{RINGTAG[ck]}{fring:g}.npz'); n = int(z['n']); P = 1e-6 / fring
    out = []
    for q in range(8):
        v = z[f'ph{q}'][::NSUB]; sh = (shift or {}).get(q, 0.0)       # every NSUB-th point of the 400-point table (same grid for all 8)
        nn = len(v)
        pts = ' '.join(f'{i * P / nn:.6e} {v[i]:.4f}' for i in range(nn)) + f' {P:.6e} {v[0]:.4f}'
        out.append(f'Vph{q} ph{q} 0 PWL({pts}) r=0 td={(T0 if t0 is None else t0) + sh:.6e}')
    p = L.net('ptrim', str(PTRIM[0]), bound)
    m = dict(VDD_WIRE_SW='vddp', VSS='0', ptrim_en='vdd')
    for q in range(8):
        m[f'PH{q}'] = f'ph{q}'; m[f'CKP{q}'] = f'ck{q}'
        for b in range(5): m[f'T{q}_{b}'] = 'vdd' if (codes[q] >> b) & 1 else '0'
        cl = ((0 if real_capture else CAP_PIN_F[q]) + (WCK_F if q == 0 else 0) + ROUTE_F + (0 if real_slicer else SLI_PIN_F[q])) * k
        out.append(f'CCK{q} ck{q} 0 {cl:.5g}f')
    out += ['VMP vdd vddp 0', f'.include {p}', L.inst('XPT', p, 'pt_ptrim', m)]
    return out, P, float(z['vring'])


def ck_instants(T, d, cols, vdd, P, tmin):
    """mean rising mid-crossing of each ck column relative to T0 + k*P/8 (s), its peak-to-peak, duty, levels."""
    res = []
    for q, col in enumerate(cols):
        v = d[:, col]; r = edges(T, v, vdd / 2); r = r[r > tmin]; f = edges(T, v, vdd / 2, False)
        if len(r) < 3: res.append(None); continue
        x = (r - T0 - q * P / 8) % P
        x = np.where(x > P * 0.9, x - P, x)      # delays are < 0.9 P
        du = [(f[f > a][0] - a) / P for a in r[:-1] if len(f[f > a])]
        sel = T > tmin
        res.append(dict(delay_ps=round(float(np.mean(x)) * 1e12, 2), pp_ps=round(float(np.ptp(x)) * 1e12, 2), duty=round(float(np.mean(du)), 4),
                        hi=round(float(v[sel].max()), 3), lo=round(float(v[sel].min()), 3)))
    return res


def clk_run(ck, fring, codes, tag):
    c, temp, vdd, bound = L.CORN[ck]
    cl, P, vring = clock_lines(ck, fring, codes, real_slicer=False)
    b = L.hdr(ck, f'clk {tag}') + cl
    tstop = T0 + 14 * P
    b += ['.control', f'tran {P / 400:.4e} {tstop:.6e}', 'set wr_singlescale', 'wrdata ' + f'clk_{tag}.txt ' + ' '.join(f'v(ck{q})' for q in range(8)) + ' i(VMP)', '.endc', '.end']
    L.RUN = H / 'run'; L.RUN.mkdir(exist_ok=True)
    log = L.run(f'clk_{tag}', b, timeout=3600)
    f_ = L.RUN / f'clk_{tag}.txt'
    if not f_.exists(): raise RuntimeError(log[-800:])
    d = np.loadtxt(f_); f_.unlink()
    T = d[:, 0]
    st = ck_instants(T, d, range(1, 9), vdd, P, T0 + 5 * P)
    sel = T > T0 + 5 * P
    return st, round(float(np.mean(d[sel, 9])) * 1e3, 2)


def solve_codes(ck, fring):
    """Trim codes that equalise the CKP rising-edge spacing at the consumers: runs code 0 and code 31, assumes a linear code
    law per channel, then verifies with the chosen codes.  Stored in clk.json[ck_fring]."""
    key = f'{ck}_{fring:g}'
    D = jload('clk.json')
    if key in D and 'codes' in D[key]: return D[key]
    s0, i0 = clk_run(ck, fring, [0] * 8, key + '_c0')
    s31, i31 = clk_run(ck, fring, [31] * 8, key + '_c31')
    if any(x is None for x in s0 + s31):
        r = dict(error='a clock does not toggle', code0=s0, code31=s31); jstore('clk.json', key, r); return r
    d0 = np.array([x['delay_ps'] for x in s0]); d31 = np.array([x['delay_ps'] for x in s31]); lsb = (d31 - d0) / 31
    need = d0.max() - d0
    codes = [int(min(31, max(0, round(need[q] / lsb[q])))) for q in range(8)]
    sc, ic = clk_run(ck, fring, codes, key + '_cb')
    dc = np.array([x['delay_ps'] for x in sc])
    r = dict(corner=ck, fring_MHz=fring, ptrim=str(PTRIM[0]), ptrim_sha256=L.sha(PTRIM[0]), ring_tag=f'{RINGTAG[ck]}{fring:g}',
             code0=s0, code31=s31, range_ps=[round(float(x), 1) for x in d31 - d0], need_ps=[round(float(x), 1) for x in need],
             pos_err_code0_ps=[round(float(x), 1) for x in d0 - d0.mean()], spread_code0_ps=round(float(np.ptp(d0)), 1),
             range_covers=bool(np.all(need <= d31 - d0)), codes=codes, trimmed=sc,
             pos_err_trimmed_ps=[round(float(x), 1) for x in dc - dc.mean()], spread_trimmed_ps=round(float(np.ptp(dc)), 1),
             idd_ptrim_mA=dict(code0=abs(i0), code31=abs(i31), trimmed=abs(ic)))
    jstore('clk.json', key, r)
    print(key, 'spread code0', r['spread_code0_ps'], 'need', r['need_ps'], 'range', r['range_ps'], 'covers', r['range_covers'], 'codes', codes,
          'spread trimmed', r['spread_trimmed_ps'], 'duty', [x['duty'] for x in sc], 'lvl', max(x['lo'] for x in sc), min(x['hi'] for x in sc), 'mA', r['idd_ptrim_mA'], flush=True)
    return r


# ---------------------------------------------------------------- sampler aperture
SLCM = dict(sf=0.44, fs=0.44, tt=0.46, ss315=0.41, ss350=0.58, ff=0.43, ssp315=0.41, ssp350=0.58)


def aperture(ck):
    """Effective sampling instant of each sampler after its CKP mid-crossing (ideal clocks, 60 ps edges, 625 MHz): a 200 mVppd
    square input with 120 ps edges whose period is P + 8 ps slides through the sampling instant; the decision flips where
    the input zero crossing passes the aperture.  Known answer for the bench: the result must not depend on the slide
    direction by more than the 8 ps step (checked with period P - 8 ps)."""
    c, temp, vdd, bound = L.CORN[ck]
    P = 1.6e-9; out = {}
    for sgn in (+1, -1):
        Pin = P + sgn * 8e-12; nc = 208; tr = 120e-12; cm = SLCM[ck]
        x0 = (250e-12 if sgn < 0 else -200e-12)        # input rising zero crossing relative to CKP0's mid-crossing in cycle 0
        b = L.hdr(ck, f'aperture {ck}')
        b += [f'Vck{q} ck{q} 0 PULSE(0 {vdd} {T0 + q * P / 8 - 30e-12:.6e} 60p 60p {P / 2 - 60e-12:.6e} {P:.6e})' for q in range(8)]
        # input: rising edge mid-crossing at T0 + x0 + n*Pin, falling half a period later
        td = T0 + x0 - tr / 2
        while td < 0.2e-9: td += Pin
        n0 = round((td - (T0 + x0 - tr / 2)) / Pin)
        b += [f'Vinp slp 0 PULSE({cm - 0.05} {cm + 0.05} {td:.6e} {tr:.3e} {tr:.3e} {Pin / 2 - tr:.6e} {Pin:.6e})',
              f'Vinn sln 0 PULSE({cm + 0.05} {cm - 0.05} {td:.6e} {tr:.3e} {tr:.3e} {Pin / 2 - tr:.6e} {Pin:.6e})']
        b += L.slicer_inst(bound, clocks={f'CKP{q}': f'ck{q}' for q in range(8)})
        tstop = T0 + (nc + 2) * P
        names = ['d0', 'e0', 'd1', 'e1', 'd2', 'e2', 'd3', 'e3']
        b += ['.control', f'tran 4p {tstop:.6e}', 'set wr_singlescale', f'wrdata ap_{ck}.txt ' + ' '.join(f'v({x})' for x in names), '.endc', '.end']
        L.RUN = H / 'run'; L.RUN.mkdir(exist_ok=True)
        log = L.run(f'ap_{ck}_{sgn}', b, timeout=3600)
        f_ = L.RUN / f'ap_{ck}.txt'
        if not f_.exists(): raise RuntimeError(log[-800:])
        d = np.loadtxt(f_); f_.unlink(); T = d[:, 0]
        res = []
        for q in range(8):
            xs, dec = [], []
            for m in range(2, nc):
                tck = T0 + q * P / 8 + m * P
                # nearest input rising crossing: T0 + x0 + (n - n0... ) : crossing index j with time tin_j = T0 + x0 + j*Pin (j may be negative)
                j = round((tck - T0 - x0) / Pin); x = (T0 + x0 + j * Pin) - tck
                if abs(x) > 0.3 * P or tck + P + 0.2e-9 > T[-1]: continue
                got = np.interp(tck + P + 0.2e-9, T, d[:, 1 + q]) > vdd / 2   # valid from clk-to-Q (0.7-1.5 ns) until the next cycle's clk-to-Q
                xs.append(x); dec.append(bool(got))
            xs = np.array(xs); dec = np.array(dec); o = np.argsort(xs); xs, dec = xs[o], dec[o]
            # input rose BEFORE the aperture (x < A) -> decision 1; find the threshold
            flips = [i for i in range(1, len(xs)) if dec[i] != dec[i - 1]]
            # one flip expected; an odd number within a few steps = decisions dithering at the threshold: take the middle of the band
            okf = len(flips) % 2 == 1 and (xs[flips[-1]] - xs[flips[0] - 1]) < 40e-12
            res.append(dict(A_ps=round(float((xs[flips[-1]] + xs[flips[0] - 1]) / 2) * 1e12, 1) if okf else None, flips=len(flips),
                            band_ps=round(float(xs[flips[-1]] - xs[flips[0] - 1]) * 1e12, 1) if flips else None, ones_first=bool(dec[0])))
        out['plus' if sgn > 0 else 'minus'] = res
    A = [np.mean([out[s][q]['A_ps'] for s in out]) if all(out[s][q]['A_ps'] is not None for s in out) else None for q in range(8)]
    r = dict(corner=ck, sl_cm=SLCM[ck], per_dir=out, A_ps=[None if a is None else round(float(a), 1) for a in A],
             dir_diff_ps=[None if out['plus'][q]['A_ps'] is None or out['minus'][q]['A_ps'] is None else round(out['plus'][q]['A_ps'] - out['minus'][q]['A_ps'], 1) for q in range(8)],
             slicer_sha256=L.sha(L.net('slicer', 'pub', bound)))
    jstore('aperture.json', ck, r); print(ck, 'aperture ps', r['A_ps'], 'dir diff', r['dir_diff_ps'], flush=True)
    return r


# ---------------------------------------------------------------- chain transient with real clocks
def tran(ck, rate, stim, padr=40.0, codes='auto', clock='real', neg=None, code=None, nbits=None):
    c, temp, vdd, bound = L.CORN[ck]
    mode, fring, bpc = MODE[rate]
    ch10.PADR[0] = 0.0; ch10.TCODE = TCODE[ck]
    L.RUN = H / 'run'; L.RUN.mkdir(exist_ok=True)
    key = f'{ck}_{rate:g}G_{stim}_pad{PADV}' + ('' if codes == 'auto' else f'_codes{codes}') + ('' if clock == 'real' else f'_{clock}') + (f'_neg{neg}' if neg else '') + (f'_c{code}' if code is not None else '')
    if not KLU: key += '_noklu'
    done = jload('tran.json')
    if key in done and 'bit_errors' in done[key]: return done[key]
    best, allc = ch10.pick(ck, rate * 1e9, stim, banks=1)
    use = best if code is None else next(r for r in allc if r['code'] == code)
    tau, sign, ccode = use['tau'], use['sign'], use['code']
    ui = 1e-9 / rate; P = 1e-6 / fring
    ap = jload('aperture.json').get(ck)
    if ap is None or any(a is None for a in ap['A_ps']): raise RuntimeError(f'no aperture record for {ck}: run rc11.py ap {ck}')
    A = np.array(ap['A_ps']) * 1e-12
    # ---- clocks
    if clock == 'ideal':
        cinfo = None; cdelay = np.zeros(8); tcodes = None
        clk_lines = [f'Vck{q} ck{q} 0 PULSE(0 {vdd} {T0 + q * P / 8 - P / 80:.6e} {P / 40:.4e} {P / 40:.4e} {P / 2 - P / 40:.6e} {P:.6e})' for q in range(8)] + ['VMP vdd vddp 0']
    else:
        if codes == 'auto':
            cinfo = solve_codes(ck, fring)
            if 'error' in cinfo: r = dict(error=cinfo['error'], key=key); jstore('tran.json', key, r); return r
            tcodes = cinfo['codes']; cdelay = np.array([x['delay_ps'] for x in cinfo['trimmed']]) * 1e-12
        else:
            tcodes = [int(codes)] * 8; cinfo = solve_codes(ck, fring)
            cdelay = np.array([x['delay_ps'] for x in cinfo['code0' if int(codes) == 0 else 'code31']]) * 1e-12
        # negative controls: PH2 (data sampler D1) late by 0.4 UI (ph2) or 0.5 UI = on the data transition (ph2x)
        shift = {2: 0.4 * ui} if neg == 'ph2' else {2: 0.5 * ui} if neg == 'ph2x' else {2: 0.45 * ui} if neg == 'ph2m' else None
        clk_lines, P, vring = clock_lines(ck, fring, tcodes, real_slicer=True, shift=shift)
    # ---- CDR-lock emulation: the loop puts the data transitions on the mean edge-sampler instant; the data samplers then
    # sit where their own clocks put them.  Sampler q decides at T0 + q*P/8 + cdelay[q] + A[q] (+ m*P).
    inst = np.arange(8) * P / 8 + cdelay + A                     # predicted, relative to T0
    if mode == 'quarter': dq, eq = [0, 2, 4, 6], [1, 3, 5, 7]
    elif mode == 'half': dq, eq = [0, 4], [2, 6]
    else: dq, eq = list(range(8)), []                            # full rate: every sampler is a candidate data phase (psel)
    if eq:
        ph = np.array([(inst[q] % ui) for q in eq]); ref = ph[0]
        phu = ref + ((ph - ref + ui / 2) % ui - ui / 2)          # unwrap around the first
        tedge = float(np.mean(phu))                               # transition instant (mod ui) relative to T0
        tcen = tedge + ui / 2
    else:
        tcen = inst[0]                                            # full rate: eye centre on sampler 0 (psel 0), others spread over the UI
    nsettle = 24; nb = nsettle + (nbits or (120 if bpc == 4 else 110 if bpc == 2 else 40)) + 4
    bits, t, v, dt = ch10.tx_wave(rate * 1e9, stim, 127)
    # bit n is at its eye centre at ttx + n*ui + tau : put that on T0 + tcen (mod ui)
    ttx = T0 + tcen - tau
    while ttx < 1.0e-9: ttx += ui
    while ttx > 1.0e-9 + ui: ttx -= ui
    tt_ = np.concatenate([ttx + t + q * 127 * ui for q in range(nb // 127 + 2)])[: nb * 32]
    vv = np.tile(v, nb // 127 + 2)[: nb * 32]
    b = L.hdr(ck, f'r11 chain {key}') + ['VTP tpi 0 PWL(0 0 ' + ' '.join(f'{x:.6e} {y:.6f}' for x, y in zip(tt_, vv)) + ')',
                                          'VTN tni 0 PWL(0 0 ' + ' '.join(f'{x:.6e} {-y:.6f}' for x, y in zip(tt_, vv)) + ')']
    b += clk_lines + ch10.chain(ck, ccode, clocks={f'CKP{q}': f'ck{q}' for q in range(8)})
    if neg == 'sl3p': b += ['CBR1 slp 0 3p', 'CBR2 sln 0 3p']
    tstop = ttx + nb * ui
    names = ['slp', 'sln', 'd0', 'e0', 'd1', 'e1', 'd2', 'e2', 'd3', 'e3'] + [f'ck{q}' for q in range(8)]
    b += ['.control', f'tran {min(ui / 50, P / 300):.4e} {tstop:.6e}', 'set wr_singlescale', f'wrdata tr_{key}.txt ' + ' '.join(f'v({x})' for x in names) + ' i(VMP)', '.endc', '.end']
    t0 = time.time(); log = L.run(f'tr_{key}', b, timeout=8 * 3600)
    f_ = L.RUN / f'tr_{key}.txt'
    if not f_.exists():
        r = dict(error=log[-600:], key=key, seconds=round(time.time() - t0)); jstore('tran.json', key, r); print(key, 'ERROR', log[-300:]); return r
    d = np.loadtxt(f_); f_.unlink(); (L.RUN / f'tr_{key}.cir').unlink()
    T = d[:, 0]; sl = (d[:, 1] - d[:, 2]) * sign
    tmin = ttx + nsettle * ui
    out = dict(key=key, pad=str(ch10.PAD), term_code=TCODE[ck], corner=ck, rate_gbps=rate, mode=mode, ring_MHz=fring, stim=stim, padr_ohm=padr, ctle_code=ccode, clock=clock, trim_codes=tcodes,
               neg=neg, seconds=round(time.time() - t0), netlists=dict(ch10.evidence(), ptrim=L.sha(PTRIM[0]), ring_tag=f'{RINGTAG[ck]}{fring:g}'),
               sl_cm_V=round(float(np.mean((d[:, 1] + d[:, 2])[T > tmin]) / 2), 3), sl_swing_mVppd=round(float(1e3 * np.ptp(sl[T > tmin])), 1))
    # ---- actual clocks at the slicer pins
    cst = ck_instants(T, d, range(11, 19), vdd, P, tmin)
    out['ckp'] = cst
    if any(x is None for x in cst):
        out.update(error='a CKP does not toggle', bit_errors=None); out['pass'] = False; jstore('tran.json', key, out); print(key, 'CKP dead'); return out
    cact = np.array([x['delay_ps'] for x in cst]) * 1e-12
    inst_a = np.arange(8) * P / 8 + cact + A
    out['ckp_pos_err_ps'] = [round(float(x) * 1e12, 1) for x in cact - cact.mean()]
    out['idd_ptrim_mA'] = round(abs(float(np.mean(d[T > tmin, 19]))) * 1e3, 2)
    # ---- eye at SL folded on the TX bit grid (as r10) and seen by each data sampler at its ACTUAL instant
    os_ = 40; n0 = nsettle
    grid = ttx + tau - ui / 2 + (np.arange((nb - n0 - 2) * os_) / os_ + n0) * ui
    vg = np.interp(grid, T, sl).reshape(-1, os_)
    ref_bits = np.array([bits[(n0 + k_) % 127] for k_ in range(vg.shape[0])])
    hts = np.array([vg[:, p_][ref_bits == 1].min() - vg[:, p_][ref_bits == 0].max() for p_ in range(os_)])
    out.update(eye_mVppd=round(float(1e3 * hts.max()), 1), eye_width_ui_ge60=round(ch10.max_run(list(hts >= 0.060)) / os_, 3),
               eye_best_phase_ui=round((int(hts.argmax()) - os_ / 2) / os_, 3))
    # zero-crossing phase of SL relative to the bit grid (where a CDR would lock) vs where the bench put the edge samplers
    zc = np.concatenate([edges(T, sl, 0.0), edges(T, sl, 0.0, False)]); zc = zc[zc > tmin]
    zph = ((zc - (ttx + tau - ui / 2)) + ui / 2) % ui - ui / 2          # 0 = nominal boundary
    out['sl_crossing_mean_ui'] = round(float(np.mean(zph) / ui), 3); out['sl_crossing_pp_ui'] = round(float(np.ptp(zph) / ui), 3)
    per = []
    for q in dq:
        # phase of this sampler's actual instant inside the bit: 0 = eye centre as placed by the bench
        x = ((T0 + inst_a[q]) - (ttx + tau)) % ui
        x = x - ui if x > ui / 2 else x
        p_ = int(round(x / ui * os_)) + os_ // 2
        h_here = float(hts[p_ % os_]) if 0 <= p_ < os_ else float('nan')
        ok = hts >= 0.060
        lft = 0
        while lft < os_ and 0 <= p_ - lft - 1 < os_ and ok[p_ - lft - 1] and ok[p_ % os_]: lft += 1
        rgt = 0
        while rgt < os_ and 0 <= p_ + rgt + 1 < os_ and ok[p_ + rgt + 1] and ok[p_ % os_]: rgt += 1
        per.append(dict(sampler=q, offset_from_centre_ui=round(float(x / ui), 3), eye_at_instant_mVppd=round(1e3 * h_here, 1),
                        margin_left_ui=round(lft / os_, 3), margin_right_ui=round(rgt / os_, 3)))
    out['data_samplers'] = per
    # ---- decisions: sampler q decides at T0 + inst_a[q] + m*P ; read its output at the best read phase
    best_ = None
    m0 = int(np.ceil((tmin - T0) / P)) + 1
    for rp in range(40):                  # read phase 0..2 P after the decision (clock-to-output exceeds P at 810 MHz, slow corner)
        tot = {q: [0, 0] for q in range(8)}
        for q in range(8):
            for m in range(m0, int((T[-1] - T0) / P) - 1):
                ts = T0 + inst_a[q] + m * P
                tread = ts + (rp + 0.5) / 20 * P
                if tread > T[-1]: continue
                nbit = int(np.floor((ts - ttx - tau + ui / 2) / ui))
                exp = bits[nbit % 127]
                got = (np.interp(tread, T, d[:, 3 + q]) > vdd / 2)
                if sign < 0: got = not got
                tot[q][1] += 1; tot[q][0] += int(bool(got) != bool(exp))
        e = sum(tot[q][0] for q in dq)
        if best_ is None or e < best_[0]: best_ = (e, tot, rp)
    e, tot, rp = best_
    out['errors_per_sampler'] = {str(q): tot[q] for q in range(8)}
    if mode == 'full':
        # the phase picker selects one sampler: pass needs >= 3 adjacent error-free phases (picker +-1 dither) with eye >= 60 mV
        clean = [tot[q][0] == 0 and tot[q][1] >= 20 and per[q]['eye_at_instant_mVppd'] >= 60 for q in range(8)]
        out.update(clean_phases=int(sum(clean)), longest_clean_run=ch10.max_run(clean), bit_errors=int(min(tot[q][0] for q in range(8))),
                   bits_checked=int(tot[0][1]), min_eye_at_instant_mVppd=max(p_['eye_at_instant_mVppd'] for p_ in per))
        out['pass_eye'] = bool(out['eye_mVppd'] >= 60 and out['eye_width_ui_ge60'] >= 0.25)
        out['pass'] = bool(out['pass_eye'] and out['longest_clean_run'] >= 3)
    else:
        out.update(bit_errors=int(e), bits_checked=int(sum(tot[q][1] for q in dq)), read_phase=round((rp + 0.5) / 20, 3),
                   min_eye_at_instant_mVppd=min(p_['eye_at_instant_mVppd'] for p_ in per),
                   min_margin_ui=min(min(p_['margin_left_ui'], p_['margin_right_ui']) for p_ in per))
        # edge samplers on transitions: early/late balance (lock indicator; 0.5 = centred on the crossings)
        out['pass_eye'] = bool(out['eye_mVppd'] >= 60 and out['eye_width_ui_ge60'] >= 0.25)
        out['pass_inst'] = bool(out['min_eye_at_instant_mVppd'] >= 60 and out['min_margin_ui'] >= 0.05)
        out['pass_ber'] = bool(e == 0 and out['bits_checked'] >= 100)
        out['pass'] = bool(out['pass_eye'] and out['pass_inst'] and out['pass_ber'])
    out['pda'] = dict(best_code=best['code'], eye_mVppd=use['eye_mVppd'])
    jstore('tran.json', key, out)
    print(key, {k_: out.get(k_) for k_ in ('ctle_code', 'trim_codes', 'eye_mVppd', 'eye_width_ui_ge60', 'min_eye_at_instant_mVppd', 'min_margin_ui', 'bit_errors', 'bits_checked',
                                           'clean_phases', 'longest_clean_run', 'sl_crossing_mean_ui', 'ckp_pos_err_ps', 'pass', 'seconds')}, flush=True)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    kw = dict(x.split('=', 1) for x in a if '=' in x); pos = [x for x in a if '=' not in x]
    if pos[0] == 'ap': aperture(pos[1])
    elif pos[0] == 'clk':
        L.RUN = H / 'run'; L.RUN.mkdir(exist_ok=True)
        solve_codes(pos[1], float(pos[2]))
    elif pos[0] == 'tran':
        tran(pos[1], float(pos[2]), pos[3], padr=float(kw.get('padr', 40)), codes=kw.get('codes', 'auto'), clock=kw.get('clock', 'real'), neg=kw.get('neg'),
             code=int(kw['code']) if 'code' in kw else None, nbits=int(kw['nbits']) if 'nbits' in kw else None)
