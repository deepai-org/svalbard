"""r10 chain bench with real neighbours (run through slot.sh; one ngspice at a time):
TX 50 ohm/leg -> [bench reference channel, applied to the TX waveform] -> user AC caps -> COB channel P2 (pkg_channel.py) ->
pad_hspad (extracted, staged b2: ESD, termination code 5 to HS_TERM_VCM, on-die AC coupling, HS_VBIAS) -> HS_RX route ->
pt_ctle r4 (staged extraction, follower inside, isolated-well junction added) -> SL: extracted pt_slicer, pt_rxselect r2
(staged extraction, off), pt_wmon_sel (off), 30 fF route.

  ch10.py ac <ck> [codes...]          AC source-EMF/2 -> SL, linear grid, saved to acdata/<ck>_c<code>.npz ; table in chain_ac.json
  ch10.py pick <ck> <rate> <stim>     best code and sampling phase from the AC data (peak-distortion eye, linear estimate)
  ch10.py tran <ck> <rate> <stim> [code] [key=value ...]   PRBS7 transient, slicer clocked with ideal ring phases: eye at SL
                                      and bit errors at D0-D3 ; results in chain_tran.json
stim: T1 (400 mVppd, COB only) | T2 (400 mVppd, 6 dB-at-Nyquist bench channel + COB) | T3 (120 mVppd, COB only)
"""
import sys, re, json, time, os, subprocess
from pathlib import Path
import numpy as np
import lib10 as L
sys.path.insert(0, str(L.W))
import pkg_channel as pc

PAD = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads/generated/stress-safe-families/wired-receive-hs/physical.spice')
# published stacked pad_hspad (PC-14), sha 320c43d9... = the staged b2 model the first runs used (same bytes)
PADR = [0.0]     # PC-14 defect: TERM_VCM metal resistance between the two termination legs (in no extraction): 0 = as extracted,
                 # 40 = nominal (~142 ohm differential at tt code 5), 70 = high metal corner.  Set by padr=<ohm>.


def pad_r(ohm):
    """Copy of the published pad model with the N leg's termination switches returned to their own TERM_VCM node, joined
    to the P leg / pin node by `ohm` (R-aware pessimistic pad variant; the pads owner's model is not edited)."""
    dst = L.NET / f'pad_hspad_r{ohm:g}.spice'
    if not dst.exists():
        lines = PAD.read_text().splitlines()
        nleg = set()
        for l in lines:           # termination resistors: ppolyf_u between PAD_N and a switch node
            t = l.split()
            if len(t) > 4 and t[0][0] == 'X' and t[4] == 'ppolyf_u' and 'PAD_N' in t[1:3]:
                nleg.add(t[1] if t[2] == 'PAD_N' else t[2])
        out, n = [], 0
        for l in lines:
            t = l.split()
            if len(t) > 5 and t[0][0] == 'X' and t[5] == 'nfet_06v0' and 'TERM_VCM' in t[1:4] and (set(t[1:4]) & nleg):
                t = [t[0]] + ['tvcm_nleg' if x == 'TERM_VCM' else x for x in t[1:4]] + t[4:]; l = ' '.join(t); n += 1
            if l.startswith('.ends') and n and 'done' not in locals():
                out.append(f'RTVCM_METAL TERM_VCM tvcm_nleg {ohm:g}'); done = True
            out.append(l)
        assert n >= 20, n
        dst.write_text('\n'.join(out) + '\n')
    return dst

ACD = L.H / ('acdata' + ('_' + L.VAR if L.VAR else '')); ACD.mkdir(exist_ok=True)
RR = [False]        # what-if: SL re-route inside each slicer bank (390 -> 150 fF of wiring per leg), set by rr=1
FMAX, DF = 8e9, 4e6
STIM = dict(T1=(0.4, False), T2=(0.4, True), T3=(0.12, False))    # TX swing (Vppd into a matched load), reference channel
APERTURE = 100e-12
VBIAS, VCM_T, TCODE = 0.98, 0.45, 5       # HS_VBIAS 0.95-1.01 V, HS_TERM_VCM 0.43-0.47 V (PINS.md), termination trim code 5


