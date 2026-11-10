"""TX modulation-quality model: EVM, ACLR, spectral mask, LO jitter and I/Q skew.

The RF chain is represented by its extracted AM-AM / AM-PM (amam_* decks in
rf_tx-sim-ext.json: baseband DC on I, CW at the LO, the board network and balun
loss included). At 20 MHz signal bandwidth on a 2.44 GHz carrier the chain is
quasi-static, so a memoryless complex-gain model is applied to an 802.11ax HE20
OFDM waveform (256-point FFT at 20 MS/s, 242 used tones, 78.125 kHz spacing,
1/4 GI). Not transistor-level: the transistor-level part is the AM-AM/AM-PM
table, the LO-skew image sweep (skew_* decks) and the CW harmonics.

Stimulus chain ahead of the RF model (stated assumptions, other owners' blocks):
  * DAC: 10-bit, 40 MS/s (2x oversampled HE20), zero-order hold;
  * reconstruction filter: 5th-order Butterworth, 15.2 MHz corner (bbfilter tt);
  * digital spectral shaping (FPGA): 255-tap equiripple low-pass at 40 MS/s, pass 9.7 MHz,
    stop 10.4 MHz (unwindowed OFDM alone fails the mask by ~6 dB even with an ideal PA);
  * baseband scaling: the RMS differential baseband per rail is chosen so the
    mean output power hits the target; the peak is not clipped digitally unless
    --cfr is given (crest-factor reduction by clip-and-filter at the given PAPR).

Impairments swept:
  * LO jitter: white phase jitter sigma_t (rms) -> phase noise 2*pi*f_LO*sigma_t
    rad rms, band-limited to the LO buffer bandwidth (assumed >> 20 MHz: white
    within the channel). Integrated-jitter interpretation.
  * Baseband I/Q timing skew between the I and Q DAC/filter paths.
  * LO quadrature skew: from the transistor-level skew_* image-rejection decks,
    converted to an equivalent phase error and applied to the waveform.

Usage: python3 tx_modulation.py [--sim generated/rf_tx-sim-ext.json] [--out generated/rf_tx-modulation.json]
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy import signal

HERE = Path(__file__).resolve().parent
F_LO = 2.44e9
FS_BB = 20e6
NFFT = 256
OVS = 16                       # simulation rate = 320 MS/s
N_SYM = 60
EVM_LIMITS_DB = {'MCS0 BPSK 1/2': -5, 'MCS2 QPSK 3/4': -13, 'MCS4 16QAM 3/4': -19, 'MCS5 64QAM 2/3': -22,
                 'MCS7 64QAM 5/6': -27, 'MCS9 256QAM 5/6': -32}
# 802.11ax HE20 transmit spectral mask (dBr vs offset MHz), piecewise linear
MASK = [(9.75, 0.0), (10.5, -20.0), (20.0, -28.0), (30.0, -40.0), (60.0, -40.0)]


def he20_tones():
    k = np.r_[-122:-1, 2:123]          # 242 used tones (DC +-1 null)
    return k


def ofdm(rng, mod_bits=6):
    """HE20 OFDM at 20 MS/s, returns complex baseband samples and the reference constellation points."""
    k = he20_tones()
    m = 2 ** (mod_bits // 2)
    lv = 2 * np.arange(m) - (m - 1)
    norm = np.sqrt(2 * np.mean(lv ** 2))
    syms, ref = [], []
    for _ in range(N_SYM):
        x = (rng.choice(lv, k.size) + 1j * rng.choice(lv, k.size)) / norm
        X = np.zeros(NFFT, complex)
        X[k % NFFT] = x
        t = np.fft.ifft(X) * np.sqrt(NFFT)
        syms.append(np.r_[t[-NFFT // 4:], t])
        ref.append(x)
    return np.concatenate(syms), np.array(ref)


def demod(y, ref):
    """Strip GI, FFT per symbol, best complex gain fit (ideal receiver equaliser: one gain), EVM."""
    k = he20_tones()
    L = NFFT + NFFT // 4
    rx = []
    for i in range(N_SYM):
        s = y[i * L + NFFT // 4:(i + 1) * L]
        rx.append(np.fft.fft(s)[k % NFFT] / np.sqrt(NFFT))
    rx = np.array(rx)
    # per-tone channel estimate (802.11 receivers equalise per subcarrier from the LTF)
    h = np.sum(rx * np.conj(ref), axis=0) / np.sum(np.abs(ref) ** 2, axis=0)
    err = rx - h * ref
    return 10 * np.log10(np.sum(np.abs(err) ** 2) / np.sum(np.abs(h * ref) ** 2))


def dac_filter(x, bits=10, fs_dac=40e6, fc=15.2e6, skew_s=0.0):
    """Upsample HE20 (20 MS/s) to the DAC rate (ideal interpolation), quantise, ZOH, analog filter.
    Output at FS_BB*OVS. skew_s delays Q relative to I (baseband path skew)."""
    up = int(round(fs_dac / FS_BB))
    xi = signal.resample_poly(x, up, 1)
    # digital TX spectral shaping in the FPGA (assumed; every 802.11 transmitter has one): equiripple
    # low-pass at the DAC rate, pass 9.7 MHz, stop from 10.4 MHz
    h = signal.remez(255, [0, 9.7e6, 10.4e6, fs_dac / 2], [1, 0], weight=[1, 30], fs=fs_dac)
    xi = np.convolve(xi, h, mode='same')
    full = 2 ** (bits - 1) - 1
    pk = np.max(np.abs(np.r_[xi.real, xi.imag]))
    q = lambda v: np.round(v / pk * full) / full * pk
    xi = q(xi.real) + 1j * q(xi.imag)
    r = int(round(FS_BB * OVS / fs_dac))
    zoh = np.repeat(xi, r)
    fs = FS_BB * OVS
    b, a = signal.butter(5, 2 * np.pi * fc, analog=True)
    bz, az = signal.bilinear(b, a, fs)
    yi = signal.lfilter(bz, az, zoh.real)
    yq = signal.lfilter(bz, az, zoh.imag)
    if skew_s:
        n = len(yq)
        f = np.fft.fftfreq(n, 1 / fs)
        yq = np.real(np.fft.ifft(np.fft.fft(yq) * np.exp(-2j * np.pi * f * skew_s)))
    return yi + 1j * yq


def rf_model(table):
    """Complex output (V pk across 50 ohm after balun) vs baseband magnitude (V diff)."""
    vin = np.array([0.0] + [r['vin'] for r in table])
    z = np.array([0j] + [complex(r['out_re'], r['out_im']) for r in table])
    ph0 = np.angle(z[1])
    mag = np.abs(z)
    ph = np.unwrap(np.angle(z[1:]) - ph0)
    ph = np.r_[ph[0], ph]

    def f(u):
        a = np.abs(u)
        g = np.interp(a, vin, mag, right=mag[-1])
        p = np.interp(a, vin, ph)
        return g * np.exp(1j * (np.angle(u) + p))
    return f, vin, mag


def spectrum_metrics(y, fs):
    f, p = signal.welch(y, fs, nperseg=4096, return_onesided=False, scaling='density')
    f = np.fft.fftshift(f); p = np.fft.fftshift(p)
    df = f[1] - f[0]
    inband = np.abs(f) <= 9.5e6
    pin = np.sum(p[inband]) * df
    adj = (np.abs(f - 20e6) <= 9.5e6), (np.abs(f + 20e6) <= 9.5e6)
    aclr = [10 * np.log10(pin / (np.sum(p[a]) * df)) for a in adj]
    # mask: PSD relative to the in-band average density, 100 kHz resolution (smoothing)
    ref = np.mean(p[np.abs(f) <= 9e6])
    k = max(1, int(round(100e3 / df)))
    ps = np.convolve(p, np.ones(k) / k, mode='same')
    margin = []
    for off, lim in zip(f, 10 * np.log10(ps / ref)):
        a = abs(off)
        if a < 9.75e6 or a > 60e6:
            continue
        lm = np.interp(a / 1e6, [m[0] for m in MASK], [m[1] for m in MASK])
        margin.append(lm - lim)
    return dict(aclr_dB_lower_upper=[round(x, 2) for x in aclr], mask_margin_dB=round(float(min(margin)), 2))


def run_case(fn, x0, ref, vrms, jitter_s=0.0, bb_skew_s=0.0, lo_phase_err_rad=0.0, cfr_papr_db=None, seed=2):
    fs = FS_BB * OVS
    x = x0.copy()
    if cfr_papr_db is not None:
        x = cfr(x, cfr_papr_db)
    u = dac_filter(x, skew_s=bb_skew_s)
    u = u / np.sqrt(np.mean(np.abs(u) ** 2)) * vrms
    if lo_phase_err_rad:   # LO quadrature phase error: Q branch rotated by the error
        i, q = u.real, u.imag
        u = (i - q * np.sin(lo_phase_err_rad)) + 1j * q * np.cos(lo_phase_err_rad)
    y = fn(u)
    if jitter_s:
        rng = np.random.default_rng(seed)
        y = y * np.exp(1j * 2 * np.pi * F_LO * jitter_s * rng.standard_normal(y.size))
    pout = 10 * np.log10(np.mean(np.abs(y) ** 2) / 2 / 50 / 1e-3)
    # receiver: ideal decimation back to 20 MS/s with the group delay of the filter removed
    d = np.argmax(np.abs(np.correlate(np.abs(y[:4000]), np.abs(np.repeat(x0[:200], OVS)), 'valid')))
    yd = signal.resample_poly(y[d:], 1, OVS)
    best = None
    for s in range(-2, 3):
        yy = yd[max(0, s):][:len(x0)]
        if len(yy) < len(x0):
            continue
        e = demod(yy, ref)
        best = e if best is None or e < best else best
    sm = spectrum_metrics(y, fs)
    return dict(pout_dBm=round(float(pout), 2), evm_dB=round(float(best), 2), **sm)


def cfr(x, papr_db, it=3):
    """Clip-and-filter crest-factor reduction (in-band tones kept, out-of-band regrowth removed)."""
    k = he20_tones()
    L = NFFT + NFFT // 4
    for _ in range(it):
        a = np.sqrt(np.mean(np.abs(x) ** 2)) * 10 ** (papr_db / 20)
        m = np.abs(x) > a
        x = np.where(m, a * x / np.maximum(np.abs(x), 1e-12), x)
        out = []
        for i in range(N_SYM):
            s = x[i * L + NFFT // 4:(i + 1) * L]
            X = np.fft.fft(s)
            keep = np.zeros(NFFT, bool); keep[k % NFFT] = True
            X[~keep] = 0
            t = np.fft.ifft(X)
            out.append(np.r_[t[-NFFT // 4:], t])
        x = np.concatenate(out)
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sim', default=str(HERE / 'generated' / 'rf_tx-sim-ext.json'))
    ap.add_argument('--out', default=str(HERE / 'generated' / 'rf_tx-modulation.json'))
    a = ap.parse_args()
    sim = json.loads(Path(a.sim).read_text())
    res = sim['results']
    out_modes = {}
    for mode, prefix in (('linear (txmix sat=0)', 'amam_'), ('high-gain (txmix sat=1)', 'amamsat_')):
        table = sorted([v['result'] for k, v in res.items() if k.startswith(prefix) and 'result' in v], key=lambda r: r['vin'])
        if table:
            out_modes[mode] = evaluate(table, res)
    Path(a.out).write_text(json.dumps(dict(model=__doc__.split('\n\n')[0], modes=out_modes), indent=1) + '\n')
    print(json.dumps({m: {k: o[k] for k in ('amam', 'at_0dBm', 'max_mean_power_meeting')} for m, o in out_modes.items()}, indent=1))


def evaluate(table, res):
    fn, vin, mag = rf_model(table)
    pdbm = 10 * np.log10(mag[1:] ** 2 / 2 / 50 / 1e-3)
    gain_ss = mag[1] / vin[1]
    lin = gain_ss * vin[1:]
    comp = 20 * np.log10(mag[1:] / lin)
    p1 = float(np.interp(-1.0, comp[::-1], pdbm[::-1])) if comp.min() < -1 else None
    rng = np.random.default_rng(1)
    x0, ref = ofdm(rng)
    papr = 10 * np.log10(np.max(np.abs(x0) ** 2) / np.mean(np.abs(x0) ** 2))
    out = dict(amam=dict(vin=vin[1:].tolist(), pout_dBm=pdbm.round(2).tolist(),
                                                          compression_dB=comp.round(2).tolist(), p1dB_out_dBm=p1,
                                                          psat_dBm=round(float(pdbm.max()), 2)),
               stimulus=dict(standard='802.11ax HE20, 242 tones, 64QAM, 60 symbols', papr_dB=round(float(papr), 2),
                             dac='10 bit, 40 MS/s, ZOH', filter='Butterworth 5th order, 15.2 MHz'),
               evm_limits_dB=EVM_LIMITS_DB, mask_dBr=MASK)
    # power sweep (no CFR and with CFR 8 dB)
    sweep = []
    for cf in (None, 8.0):
        for vr in np.round(np.geomspace(0.03, 0.4, 30), 4):
            r = run_case(fn, x0, ref, vr, cfr_papr_db=cf)
            r.update(bb_vrms=float(vr), cfr_papr_dB=cf)
            sweep.append(r)
    out['power_sweep'] = sweep

    def at_0dbm(rows):
        rows = [r for r in rows if r['pout_dBm'] >= -0.05]
        return min(rows, key=lambda r: r['pout_dBm']) if rows else None
    out['max_mean_power_meeting'] = {}
    for name, lim in EVM_LIMITS_DB.items():
        for cf in (None, 8.0):
            ok = [r for r in sweep if r['cfr_papr_dB'] == cf and r['evm_dB'] <= lim and r['mask_margin_dB'] >= 0]
            out['max_mean_power_meeting'][f'{name} (EVM {lim} dB + mask), cfr={cf}'] = max((r['pout_dBm'] for r in ok), default=None)
    out['at_0dBm'] = {('cfr_%s' % cf): at_0dbm([r for r in sweep if r['cfr_papr_dB'] == cf]) for cf in (None, 8.0)}
    # impairments at the 0 dBm operating point (CFR 8 dB)
    op = out['at_0dBm']['cfr_8.0'] or max(sweep, key=lambda r: r['pout_dBm'])
    vr = op['bb_vrms']
    out['lo_jitter_sweep'] = [dict(jitter_ps_rms=j, **run_case(fn, x0, ref, vr, jitter_s=j * 1e-12, cfr_papr_db=8.0))
                              for j in (0.0, 0.3, 0.5, 1.0, 2.0, 3.0)]
    out['bb_iq_skew_sweep'] = [dict(skew_ps=s, **run_case(fn, x0, ref, vr, bb_skew_s=s * 1e-12, cfr_papr_db=8.0))
                               for s in (0, 50, 100, 250, 500, 1000)]
    lo = []
    for k, v in sorted(res.items()):
        if k.startswith('skew_') and 'result' in v:
            irr = v['result']['image_rejection_dB']
            # image ratio -> equivalent quadrature phase error (gain error neglected): IRR = cot^2(theta/2)
            th = 2 * np.arctan(10 ** (-irr / 20))
            r = run_case(fn, x0, ref, vr, lo_phase_err_rad=float(th), cfr_papr_db=8.0)
            lo.append(dict(lo_q_skew_ps=v['meta']['lo_q_skew_ps'], image_rejection_dB_transistor=irr,
                           equiv_phase_err_deg=round(float(np.degrees(th)), 3), **r))
    out['lo_iq_skew_sweep'] = lo
    return out


if __name__ == '__main__':
    main()