def front(ck, place='P2', hs_route_f=20.0):
    """Everything between the TX EMF nodes (tpi/tni) and the CTLE input (inp/inn)."""
    bound = L.CORN[ck][3]
    k = dict(nom=1.0, pess=1.15, opt=0.85)[bound]
    pad = L.net('pad_hspad', str(pad_r(PADR[0]) if PADR[0] else PAD), bound)
    m = dict(DVDD='vdd', VSS='0', VDD='vdd', TERM_VCM='tvcm', TERM_ENABLE='vdd', VBIAS='hvb', RX_P='inp', RX_N='inn', PAD_P='pdp', PAD_N='pdn')
    for b in range(4): m[f'TERM_TRIM{b}'] = 'vdd' if (TCODE >> b) & 1 else '0'
    return [pc.subckt('cobp', 'WIRE_RX_P', pc.PLACES[place], 0.0), pc.subckt('cobn', 'WIRE_RX_N', pc.PLACES[place], 0.0),
            'RTP tpi tp 50', 'RTN tni tn 50', 'CACP tp bp 100n', 'CACN tn bn 100n', 'RBP bp 0 1G', 'RBN bn 0 1G',
            'XCP pdp bp cobp', 'XCN pdn bn cobn', f'VTVCM tvcm 0 {VCM_T}', f'VHVB hvb 0 {VBIAS}',
            f'.include {pad}', L.inst('XPAD', pad, 'hs_protected_pad', m),
            f'CHRP inp 0 {hs_route_f * k:.4g}f', f'CHRN inn 0 {hs_route_f * k:.4g}f']


BANKB_ROUTE_F = 60.0     # extra SL route to the second slicer bank (R8-ARCH, not placed yet): 60 fF/leg assumed (low 30, high 100)


def chain(ck, code, clocks=None, extra_sl_f=0.0, banks=1, clocks_b=None, bankb_f=BANKB_ROUTE_F):
    bound = L.CORN[ck][3]
    b = front(ck) + L.ctle_inst('stg', bound, code) + L.well_lines(bound)
    b += L.slicer_inst(bound, clocks=clocks) + L.rxsel_inst('stg', bound) + L.wmon_inst(bound, rxp='urxp', rxn='urxn')
    kk = dict(nom=1.0, pess=1.15, opt=0.85)[bound]
    if RR[0]: extra_sl_f = extra_sl_f + 150.0 * banks
    if banks == 2:       # R8-ARCH: second published pt_slicer (bank B) on SL, on the interpolated phases
        b += L.slicer_inst(bound, clocks=clocks_b, x='XSB', pre='b_', include=False)
        extra_sl_f = extra_sl_f + bankb_f
    b += [f'CSP slp 0 {(30 + extra_sl_f) * kk:.4g}f', f'CSN sln 0 {(30 + extra_sl_f) * kk:.4g}f']
    return b


def evidence():
    return dict(ctle=L.sha(L.STG / 'ctle.ext.spice'), rxselect=L.sha(L.STG / 'rxselect.ext.spice'), slicer=L.sha(L.G / 'slicer.ext.spice'),
                wmon_sel=L.sha(L.G / 'wmon_sel.ext.spice'), pad_hspad=L.sha(PAD), well=json.loads(L.WELL.read_text()) if L.WELL.exists() else None)


# ---------------------------------------------------------------- AC
def ac(ck, code, extra=(), tag=None, extra_sl_f=0.0, banks=1, bankb_f=BANKB_ROUTE_F):
    tag = tag or f'{ck}_c{code}' + ('_b2' if banks == 2 else '') + (f'_r{bankb_f:g}' if banks == 2 and bankb_f != BANKB_ROUTE_F else '') + ('_rr' if RR[0] else '') + (f'_pr{PADR[0]:g}' if PADR[0] else '')
    out = ACD / f'{tag}.npz'
    if out.exists(): return dict(np.load(out))
    n = int(round(FMAX / DF))
    b = L.hdr(ck, f'chain ac code{code}') + ['VTP tpi 0 DC 0 AC 1', 'VTN tni 0 DC 0 AC -1'] + chain(ck, code, extra_sl_f=extra_sl_f, banks=banks, bankb_f=bankb_f) + list(extra)
    b += ['.control', 'op', 'let cm=(v(slp)+v(sln))/2', 'print cm', 'let cmi=(v(inp)+v(inn))/2', 'print cmi', 'print i(VDD)',
          f'ac lin {n} {DF} {FMAX}', 'set wr_singlescale', f'wrdata chac_{tag}.txt v(slp)-v(sln) v(inp)-v(inn) v(pdp)-v(pdn)', '.endc', '.end']
    t0 = time.time(); log = L.run(f'chac_{tag}', b)
    d = np.loadtxt(L.RUN / f'chac_{tag}.txt')
    r = dict(f=d[:, 0], h=d[:, 1] + 1j * d[:, 2], hin=d[:, 3] + 1j * d[:, 4], hpad=d[:, 5] + 1j * d[:, 6])
    for k_ in ('cm', 'cmi', 'i(vdd)'):
        m = re.search(rf'^{re.escape(k_)} = ([-+0-9.eE]+)', log, re.M)
        r[k_] = float(m.group(1)) if m else np.nan
    np.savez(out, **r); (L.RUN / f'chac_{tag}.txt').unlink()
    g = lambda fq: float(20 * np.log10(abs(np.interp(fq, r['f'], abs(r['h'])))))
    row = dict(gdc_20MHz=round(g(20e6), 2), g625=round(g(625e6), 2), g1g25=round(g(1.25e9), 2), g1g35=round(g(1.35e9), 2), g1g62=round(g(1.62e9), 2),
               gpk=round(float(20 * np.log10(abs(r['h']).max())), 2), fpk_MHz=round(float(r['f'][abs(r['h']).argmax()] / 1e6)),
               pad_g1g25=round(float(20 * np.log10(np.interp(1.25e9, r['f'], abs(r['hin'])))), 2), pad_g1g62=round(float(20 * np.log10(np.interp(1.62e9, r['f'], abs(r['hin'])))), 2),
               sl_cm=round(float(r['cm']), 3), in_cm=round(float(r['cmi']), 3), idd_mA=round(-1e3 * float(r['i(vdd)']), 2), seconds=round(time.time() - t0))
    L.store('chain_ac.json', tag, row); print(tag, row, flush=True)
    return r


# ---------------------------------------------------------------- reference channel and PDA
def chan_db(f, fn):
    """Bench reference channel: 6 dB differential insertion loss at fn (spec/interface-requirements.md), skin + dielectric."""
    x = np.abs(f) / fn
    return 6.0 * (0.4 * np.sqrt(x) + 0.6 * x)


def minphase(mag):
    """Minimum-phase spectrum (full FFT grid, even length) with the given magnitude."""
    n = len(mag); c = np.fft.ifft(np.log(np.maximum(mag, 1e-12))).real
    w = np.zeros(n); w[0] = 1; w[1:n // 2] = 2; w[n // 2] = 1
    return np.exp(np.fft.fft(c * w))


def pulse(ck, code, rate, stim, os_=16, hfun=None, banks=1):
    """Single-bit response at SL (V, differential, for +-A/2 signalling) on a time grid ui/os_ long 1/DF."""
    A, ref = STIM[stim]; ui = 1 / rate; tr = 0.3 * ui
    r = (ac(ck, code, banks=banks) if banks == 2 else ac(ck, code)) if hfun is None else hfun
    dt = ui / os_; n = int(round(1 / DF / dt)); n += n % 2
    f = np.fft.fftfreq(n, dt)
    H = np.interp(np.abs(f), r['f'], r['h'].real, right=0) + 1j * np.sign(f) * np.interp(np.abs(f), r['f'], r['h'].imag, right=0)
    H[np.abs(f) < DF / 2] = r['h'][4].real      # DC bin = the 20 MHz plateau: the on-die AC coupling (0.85 MHz) is not an ISI term for PRBS7
    P = (A / 2) * ui * np.sinc(f * ui) * np.sinc(f * tr) / dt
    if ref: P = P * minphase(10 ** (-chan_db(f, rate / 2) / 20))
    p = np.fft.ifft(P * H).real
    return p, dt


def pda(ck, code, rate, stim, os_=16, banks=1):
    p, dt = pulse(ck, code, rate, stim, os_, banks=banks)
    n = len(p); best = None; hts = []
    for ph in range(os_):
        col = p[ph::os_]; k = np.argmax(np.abs(col)); main = col[k]
        idx = [(k + q) % len(col) for q in range(-4, 13)]          # 4 pre-cursors, 12 post-cursors (PRBS7 memory)
        isi = np.sum(np.abs(col[idx])) - abs(main)
        h = 2 * (abs(main) - isi); hts.append(h)
        if best is None or h > best[0]: best = (h, ph, k, np.sign(main))
    h, ph, k, sg = best
    ti = k * os_ + ph
    if ti > n // 2: ti -= n
    # pulse() centres the transmitted trapezoid on t = 0; in tx_wave bit n starts its edge at n*ui and its trapezoid is
    # centred at n*ui + ui/2 + tr/2 (tr = 0.3 ui): tau = eye-centre time after the START of the transmitted bit
    tau = ti * dt + 0.65 / rate
    width = max_run([x >= 0.060 for x in hts]) / os_
    return dict(code=code, eye_mVppd=round(1e3 * h, 1), tau=tau, sign=float(sg), width_ui_ge60=round(width, 3))


def max_run(flags):
    """longest circular run of True."""
    n = len(flags)
    if all(flags): return n
    best = cur = 0
    for x in list(flags) * 2:
        cur = cur + 1 if x else 0; best = max(best, cur)
    return min(best, n)


def pick(ck, rate, stim, codes=range(8), banks=1):
    res = [pda(ck, c, rate, stim, banks=banks) for c in codes]
    best = max(res, key=lambda r: r['eye_mVppd'])
    return best, res


# ---------------------------------------------------------------- transient
def prbs7(n):
    st = [1] * 7; out = []
    for _ in range(n):
        nb = st[6] ^ st[5]; out.append(st[6]); st = [nb] + st[:6]
    return out


def tx_wave(rate, stim, nbits, os_=32):
    """One period of the PRBS7 TX EMF/2 waveform (differential, V) incl. the reference channel; periodic."""
    A, ref = STIM[stim]; ui = 1 / rate; tr = 0.3 * ui; dt = ui / os_
    bits = prbs7(127)
    t = np.arange(127 * os_) * dt
    v = np.zeros(len(t))
    lev = [(A / 2) * (1 if b else -1) for b in bits]
    for k in range(127):
        a, b = lev[k - 1], lev[k]
        seg = slice(k * os_, (k + 1) * os_); tt = t[seg] - k * ui
        v[seg] = np.where(tt < tr, a + (b - a) * tt / tr, b)
    if ref:
        f = np.fft.fftfreq(len(v), dt)
        v = np.fft.ifft(np.fft.fft(v) * minphase(10 ** (-chan_db(f, rate / 2) / 20))).real
    return bits, t, v, dt


def tran(ck, rate, stim, code, tau, sign=1.0, extra=(), tag=None, nsettle=20, extra_sl_f=0.0, banks=1):
    c, temp, vdd, bound = L.CORN[ck]
    ui = 1 / rate
    # <= 2.5 Gb/s: quarter rate, one bank (ring = line/4; D0..D3 are the data samplers).  2.7 / 3.24 Gb/s: R8-ARCH eighth
    # rate (ring = line/8): bank A's eight samplers D0,E0,D1,E1,.. on CKP0..7 are the data samplers (one per UI); bank B
    # (if banks == 2) is clocked on the 16-phase interleave (+P/16) and is a load here
    quarter = rate < 2.6e9
    fring = rate / 4 if quarter else rate / 8
    P = 1 / fring; uq = P / 4 if quarter else P / 8
    tag = tag or f'{ck}_{rate / 1e9:g}G_{stim}_c{code}'
    bits, t, v, dt = tx_wave(rate, stim, 127)
    nb = nsettle + 127 + 4
    # clocks: CKPk rising at T0 + k*P/8 ; D_j decides at T0 + j*uq + m*P + APERTURE.  The TX bit n starts at ttx + n*ui and is
    # at its eye centre tau later: put bit n0's centre on a D0 instant
    T0 = 2e-9
    ttx = T0 + APERTURE - tau
    while ttx < 1.0e-9: ttx += P
    tt = np.concatenate([ttx + t + q * 127 * ui for q in range(nb // 127 + 2)])[: nb * 32]
    vv = np.tile(v, nb // 127 + 2)[: nb * 32]
    # v is the differential level at a matched load (EMF/2): EMF per leg = +-v
    pts_p = ['0 0'] + [f'{x:.6e} {y:.6f}' for x, y in zip(tt, vv)]
    pts_n = ['0 0'] + [f'{x:.6e} {-y:.6f}' for x, y in zip(tt, vv)]
    tr_ = P / 40
    clk = {f'CKP{k}': f'ck{k}' for k in range(8)}
    b = L.hdr(ck, f'chain tran {tag}') + ['VTP tpi 0 PWL(' + ' '.join(pts_p) + ')', 'VTN tni 0 PWL(' + ' '.join(pts_n) + ')']
    b += [f'Vck{k} ck{k} 0 PULSE(0 {vdd} {T0 + k * P / 8:.6e} {tr_:.4e} {tr_:.4e} {P / 2 - tr_:.6e} {P:.6e})' for k in range(8)]
    clkb = {f'CKP{k}': f'ckb{k}' for k in range(8)} if banks == 2 else None
    if banks == 2:
        b += [f'Vckb{k} ckb{k} 0 PULSE(0 {vdd} {T0 + k * P / 8 + P / 16:.6e} {tr_:.4e} {tr_:.4e} {P / 2 - tr_:.6e} {P:.6e})' for k in range(8)]
    b += chain(ck, code, clocks=clk, extra_sl_f=extra_sl_f, banks=banks, clocks_b=clkb) + list(extra)
    tstop = ttx + nb * ui
    b += ['.control', f'tran {ui / 50:.4e} {tstop:.6e}', 'set wr_singlescale',
          f'wrdata chtr_{tag}.txt v(slp) v(sln) v(d0) v(d1) v(d2) v(d3) v(inp) v(inn) v(e0) v(e1) v(e2) v(e3)', '.endc', '.end']
    t0 = time.time(); log = L.run(f'chtr_{tag}', b, timeout=6 * 3600)
    f_ = L.RUN / f'chtr_{tag}.txt'
    if not f_.exists(): return dict(error=log[-500:], seconds=round(time.time() - t0))
    d = np.loadtxt(f_); np.savez_compressed(ACD / f'tr_{tag}.npz', d=d.astype(np.float32)); f_.unlink()
    T = d[:, 0]; sl = d[:, 1] - d[:, 2]
    out = dict(tag=tag, corner=ck, rate_gbps=rate / 1e9, stim=stim, code=code, mode='quarter' if quarter else 'eighth', banks=banks, ring_MHz=fring / 1e6,
               tx_mVppd=STIM[stim][0] * 1e3, ref_channel=STIM[stim][1], seconds=round(time.time() - t0), netlists=evidence())
    # ---- eye at SL: fold on the TX bit grid, expected bit = transmitted bit delayed by tau (sign from the AC data)
    os_ = 40; n0 = nsettle
    grid = ttx + tau - ui / 2 + (np.arange((nb - n0 - 2) * os_) / os_ + n0) * ui
    vg = np.interp(grid, T, sl).reshape(-1, os_)
    ref_bits = np.array([bits[(n0 + k) % 127] for k in range(vg.shape[0])])
    hts = []
    for ph in range(os_):
        col = vg[:, ph] * sign
        hts.append(col[ref_bits == 1].min() - col[ref_bits == 0].max())
    hts = np.array(hts); bp = int(hts.argmax())
    out.update(eye_mVppd=round(float(1e3 * hts.max()), 1), eye_best_phase_ui=round((bp - os_ / 2) / os_, 3),
               eye_width_ui_ge60=round(max_run(list(hts >= 0.060)) / os_, 3), eye_at_sampling_instant_mVppd=round(float(1e3 * hts[os_ // 2]), 1),
               sl_swing_mVppd=round(float(1e3 * (sl[T > ttx + n0 * ui].max() - sl[T > ttx + n0 * ui].min())), 1),
               sl_cm_V=round(float(np.mean((d[:, 1] + d[:, 2])[T > ttx + n0 * ui]) / 2), 3),
               in_swing_mVppd=round(float(1e3 * np.ptp((d[:, 7] - d[:, 8])[T > ttx + n0 * ui])), 1))
    # ---- bit errors at D0-D3: decision j,m at T0 + j*uq + m*P + APERTURE ; output read at the best phase of the ring period
    # (column in d, time offset): quarter D_j at j*uq ; eighth: sampler k on CKPk at k*uq, k even -> D(k/2), odd -> E((k-1)/2)
    samplers = [(3 + j, j * uq) for j in range(4)] if quarter else [((3 + k // 2) if k % 2 == 0 else (9 + k // 2), k * uq) for k in range(8)]
    m0 = int(np.ceil((ttx + n0 * ui - T0) / P)) + 1
    best = None
    for rp in range(20):                   # read phase after the decision instant, fraction of the ring period
        errs = chk = 0
        for col_, off_ in samplers:
            for m in range(m0, int((T[-1] - T0) / P) - 1):
                ts = T0 + off_ + m * P + APERTURE
                tread = ts + (rp + 0.5) / 20 * P
                if tread > T[-1]: continue
                nbit = int(np.floor((ts - ttx - tau + ui / 2) / ui))
                exp = bits[nbit % 127] if sign > 0 else 1 - bits[nbit % 127]
                got = np.interp(tread, T, d[:, col_]) > vdd / 2
                chk += 1; errs += int(got != bool(exp))
        if best is None or errs < best[0]: best = (errs, chk, rp)
    out.update(bit_errors=best[0], bits_checked=best[1], read_phase=round((best[2] + 0.5) / 20, 3))
    out['pass_eye'] = bool(out['eye_mVppd'] >= 60 and out['eye_width_ui_ge60'] >= 0.25)
    out['pass_ber'] = bool(best[0] == 0 and best[1] >= 100)
    out['pass'] = out['pass_eye'] and out['pass_ber']
    return out


def do_tran(ck, rate, stim, code=None, **kw):
    banks = kw.setdefault('banks', 1 if rate < 2.6e9 else 2)
    key = f'{ck}_{rate / 1e9:g}G_{stim}' + ('_rr' if RR[0] else '') + (f'_pr{PADR[0]:g}' if PADR[0] else '') + ('_b1' if banks == 1 and rate >= 2.6e9 else '') + (f'_c{code}' if code is not None else '') + (('_' + kw['tag']) if kw.get('tag') else '')
    res = L.stored('chain_tran.json')
    if key in res and 'bit_errors' in res[key]:
        return res[key]
    best, allc = pick(ck, rate, stim, banks=banks)
    if code is None: use = best
    else: use = next(r for r in allc if r['code'] == code)
    r = tran(ck, rate, stim, use['code'], use['tau'], use['sign'], tag=key, **{k: v for k, v in kw.items() if k != 'tag'})
    r['pda'] = dict(best_code=best['code'], eye_mVppd=use['eye_mVppd'], width_ui_ge60=use['width_ui_ge60'], all={x['code']: x['eye_mVppd'] for x in allc})
    L.store('chain_tran.json', key, r)
    print(key, {k: r.get(k) for k in ('code', 'eye_mVppd', 'eye_width_ui_ge60', 'eye_at_sampling_instant_mVppd', 'eye_best_phase_ui', 'bit_errors', 'bits_checked', 'read_phase', 'sl_cm_V', 'pass', 'seconds', 'error')},
          'pda', r['pda']['eye_mVppd'], flush=True)
    return r


if __name__ == '__main__':
    a = sys.argv[1:]
    pr = [x for x in a if x.startswith('padr=')]
    if pr:
        a.remove(pr[0]); PADR[0] = float(pr[0][5:])
    if 'rr=1' in a:
        a.remove('rr=1'); RR[0] = True; L.SLICER_KIND[0] = L.slicer_noslwire()
    if a[0] == 'ac':
        b2 = 'b2' in a; codes = [int(x) for x in a[2:] if x.isdigit()] or range(8)
        for code in codes: ac(a[1], code, banks=2 if b2 else 1)
    elif a[0] == 'rl':       # termination seen at the pad and return loss at the TX reference plane (100 ohm differential)
        ck = a[1]
        b = L.hdr(ck, 'rl') + ['VTP tpi 0 DC 0 AC 1', 'VTN tni 0 DC 0 AC -1'] + chain(ck, 0)
        b += ['.control', 'ac lin 400 10e6 4e9', 'set wr_singlescale', 'wrdata chrl.txt v(tp)-v(tn) v(pdp)-v(pdn) v(slp)-v(sln)', '.endc', '.end']
        L.run(f'chrl_{ck}_pr{PADR[0]:g}', b)
        d = np.loadtxt(L.RUN / 'chrl.txt'); f_ = d[:, 0]; v1 = d[:, 1] + 1j * d[:, 2]
        rl = -20 * np.log10(np.maximum(abs(v1 - 1), 1e-9))
        band = lambda lo, hi: round(float(rl[(f_ >= lo) & (f_ <= hi)].min()), 2)
        zlf = 100 * v1[1] / (2 - v1[1])
        row = dict(padr_ohm=PADR[0], z_diff_20MHz_ohm=round(float(abs(zlf)), 1), rl_min_0p1_1p25GHz_dB=band(0.1e9, 1.25e9), rl_min_1p25_1p62GHz_dB=band(1.25e9, 1.62e9),
                   rl_at_1p25GHz_dB=round(float(np.interp(1.25e9, f_, rl)), 2), rl_at_1p62GHz_dB=round(float(np.interp(1.62e9, f_, rl)), 2))
        L.store('chain_rl.json', f'{ck}_pr{PADR[0]:g}', row); print(ck, row, flush=True)
    elif a[0] == 'pick':
        best, allc = pick(a[1], float(a[2]) * 1e9, a[3], banks=2 if 'b2' in a else 1); print('best', best); [print(x) for x in allc]
    elif a[0] == 'tran':
        kw = dict(x.split('=') for x in a[4:] if '=' in x); code = next((int(x) for x in a[4:] if '=' not in x), None)
        if 'broken' in kw:          # negative control: 3 pF on each SL leg (must fail C-EYE and C-BER)
            do_tran(a[1], float(a[2]) * 1e9, a[3], code, tag='broken3pF', extra=['CBR1 slp 0 3p', 'CBR2 sln 0 3p'])
        elif 'slc' in kw:           # extra SL capacitance per leg in fF (what-if: negative = SL re-route in the slicer)
            do_tran(a[1], float(a[2]) * 1e9, a[3], code, tag=f'slc{kw["slc"]}', extra_sl_f=float(kw['slc']))
        elif 'banks' in kw:
            do_tran(a[1], float(a[2]) * 1e9, a[3], code, banks=int(kw['banks']))
        else:
            do_tran(a[1], float(a[2]) * 1e9, a[3], code)
